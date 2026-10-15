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

/** PUT 请求（如 /monitor/rules 保存）。超时与错误归一策略与 POST 一致。 */
async function putPluginApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.put) throw new Error('缺少 MoviePilot 注入的 api.put')
  const timeoutMs = Math.max(0, Number(options.timeoutMs) || DEFAULT_POST_TIMEOUT_MS);
  const url = pluginPath(pluginId, path);
  const startedAt = Date.now();
  try {
    return await withTimeout(api, 'put', url, payload, timeoutMs)
  } catch (err) {
    throw normalizeError(err, path)
  } finally {
    const elapsed = Date.now() - startedAt;
    if (timeoutMs && elapsed >= SLOW_REQUEST_MS) {
      console.warn(`[TgMediaCenter] PUT ${path} ${elapsed}ms`);
    }
  }
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

/**
 * 流水「决策」字段的展示辅助（详情页 / 仪表盘 / 资源监控面板共用）。
 *
 * 决策值是入库的英文常量（model/hit_log.py），直接展示对人不友好；
 * 这里做一层中文映射，未认识的值原样返回（前向兼容新决策）。
 *
 * 注意：文案必须与后端 ``model/hit_log.py`` 的 ``DECISION_LABELS`` 逐字一致，
 * 否则筛选下拉（取后端选项）与流水徽章（取本模块）会对不上。
 */

const DECISION_LABELS = {
  hit: '命中推送',
  failed: '处理失败',
  skipped_not_missing: '媒体库已存在',
  skipped_not_subscribed: '未订阅',
  skipped_unrecognized: '无法识别',
  skipped_keyword: '关键词未命中',
  skipped_excluded: '命中排除词',
  skipped_no_link: '无可推链接',
  skipped_unknown: '无法判断',
  skipped_extension: '扩展名未命中',
  skipped_pt_active: 'PT 在途',
  skipped_pt_waiting: '等 PT 成熟期',
};

/** 决策中文文案（未知值原样返回）。 */
function decisionLabel(value) {
  const key = String(value || '').trim();
  return DECISION_LABELS[key] || key || '—'
}

/** 决策徽章颜色。 */
function decisionColor(value) {
  if (value === 'hit') return 'success'
  if (value === 'failed') return 'error'
  if (String(value || '').startsWith('skipped')) return 'default'
  return 'primary'
}

export { _export_sfc as _, getPluginApi as a, decisionColor as b, putPluginApi as c, decisionLabel as d, getPluginConfig as g, postPluginApi as p, savePluginConfig as s, unwrap as u };
