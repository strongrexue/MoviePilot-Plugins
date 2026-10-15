/**
 * 插件 API 封装。
 *
 * 约定（对齐 MoviePilot V3 API 响应适配指南）：
 * - 使用宿主注入的 api 客户端，baseURL 已含 /api/v1/，因此只传相对路径；
 * - 路径统一拼成 `plugin/<pluginId>/<path>`，pluginId 来自宿主注入，保证虚拟分身隔离；
 * - 插件后端统一返回 schemas.Response[T]，读取时按 envelope 取 data，同时兼容裸业务模型。
 */

const SLOW_REQUEST_MS = 1500;
const DEFAULT_TIMEOUT_MS = 20000;

/** 渲染类接口（预取素材 + 合成）耗时远高于普通查询，单独放宽到 60s：
 *  首次预览「海报墙」这类布局要并行下载几十张海报，20s 会误判超时。 */
const RENDER_TIMEOUT_MS = 60000;

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

/** 把传输层错误翻译成可读提示（后端 detail 优先）。 */
function normalizeError(err, path) {
  if (!err || typeof err !== 'object') return err
  const status = Number(err.response?.status) || 0;
  const detail = typeof err.response?.data?.detail === 'string' ? err.response.data.detail.trim() : '';
  if (detail) return new Error(detail)
  const raw = String(err?.message || '');
  if (raw && !/^Request failed with status code \d+/.test(raw) && !/^Network Error$/i.test(raw)) return err
  if (status === 401 || status === 403) return new Error(`未授权（HTTP ${status}）：请重新登录 MoviePilot 后再试`)
  if (status >= 500) return new Error(`插件后端异常（HTTP ${status}）：请查看 MoviePilot 运行日志`)
  if (!status) return new Error(`网络请求失败（${path}）：无法连接 MoviePilot 后端`)
  return err
}

async function withTimeout(api, method, url, payload, timeoutMs) {
  const controller = typeof AbortController === 'function' ? new AbortController() : null;
  const signal = controller ? { signal: controller.signal } : undefined;
  const doRequest = () => {
    if (method === 'get') return api.get(url, signal)
    if (method === 'put') return api.put(url, payload, signal)
    return api.post(url, payload, signal)
  };
  if (!timeoutMs) return doRequest()
  let timerId;
  const request = Promise.resolve().then(doRequest);
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

async function request(api, method, pluginId, path, payload, options = {}) {
  const timeoutMs = Math.max(0, Number(options.timeoutMs) || DEFAULT_TIMEOUT_MS);
  const url = pluginPath(pluginId, path);
  const startedAt = Date.now();
  try {
    return await withTimeout(api, method, url, payload, timeoutMs)
  } catch (err) {
    throw normalizeError(err, path)
  } finally {
    const elapsed = Date.now() - startedAt;
    if (timeoutMs && elapsed >= SLOW_REQUEST_MS) {
      console.warn(`[EmbyCoverCenter] ${method.toUpperCase()} ${path} ${elapsed}ms`);
    }
  }
}

async function getPluginApi(api, pluginId, path, options = {}) {
  if (!api?.get) throw new Error('缺少 MoviePilot 注入的 api.get')
  return request(api, 'get', pluginId, path, undefined, options)
}

async function postPluginApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('缺少 MoviePilot 注入的 api.post')
  return request(api, 'post', pluginId, path, payload, options)
}

/** 读取配置（宿主提供 plugin/<id> 的 GET/PUT 配置接口）。 */
async function getPluginConfig(api, pluginId) {
  if (!api?.get) throw new Error('缺少 MoviePilot 配置 API')
  const response = await api.get(pluginPath(pluginId));
  return unwrap(response)
}

/** 保存配置。 */
async function savePluginConfig(api, pluginId, payload = {}) {
  if (!api?.put) throw new Error('缺少 MoviePilot 配置 API')
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

export { RENDER_TIMEOUT_MS as R, _export_sfc as _, getPluginApi as a, getPluginConfig as g, postPluginApi as p, savePluginConfig as s, unwrap as u };
