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
  // ② 115 网盘（登录态只走扫码，Cookie 存插件数据，不放配置/表单）
  pan115_enabled: false,
  pan115_target_cid: '',
  pan115_batch_max_size: 20,
  // ④ TG 资源监控（规则结构见 /monitor/rules 接口返回；id 由后端补缺）
  monitor_enabled: false,
  monitor_rules: [],
  // ⑤ 历史消息缓存（设置由 /cache/settings 归一，这里保证「保存配置」不丢字段）
  cache_enabled: false,
  cache_chat_ids: [],
  cache_destination: 'smart',
  cache_sync_mode: 'relative',
  cache_sync_days: 30,
  cache_batch_size: 200,
  cache_subscribe_enabled: true,
  cache_backfill_enabled: false,
  cache_cron: '0 */6 * * *',
  cache_subscribe_cron: '*/30 * * * *',
  cache_backfill_cron: '*/30 * * * *',
  // ⑥ TG 通用转发（规则结构见 /forward/rules 接口返回；id 由后端补缺，f 前缀）
  forward_enabled: false,
  forward_rules: [],
  // 通知（P7 启用：走 MP 通知渠道 post_message）
  notify_on_hit: true,
  notify_on_error: true,
  notify_on_search: true,
  interactive_push: true,
  interactive_dedup: true,
  // ⑨ 发现页入口（1.8.0）：在 MP 左侧「发现」分区注册本插件整页入口
  discovery_page_enabled: false,
  // ⑩ P9 重复获取治理（1.9.0）
  //   注意：P9-1 只放出「能力探针」（反向 R0 开关 1.9.1 真机验证无收益后移除），
  //   闸门 A 的三个键先在表单里占位，保证「保存配置」整份覆盖时不会把它们清掉
  //  （P9-2 落地后再给界面控件）。
  p9_forward_gate_enabled: false,
  p9_maturity_hours: 2,
  p9_check_downloader: true,
  // ⑪ 反向闸门 R1（1.13.8）：新增订阅时跳过宿主的「首次全站搜索」
  //   独立开关，与 cache_subscribe_enabled（订阅回搜）互不依赖；默认关
  skip_first_search_enabled: false,
}

// ⚠️ 新增配置项时必须同步加到这里：保存是"整份覆盖"，
// 表单里没有的字段会被清空（后端自管状态请改存插件数据，不要放配置）。

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
