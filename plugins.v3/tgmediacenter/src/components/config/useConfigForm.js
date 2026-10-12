import { reactive, ref } from 'vue'
import { getPluginConfig } from '../api'

/**
 * 插件配置表单逻辑。
 *
 * 约定：
 * - 默认值在这里维护一份，与后端 `default_config()` 对齐（后端是权威，此处仅用于首屏渲染）；
 * - 保存时整体提交，交由后端 `update_config()` 覆盖写入；
 * - 敏感字段（会话串 / Cookie）由后端掩码返回，前端不回写空值覆盖。
 */
export const configDefaults = {
  enabled: false,
  // ① TG 核心凭证
  tg_api_id: '',
  tg_api_hash: '',
  tg_phone: '',
  tg_session_string: '',
  tg_user_cooldown_seconds: 5,
  tg_keep_alive_seconds: 60,
  tg_aggregation_window_seconds: 3.0,
}

/** 不参与表单回写的敏感字段：保存时若为空则跳过。 */
const SECRET_FIELDS = new Set(['tg_session_string'])

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

  async function loadConfig() {
    loading.value = true
    error.value = ''
    try {
      const value = initialConfig?.() || await getPluginConfig(api(), pluginId())
      applyConfig(value)
    } catch (err) {
      error.value = err?.message || '配置读取失败'
    } finally {
      loading.value = false
    }
  }

  function buildPayload() {
    const payload = { ...form }
    for (const key of SECRET_FIELDS) {
      if (!payload[key]) delete payload[key]
    }
    return payload
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
