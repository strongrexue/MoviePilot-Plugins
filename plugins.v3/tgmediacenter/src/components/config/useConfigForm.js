import { reactive, ref } from 'vue'
import { getPluginConfig } from '../api'

/**
 * 插件配置表单逻辑。
 *
 * 约定：
 * - 默认值在这里维护一份，与后端 `default_config()` 对齐（后端是权威，此处仅用于首屏渲染）；
 * - 保存时整体提交，交由宿主 `update_config()` **覆盖**写入；
 * - 后端自己维护的状态（如 TG 会话串、对话缓存）一律**不放进表单**，否则一次保存就会把它
 *   连同表单一起覆盖掉。宿主注入的 `initialConfig` 是"打开配置页那一刻"的快照，
 *   因此**优先重新拉取**，拉取失败才退回快照。
 */
export const configDefaults = {
  enabled: false,
  // ① TG 核心凭证
  tg_api_id: '',
  tg_api_hash: '',
  tg_phone: '',
  tg_user_cooldown_seconds: 5,
  tg_keep_alive_seconds: 60,
  tg_aggregation_window_seconds: 3.0,
}

export function useConfigForm({ api, pluginId, initialConfig, emit }) {
  const form = reactive({ ...configDefaults })
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')

  function applyConfig(value) {
    const source = value && typeof value === 'object' ? value : {}
    for (const [key, fallback] of Object.entries(configDefaults)) {
      const next = source[key]
      form[key] = next === undefined || next === null ? fallback : next
    }
  }

  function snapshot() {
    try {
      const value = typeof initialConfig === 'function' ? initialConfig() : initialConfig
      return value && typeof value === 'object' ? value : {}
    } catch {
      return {}
    }
  }

  async function loadConfig() {
    loading.value = true
    error.value = ''
    try {
      // 快照可能早于后端写入（例如登录成功后保存的会话），因此以实时读取为准
      let value = null
      try {
        value = await getPluginConfig(api(), pluginId())
      } catch (err) {
        value = null
        error.value = err?.message || ''
      }
      applyConfig(value && Object.keys(value).length ? value : snapshot())
    } catch (err) {
      error.value = err?.message || '配置读取失败'
      applyConfig(snapshot())
    } finally {
      loading.value = false
    }
  }

  function buildPayload() {
    return { ...form }
  }

  async function saveConfig() {
    if (saving.value) return
    saving.value = true
    error.value = ''
    try {
      emit('save', buildPayload())
    } finally {
      saving.value = false
    }
  }

  return reactive({
    form,
    loading,
    saving,
    error,
    loadConfig,
    saveConfig,
    applyConfig,
  })
}
