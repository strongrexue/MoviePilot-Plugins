/**
 * 插件 API 封装。
 *
 * 约定（对齐 MoviePilot V3 API 响应适配指南）：
 * - 使用宿主注入的 api 客户端，baseURL 已含 /api/v1/，因此只传相对路径；
 * - 路径统一拼成 `plugin/<pluginId>/<path>`，pluginId 来自宿主注入，保证虚拟分身隔离；
 * - 插件后端统一返回 schemas.Response[T]，读取时按 envelope 取 data，同时兼容裸业务模型。
 */

const SLOW_REQUEST_MS = 1500;
/**
 * POST 默认超时。登录/发码/拉对话都要走 Telegram 网络，经代理时可能较慢，
 * 因此给得比较宽；关键是不能无限等待（否则界面会一直转圈）。
 * 注意：真正的上限通常来自反向代理的读超时（约 60 秒），因此各调用点会给
 * 更贴近后端预算的值，这里只是兜底。
 */
const DEFAULT_POST_TIMEOUT_MS = 75000;

function pluginPath(pluginId, path = '') {
  const id = String(pluginId || '').trim();
  if (!id) throw new Error('缺少 MoviePilot 注入的 pluginId')
  const suffix = String(path || '').replace(/^\/+/, '');
  return suffix ? `plugin/${id}/${suffix}` : `plugin/${id}`
}

/** 从统一 envelope 或裸业务模型中取出业务数据。 */
function unwrap(response) {
  if (response && typeof response === 'object' && 'success' in response && 'data' in response) {
    if (response.success === false) {
      throw new Error(response.message || '插件接口调用失败')
    }
    return response.data
  }
  return response
}

function timeoutError(path, timeoutMs) {
  const error = new Error(`请求超时（${Math.ceil(timeoutMs / 1000)} 秒）：${path}`);
  error.code = 'PLUGIN_API_TIMEOUT';
  return error
}

/** axios 自己的默认文案，遇到这些才说明"没人翻译过"。 */
function isRawNetworkError(message) {
  return /^Request failed with status code \d+/.test(message)
    || /^Network Error$/i.test(message)
    || /^timeout of \d+ms exceeded$/i.test(message)
}

/**
 * 把网关/传输层错误翻译成可操作的中文提示。
 *
 * 典型场景：首次发码要现连 Telegram，超过反向代理的读超时后前端只会收到一个
 * 502 页面（后端其实还在跑，验证码也确实发出去了）。此时必须给用户可执行的指引，
 * 而不是 "Request failed with status code 502"。
 */
function normalizeError(err, path) {
  if (!err || typeof err !== 'object') return err

  const response = err.response;
  const status = Number(response?.status) || 0;
  const data = response?.data;
  const detail = typeof data?.detail === 'string' ? data.detail.trim() : '';
  const rawMessage = String(err?.message || '');

  // 后端返回的业务/超时提示最准确，优先展示
  if (detail) {
    const wrapped = new Error(detail);
    wrapped.status = status;
    return wrapped
  }
  // 已经是宿主编排或本封装给出的提示，保持不动
  if (rawMessage && !isRawNetworkError(rawMessage)) return err

  if (status === 502 || status === 503 || status === 504) {
    const wrapped = new Error(
      `请求被网关中断（HTTP ${status}）：连接 Telegram 或拉取数据较慢时会出现。`
      + '请等待约 10 秒后重试；若你刚点过「发送验证码」，验证码可能已经发出——可直接输入验证码登录。',
    );
    wrapped.status = status;
    wrapped.code = 'GATEWAY_TIMEOUT';
    return wrapped
  }
  if (status === 401 || status === 403) {
    const wrapped = new Error(`未授权（HTTP ${status}）：请重新登录 MoviePilot 后再试`);
    wrapped.status = status;
    return wrapped
  }
  if (status >= 500) {
    const wrapped = new Error(`插件后端异常（HTTP ${status}）：请查看 MoviePilot 运行日志`);
    wrapped.status = status;
    return wrapped
  }
  if (!status) {
    return new Error(`网络请求失败（${path}）：无法连接 MoviePilot 后端，请检查网络或反向代理`)
  }
  return err
}

async function withTimeout(api, method, url, payload, timeoutMs) {
  const send = () => (method === 'get' ? api.get(url) : api.post(url, payload));
  if (!timeoutMs) return send()

  const controller = typeof AbortController === 'function' ? new AbortController() : null;
  let timerId;
  const request = Promise.resolve().then(() =>
    method === 'get'
      ? api.get(url, controller ? { signal: controller.signal } : undefined)
      : api.post(url, payload, controller ? { signal: controller.signal } : undefined),
  );
  const timeout = new Promise((_, reject) => {
    timerId = setTimeout(() => {
      controller?.abort();
      reject(timeoutError(url, timeoutMs));
    }, timeoutMs);
  });
  try {
    return await Promise.race([request, timeout])
  } finally {
    clearTimeout(timerId);
  }
}

async function getPluginApi(api, pluginId, path, options = {}) {
  if (!api?.get) throw new Error('缺少 MoviePilot 注入的 api.get')
  const timeoutMs = Math.max(0, Number(options.timeoutMs) || 0);
  const url = pluginPath(pluginId, path);
  const startedAt = Date.now();
  try {
    return await withTimeout(api, 'get', url, undefined, timeoutMs)
  } catch (err) {
    throw normalizeError(err, path)
  } finally {
    const elapsed = Date.now() - startedAt;
    if (timeoutMs && elapsed >= SLOW_REQUEST_MS) {
      console.warn(`[TgMediaCenter] GET ${path} ${elapsed}ms`);
    }
  }
}

async function postPluginApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('缺少 MoviePilot 注入的 api.post')
  // POST 默认给一个上限：没有超时的话，后端卡住时前端会无限转圈，用户无从判断
  const timeoutMs = Math.max(0, Number(options.timeoutMs) || DEFAULT_POST_TIMEOUT_MS);
  const url = pluginPath(pluginId, path);
  const startedAt = Date.now();
  try {
    return await withTimeout(api, 'post', url, payload, timeoutMs)
  } catch (err) {
    throw normalizeError(err, path)
  } finally {
    const elapsed = Date.now() - startedAt;
    if (timeoutMs && elapsed >= SLOW_REQUEST_MS) {
      console.warn(`[TgMediaCenter] POST ${path} ${elapsed}ms`);
    }
  }
}

/** 读取配置（宿主提供 plugin/<id> 的 GET/PUT 配置接口）。 */
async function getPluginConfig(api, pluginId) {
  const response = await api.get(pluginPath(pluginId));
  return unwrap(response)
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, getPluginConfig as a, getPluginApi as g, postPluginApi as p, unwrap as u };
