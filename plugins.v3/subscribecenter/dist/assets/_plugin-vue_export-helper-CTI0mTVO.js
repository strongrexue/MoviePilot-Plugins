/**
 * 前端组件版本号。
 *
 * ⚠️ 必须与后端 `SubscribeCenter.plugin_version` 一致。
 *
 * 为什么单独放一个文件：`remoteEntry.js` 文件名固定无哈希，宿主加载器也不追加缓存参数，
 * 浏览器只在页面加载时拉取一次远程组件。因此"插件更新了但界面还是旧的"是常态，
 * 唯一能确认当前浏览器到底加载了哪一版的办法，就是在组件里把这个号显示出来、
 * 并与后端 `/status` 返回的 plugin_version 比对；不一致就提示硬刷新。
 */
const FRONTEND_VERSION = '1.17.2';

/**
 * 插件 API 封装。
 *
 * 约定（对齐 MoviePilot V3 API 响应适配指南）：
 * - 使用宿主注入的 api 客户端，baseURL 已含 /api/v1/，因此只传相对路径；
 * - 路径统一拼成 `plugin/<pluginId>/<path>`，pluginId 来自宿主注入，保证虚拟分身隔离；
 * - 插件后端统一返回 schemas.Response[T]，读取时按 envelope 取 data，同时兼容裸业务模型。
 */

const SLOW_REQUEST_MS = 1500;
const DEFAULT_POST_TIMEOUT_MS = 120000;

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

function isRawNetworkError(message) {
  return /^Request failed with status code \d+/.test(message)
    || /^Network Error$/i.test(message)
    || /^timeout of \d+ms exceeded$/i.test(message)
}

function normalizeError(err, path) {
  if (!err || typeof err !== 'object') return err

  const response = err.response;
  const status = Number(response?.status) || 0;
  const data = response?.data;
  const detail = typeof data?.detail === 'string' ? data.detail.trim() : '';
  const rawMessage = String(err?.message || '');

  if (detail) {
    const wrapped = new Error(detail);
    wrapped.status = status;
    return wrapped
  }
  if (rawMessage && !isRawNetworkError(rawMessage)) return err

  if (status === 502 || status === 503 || status === 504) {
    const wrapped = new Error(
      `请求被网关中断（HTTP ${status}）：发现任务可能仍在后台运行，请稍后刷新状态查看结果。`,
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
  const doRequest = (signal) => {
    if (method === 'get') return api.get(url, signal ? { signal } : undefined)
    if (method === 'put') return api.put(url, payload, signal ? { signal } : undefined)
    return api.post(url, payload, signal ? { signal } : undefined)
  };
  if (!timeoutMs) return doRequest()

  const controller = typeof AbortController === 'function' ? new AbortController() : null;
  let timerId;
  const request = Promise.resolve().then(() => doRequest(controller?.signal));
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

async function request(api, method, pluginId, path, payload, timeoutMs) {
  if (!api?.[method]) throw new Error(`缺少 MoviePilot 注入的 api.${method}`)
  const url = pluginPath(pluginId, path);
  const startedAt = Date.now();
  try {
    return await withTimeout(api, method, url, payload, timeoutMs)
  } catch (err) {
    throw normalizeError(err, path)
  } finally {
    const elapsed = Date.now() - startedAt;
    if (timeoutMs && elapsed >= SLOW_REQUEST_MS) {
      console.warn(`[SubscribeCenter] ${method.toUpperCase()} ${path} ${elapsed}ms`);
    }
  }
}

async function getPluginApi(api, pluginId, path, options = {}) {
  return request(api, 'get', pluginId, path, undefined, Math.max(0, Number(options.timeoutMs) || 0))
}

async function postPluginApi(api, pluginId, path, payload = {}, options = {}) {
  const timeoutMs = Math.max(0, Number(options.timeoutMs) || DEFAULT_POST_TIMEOUT_MS);
  return request(api, 'post', pluginId, path, payload, timeoutMs)
}

/** 读取配置（宿主提供 plugin/<id> 的 GET/PUT 配置接口）。 */
async function getPluginConfig(api, pluginId) {
  const response = await api.get(pluginPath(pluginId));
  return unwrap(response)
}

/** 保存配置。 */
async function savePluginConfig(api, pluginId, payload = {}) {
  const response = await api.put(pluginPath(pluginId), payload);
  return unwrap(response)
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { FRONTEND_VERSION as F, _export_sfc as _, getPluginConfig as a, getPluginApi as g, postPluginApi as p, savePluginConfig as s, unwrap as u };
