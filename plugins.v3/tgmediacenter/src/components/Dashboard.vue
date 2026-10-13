<script setup>
import { computed, onMounted, ref } from 'vue'
import { getPluginApi, unwrap } from './api'
import { decisionLabel } from './decision'

/**
 * 插件仪表盘卡片（宿主首页的模块卡片）。
 *
 * 与详情页（Page.vue）共用 ``/overview`` 聚合接口：卡片只放"一眼可见"的
 * 汇总（TG / 115 / 缓存 / 队列）+ 最近几条监控流水，详细排查去详情页。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, default: () => ({}) },
})

const loading = ref(false)
const loadError = ref('')
const data = ref(null)

const dashboardPluginId = () => String(props.pluginId || '').trim() || 'TgMediaCenter'

async function loadData() {
  loading.value = true
  loadError.value = ''
  try {
    data.value = unwrap(await getPluginApi(props.api, dashboardPluginId(), 'overview', { timeoutMs: 15000 }))
  } catch (error) {
    loadError.value = error?.message || '概览加载失败'
  } finally {
    loading.value = false
  }
}

const tg = computed(() => data.value?.tg || {})
const pan115 = computed(() => data.value?.pan115 || {})
const cache = computed(() => data.value?.cache || {})
const monitor = computed(() => data.value?.monitor || {})
const forward = computed(() => data.value?.forward || {})
const pipeline = computed(() => monitor.value.pipeline || {})
const recent = computed(() => (data.value?.recent_hits || []).slice(0, 5))

const tgOk = computed(() => Boolean(tg.value.connected && tg.value.authorized))
const pan115Ok = computed(() => Boolean(pan115.value.enabled && pan115.value.authorized))
const cacheOk = computed(() => Boolean(cache.value.enabled))

function fmtTime(value) {
  return String(value || '').replace('T', ' ').slice(5, 16) || '—'
}

function mediaName(item) {
  if (!item.title) return `消息 #${item.message_id}`
  const year = item.year ? ` (${item.year})` : ''
  let name = `${item.title}${year}`
  if (item.season || item.episode) {
    name += ` S${String(item.season ?? 1).padStart(2, '0')}E${String(item.episode ?? 0).padStart(2, '0')}`
  }
  return name
}

onMounted(loadData)
</script>

<template>
  <VCard flat class="tg-dashboard">
    <VCardItem class="tg-dashboard-header">
      <template #prepend>
        <VAvatar color="primary" variant="tonal" rounded="lg" size="40">
          <VIcon icon="mdi-chart-box-outline" />
        </VAvatar>
      </template>
      <VCardTitle class="text-subtitle-1">TG媒体中心</VCardTitle>
      <VCardSubtitle class="text-caption">
        TG / 115 / 缓存概览 · 缓存 {{ cache.total ?? 0 }} 条 · 队列待处理 {{ pipeline.push_pending ?? 0 }}
      </VCardSubtitle>
      <template #append>
        <VBtn icon variant="text" size="small" :loading="loading" @click="loadData">
          <VIcon icon="mdi-refresh" />
        </VBtn>
      </template>
    </VCardItem>
    <VDivider />
    <VProgressLinear v-if="loading" indeterminate color="primary" height="2" />
    <VCardText class="pa-3">
      <VAlert v-if="loadError" type="warning" variant="tonal" density="compact">{{ loadError }}</VAlert>

      <template v-else-if="data">
        <div class="tg-chips">
          <VChip size="small" variant="tonal" :color="tgOk ? 'success' : 'warning'" label>
            TG {{ tgOk ? '已连接' : (tg.api_configured ? '未连接' : '未配置') }}
          </VChip>
          <VChip size="small" variant="tonal" :color="pan115Ok ? 'success' : 'default'" label>
            115 {{ pan115Ok ? '已登录' : (pan115.enabled ? '未登录' : '未启用') }}
          </VChip>
          <VChip size="small" variant="tonal" :color="cacheOk ? 'info' : 'default'" label>
            缓存 {{ cache.chats ?? 0 }} 频道
          </VChip>
          <VChip size="small" variant="tonal" color="primary" label>
            监控命中 {{ pipeline.hit ?? 0 }}
          </VChip>
          <VChip size="small" variant="tonal" color="primary" label>
            转发命中 {{ pipeline.forward_hit ?? 0 }}
          </VChip>
          <VChip
            size="small"
            variant="tonal"
            :color="(pipeline.push_failed ?? 0) > 0 ? 'error' : 'default'"
            label
          >
            失败 {{ pipeline.push_failed ?? 0 }}
          </VChip>
          <VChip size="small" variant="tonal" color="default" label>
            规则 {{ (monitor.rules_count ?? 0) + (forward.rules_count ?? 0) }} 条
          </VChip>
        </div>

        <div v-if="recent.length" class="tg-recent">
          <div class="tg-recent-title">最近流水</div>
          <div v-for="item in recent" :key="`${item.kind}-${item.id}`" class="tg-recent-row">
            <span class="tg-recent-media">{{ mediaName(item) }}</span>
            <span class="tg-recent-meta">{{ decisionLabel(item.decision) }} · {{ fmtTime(item.created_at) }}</span>
          </div>
        </div>
        <div v-else class="tg-empty">暂无命中记录：规则命中后会在这里出现。</div>
      </template>
    </VCardText>
  </VCard>
</template>

<style scoped>
.tg-dashboard {
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.tg-dashboard-header { padding: 12px 16px; }
.tg-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.tg-recent { margin-top: 10px; }
.tg-recent-title { font-size: 12px; opacity: 0.7; margin-bottom: 4px; }
.tg-recent-row { display: flex; align-items: center; gap: 8px; font-size: 12.5px; padding: 2px 0; }
.tg-recent-media { flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tg-recent-meta { flex: 0 0 auto; font-size: 11.5px; opacity: 0.7; }
.tg-empty { padding: 12px; text-align: center; font-size: 12.5px; opacity: 0.65; }
</style>
