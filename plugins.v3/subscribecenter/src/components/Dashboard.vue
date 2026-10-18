<script setup>
/**
 * 仪表盘小组件：紧凑展示运行状态与今日写入进度。
 */
import { computed, onMounted, ref } from 'vue'
import { FRONTEND_VERSION } from './version'
import { getPluginApi, unwrap } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'SubscribeCenter' },
  config: { type: Object, default: () => ({}) },
})

const status = ref(null)
const error = ref('')

const backendVersion = computed(() => String(status.value?.plugin_version || ''))
const versionMismatch = computed(
  () => backendVersion.value && backendVersion.value !== FRONTEND_VERSION,
)

const progress = computed(() => {
  const s = status.value
  if (!s) return 0
  const limit = Number(s.daily_limit) || 0
  if (!limit) return 0
  return Math.min(100, Math.round((Number(s.written_today) / limit) * 100))
})

async function load() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status'))
    error.value = ''
  } catch (err) {
    error.value = err?.message || '状态加载失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="sc-dash">
    <VAlert
      v-if="versionMismatch"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-2"
      text="前端组件与后端版本不一致，请 Ctrl+Shift+R 硬刷新。"
    />
    <VAlert v-if="error" type="error" variant="tonal" density="compact" class="mb-2" :text="error" />

    <template v-if="status">
      <div class="d-flex align-center flex-wrap ga-2 mb-2">
        <VChip size="small" variant="flat" :color="status.enabled ? 'success' : 'default'">
          {{ status.enabled ? '已启用' : '未启用' }}
        </VChip>
            <VChip v-if="status.busy" size="small" variant="flat" color="warning">运行中</VChip>
      </div>

      <div class="sc-hint mb-1">
        今日写入 {{ status.written_today }} / {{ status.daily_limit }}
      </div>
      <VProgressLinear :model-value="progress" height="6" rounded class="mb-2" />

      <div class="sc-hint">最近运行：{{ status.last_run || '—' }}</div>
      <div class="sc-hint">
        上次拉取 {{ status.last_summary?.fetched ?? 0 }} 条 ·
        新增 {{ status.last_summary?.added ?? 0 }} 条 ·
        待确认 {{ status.last_summary?.pending_review ?? 0 }} 条
      </div>
    </template>
    <div v-else class="sc-hint">状态加载中…</div>
  </div>
</template>

<style scoped>
.sc-dash {
  padding: 4px;
}
.sc-hint {
  font-size: 12px;
  line-height: 1.5;
  opacity: 0.75;
}
</style>
