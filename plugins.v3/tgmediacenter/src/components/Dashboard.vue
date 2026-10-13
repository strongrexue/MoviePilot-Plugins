<script setup>
import { computed, onMounted, ref } from 'vue'
import { getPluginApi, unwrap } from './api'
import { decisionLabel } from './decision'

/**
 * 插件仪表盘卡片（宿主首页的模块卡片）。
 *
 * 与详情页（Page.vue）共用 ``/overview`` 聚合接口：卡片只放"一眼可见"的
 * 汇总（TG / 115 / 缓存 / 队列）+ 最近几条监控流水。
 *
 * 流水默认只显示摘要（``SUMMARY_LIMIT`` 条，避免首页卡片被拉长）；想往下翻用
 * 「加载更多」，按 20 条一页走 ``/monitor/hits`` 分页接口追加，最多 ``MAX_HITS`` 条。
 * 完整流水与关键词搜索在插件「资源监控」面板（宿主未提供可靠的插件页深链，
 * 所以这里不跳转，只用一行提示指路）。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, default: () => ({}) },
})

const SUMMARY_LIMIT = 5
const PAGE_STEP = 20
const MAX_HITS = 100

const loading = ref(false)
const loadingMore = ref(false)
const loadError = ref('')
const data = ref(null)
const extraHits = ref([])
const loadedPages = ref(0)
const hitsTotal = ref(0)

const dashboardPluginId = () => String(props.pluginId || '').trim() || 'TgMediaCenter'

async function loadData() {
  loading.value = true
  loadError.value = ''
  // 概览刷新会重置追加的流水（拿到最新一屏），避免新旧两批混在一起
  extraHits.value = []
  loadedPages.value = 0
  hitsTotal.value = 0
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

const hitKey = (item) => `${item.kind}-${item.id}`

const recent = computed(() => {
  const base = (data.value?.recent_hits || []).slice(0, SUMMARY_LIMIT)
  if (!extraHits.value.length) return base
  // 追加页与摘要来自同一张表，按 kind+id 去重，避免同一条出现两次
  const seen = new Set(base.map(hitKey))
  const merged = [...base]
  for (const item of extraHits.value) {
    if (seen.has(hitKey(item))) continue
    seen.add(hitKey(item))
    merged.push(item)
  }
  return merged
})

const canLoadMore = computed(() => {
  if (loadingMore.value) return false
  if (recent.value.length >= MAX_HITS) return false
  // 还没点过：先让点，拿到 total 后再按剩量判断
  if (!loadedPages.value) return true
  return hitsTotal.value > recent.value.length
})

async function loadMore() {
  if (loadingMore.value || !canLoadMore.value) return
  loadingMore.value = true
  loadError.value = ''
  try {
    const nextPage = loadedPages.value + 1
    const params = new URLSearchParams({
      page: String(nextPage),
      page_size: String(PAGE_STEP),
    })
    const res = unwrap(await getPluginApi(
      props.api, dashboardPluginId(), `monitor/hits?${params.toString()}`, { timeoutMs: 15000 },
    ))
    loadedPages.value = nextPage
    hitsTotal.value = res?.total || 0
    const seen = new Set([...recent.value.map(hitKey)])
    const fresh = (res?.items || []).filter(item => !seen.has(hitKey(item)))
    extraHits.value = [...extraHits.value, ...fresh].slice(0, MAX_HITS)
  } catch (error) {
    loadError.value = error?.message || '加载更多流水失败'
  } finally {
    loadingMore.value = false
  }
}

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
    const s = String(item.season ?? 1).padStart(2, '0')
    const e = String(item.episode ?? 0).padStart(2, '0')
    const end = Number(item.episode_end ?? 0)
    if (end > (item.episode ?? 0)) {
      name += ` S${s}E${e}-E${String(end).padStart(2, '0')}`
    } else {
      name += ` S${s}E${e}`
    }
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
          <div class="tg-recent-title">
            <span>最近流水</span>
            <span class="tg-recent-count">
              {{ recent.length }}{{ hitsTotal ? ` / ${Math.min(hitsTotal, MAX_HITS)}` : '' }} 条
            </span>
          </div>
          <!-- 列表在卡片内滚动：宿主仪表盘网格可能给卡片固定高度，
               不限制高度时「加载更多」追加的行会被裁掉，看起来像没生效 -->
          <div class="tg-recent-list">
            <div v-for="item in recent" :key="hitKey(item)" class="tg-recent-row">
              <span class="tg-recent-media">{{ mediaName(item) }}</span>
              <span class="tg-recent-meta">{{ decisionLabel(item.decision) }} · {{ fmtTime(item.created_at) }}</span>
            </div>
          </div>
          <div class="tg-recent-actions">
            <VBtn
              v-if="canLoadMore"
              size="x-small"
              variant="text"
              color="primary"
              :loading="loadingMore"
              @click="loadMore"
            >
              加载更多
            </VBtn>
            <span v-else-if="recent.length >= MAX_HITS" class="tg-recent-hint">
              已显示最近 {{ MAX_HITS }} 条
            </span>
            <span class="tg-recent-hint">完整流水与关键词搜索在插件「资源监控」面板</span>
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
.tg-recent-title { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; font-size: 12px; opacity: 0.7; margin-bottom: 4px; }
.tg-recent-count { font-size: 11px; }
/* 列表区限高滚动：默认 5 条摘要一眼看完，加载更多后最多展示约 6 行，
   其余在卡片内滚动，「加载更多」按钮固定在滚动区外始终可见可点 */
.tg-recent-list { max-height: 132px; overflow-y: auto; overscroll-behavior: contain; }
.tg-recent-row { display: flex; align-items: center; gap: 8px; font-size: 12.5px; padding: 2px 0; }
.tg-recent-media { flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tg-recent-meta { flex: 0 0 auto; font-size: 11.5px; opacity: 0.7; }
.tg-recent-actions { display: flex; align-items: center; gap: 10px; margin-top: 6px; flex-wrap: wrap; }
.tg-recent-hint { font-size: 11px; opacity: 0.6; }
.tg-empty { padding: 12px; text-align: center; font-size: 12.5px; opacity: 0.65; }
</style>
