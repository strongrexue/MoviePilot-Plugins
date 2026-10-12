/**
 * 插件 API 封装。
 *
 * 约定（对齐 MoviePilot V3 API 响应适配指南）：
 * - 使用宿主注入的 api 客户端，baseURL 已含 /api/v1/，因此只传相对路径；
 * - 路径统一拼成 `plugin/<pluginId>/<path>`，pluginId 来自宿主注入，保证虚拟分身隔离；
 * - 插件后端统一返回 schemas.Response[T]，读取时按 envelope 取 data，同时兼容裸业务模型。
 */

const SLOW_REQUEST_MS = 1500;

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
  } finally {
    const elapsed = Date.now() - startedAt;
    if (timeoutMs && elapsed >= SLOW_REQUEST_MS) {
      console.warn(`[TgMediaCenter] GET ${path} ${elapsed}ms`);
    }
  }
}

async function postPluginApi(api, pluginId, path, payload = {}) {
  if (!api?.post) throw new Error('缺少 MoviePilot 注入的 api.post')
  return await withTimeout(api, 'post', pluginPath(pluginId, path), payload, 0)
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
