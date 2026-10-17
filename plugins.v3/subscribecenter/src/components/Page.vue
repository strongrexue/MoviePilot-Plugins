<script setup>
/**
 * 详情页（插件管理里的弹窗 / 侧栏整页共用）。
 *
 * 展示运行状态、各数据源情况、最近流水，并提供「立即运行一次」。
 * 与仪表盘共用 /status 与 /history 接口。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { FRONTEND_VERSION } from './version'
import { getPluginApi, postPluginApi, unwrap } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'SubscribeCenter' },
  // 作为 MP 左侧「发现」分区的整页入口渲染时置 true：整页没有"关闭"语义，隐藏关闭按钮。
  appPage: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'switch'])

const loading = ref(false)
const busy = ref('')
const tip = ref({ show: false, ok: true, text: '' })
const status = ref(null)
const history = ref({ items: [], total: 0, page: 1, count: 20 })
const filter = ref('')

let refreshTimer = null

const backendVersion = computed(() => String(status.value?.plugin_version || ''))
const versionMismatch = computed(() => {
  if (!backendVersion.value) return ''
  return backendVersion.value === FRONTEND_VERSION
    ? ''
    : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backendVersion.value}`
})

const DECISION_LABELS = {
  added: '新增订阅',
  skipped_dry_run: 'dry-run 跳过',
  skipped_first_run_dry: '首次试运行',
  skipped_already_subscribed: '已订阅',
  skipped_already_completed: '已完成过',
  skipped_duplicate: '跨源重复',
  skipped_rating: '评分不足',
  skipped_popularity: '关注度不足',
  skipped_out_of_window: '超出窗口',
  skipped_not_future: '定档已过',
  skipped_daily_limit: '触达上限',
  pending_review: '待确认',
  skipped_special: '特别篇（不处理）',
  skipped_finished: '已播完（跳过）',
  skipped_no_date: '无日期（跳过）',
  skipped_want: '想看不足（跳过）',
  skipped_source_disabled: '源未启用',
}

/**
 * 拼封面地址：**走插件后端代理**，不直连 image.tmdb.org。
 *
 * 原因：TMDB API 是服务器带代理访问的，但图片是浏览器直连 ——
 * 国内网络下 image.tmdb.org 常常连不上，封面会整片空白（真机反馈）。
 * 走 /poster 代理后浏览器只连 MoviePilot，图片由服务器绕代理取回。
 */
function posterUrl(item) {
  const path = item?.poster
  if (!path) return ''
  if (String(path).startsWith('http')) return String(path)
  const id = String(props.pluginId || 'SubscribeCenter')
  // 插件路由固定挂在 /api/v1/plugin/<id> 下；<img> 用绝对路径，与 axios 的 baseURL 无关。
  return `/api/v1/plugin/${id}/poster?path=${encodeURIComponent(path)}`
}

function decisionLabel(value) {
  return DECISION_LABELS[value] || value || '—'
}

function decisionColor(value) {
  if (value === 'added') return 'success'
  if (value === 'pending_review') return 'warning'
  if (String(value || '').startsWith('skipped')) return 'default'
  return 'default'
}

function setTip(text, ok = true) {
  tip.value = { show: true, ok, text }
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status'))
  } catch (error) {
    setTip(error?.message || '状态加载失败', false)
  }
}

async function loadHistory() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: String(history.value.page || 1),
      count: String(history.value.count || 20),
    })
    if (filter.value) params.set('decision', filter.value)
    history.value = unwrap(
      await getPluginApi(props.api, props.pluginId, `history?${params.toString()}`),
    )
  } catch (error) {
    setTip(error?.message || '流水加载失败', false)
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadStatus(), loadHistory()])
}

async function runOnce() {
  if (busy.value) return
  busy.value = 'run'
  try {
    const result = unwrap(
      await postPluginApi(props.api, props.pluginId, 'run_once', {}, { timeoutMs: 600000 }),
    )
    if (result?.skipped) {
      setTip('已有发现任务正在运行，本次跳过')
    } else {
      const s = result?.summary || {}
      setTip(
        `本次完成：拉取 ${s.fetched ?? 0} 条 / 新增 ${s.added ?? 0} 条 / `
          + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`,
      )
    }
    await refreshAll()
  } catch (error) {
    setTip(error?.message || '运行失败', false)
  } finally {
    busy.value = ''
  }
}

function prevPage() {
  if (history.value.page <= 1) return
  history.value.page -= 1
  loadHistory()
}

function nextPage() {
  const total = Number(history.value.total) || 0
  const count = Number(history.value.count) || 20
  if (history.value.page * count >= total) return
  history.value.page += 1
  loadHistory()
}

/** 上次运行的详细数字（通知里只报新增，细节放这里看）。 */
const lastSummary = computed(() => status.value?.last_summary || null)

/** 顶部统计卡：状态一览。 */
const statCards = computed(() => {
  const s = status.value || {}
  const summary = lastSummary.value || {}
  const sources = s.sources || []
  const enabledSources = sources.filter((row) => row.enabled)
  return [
    {
      icon: 'mdi-download-network-outline',
      label: '今日写入',
      value: `${s.written_today ?? 0}`,
      sub:
        s.daily_limit == null
          ? '上限未知'
          : Number(s.daily_limit) <= 0
            ? '不限条数'
            : `上限 ${s.daily_limit} 条`,
      color: 'primary',
    },
    {
      icon: 'mdi-radar',
      label: '数据源',
      value: `${enabledSources.length}/${sources.length}`,
      sub: s.enabled ? '插件已启用' : '插件未启用',
      color: s.enabled ? 'success' : 'warning',
    },
    {
      icon: 'mdi-plus-circle-outline',
      label: '上次新增',
      value: `${summary.added ?? 0}`,
      sub: summary.fetched != null ? `拉取 ${summary.fetched} 条` : '尚无运行记录',
      color: 'success',
    },
    {
      icon: 'mdi-clock-outline',
      label: '最近运行',
      value: s.last_run ? String(s.last_run).slice(11) : '—',
      sub: s.last_run ? String(s.last_run).slice(0, 10) : '从未运行',
      color: 'info',
    },
  ]
})

onMounted(() => {
  refreshAll()
  refreshTimer = setInterval(refreshAll, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div class="sc-root">
    <VAlert
      v-if="versionMismatch"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-3"
      :text="`${versionMismatch}：浏览器仍在用缓存的旧联邦组件。请按 Ctrl+Shift+R 硬刷新页面。`"
    />
    <VAlert
      v-if="tip.show"
      :type="tip.ok ? 'success' : 'error'"
      variant="tonal"
      density="compact"
      class="mb-3"
      closable
      :text="tip.text"
      @click:close="tip.show = false"
    />

    <!-- 顶部标题栏：标题在左、操作在右（对齐本仓库其他插件的详情页） -->
    <div class="sc-top">
      <div class="sc-top-left">
        <div class="sc-logo">
          <VIcon icon="mdi-movie-open-star-outline" size="20" />
        </div>
        <div class="sc-top-text">
          <div class="sc-title">
            胖虎订阅中心
            <VChip size="x-small" variant="flat" color="primary" class="ml-2">
              v{{ FRONTEND_VERSION }}
            </VChip>
          </div>
          <div class="sc-subtitle">发现片源 → 解析身份 → 去重 → 写订阅</div>
        </div>
      </div>
      <div class="sc-top-actions">
        <VBtn
          color="primary"
          size="small"
          variant="flat"
          prepend-icon="mdi-radar"
          :loading="busy === 'run'"
          @click="runOnce"
        >
          立即运行一次
        </VBtn>
        <VBtn size="small" variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="refreshAll">
          刷新
        </VBtn>
        <VBtn size="small" variant="text" prepend-icon="mdi-cog" @click="emit('switch')">设置</VBtn>
      </div>
    </div>

    <!-- 顶部统计卡：一屏看清状态 -->
    <div class="sc-stat-grid">
      <div v-for="card in statCards" :key="card.label" class="sc-stat">
        <div class="sc-stat-top">
          <VIcon :icon="card.icon" size="17" :color="card.color" />
          <span class="sc-stat-label">{{ card.label }}</span>
        </div>
        <div class="sc-stat-value">{{ card.value }}</div>
        <div class="sc-stat-sub">{{ card.sub }}</div>
      </div>
    </div>

    <!-- 数据源一览 -->
    <div class="sc-sources">
      <div v-for="s in (status?.sources || [])" :key="s.source" class="sc-source-chip">
        <div class="sc-source-head">
          <b>{{ s.source }}</b>
          <VChip size="x-small" variant="flat" :color="s.enabled ? 'success' : 'default'">
            {{ s.enabled ? '已启用' : '未启用' }}
          </VChip>
          <VChip v-if="!s.implemented" size="x-small" variant="flat" color="warning">
            未实现
          </VChip>
        </div>
        <div class="sc-source-sub">
          最近 {{ s.last_count }} 条 · {{ s.last_run || '从未运行' }}
        </div>
        <div v-if="s.last_error" class="sc-error">失败：{{ s.last_error }}</div>
      </div>
    </div>

    <!-- 发现流水：表格式，一眼看全 -->
    <div class="sc-card">
      <div class="sc-card-head">
        <span class="sc-card-title">发现流水</span>
        <VSelect
          v-model="filter"
          :items="[{ title: '全部状态', value: '' }, ...Object.entries(DECISION_LABELS).map(([value, title]) => ({ title, value }))]"
          density="compact"
          hide-details
          variant="outlined"
          style="max-width: 190px"
          @update:model-value="history.page = 1; loadHistory()"
        />
        <VChip size="x-small" variant="tonal">共 {{ history.total }} 部作品</VChip>
        <VChip size="x-small" variant="text">每部只显示最新状态</VChip>
      </div>

      <div v-if="!history.items.length" class="sc-empty">
        还没有流水。点「立即运行一次」即可看到发现结果。
      </div>

      <!-- 卡片网格：多列并排，像榜单页那样一眼扫过 -->
      <div v-else class="sc-grid">
        <div v-for="(item, index) in history.items" :key="index" class="sc-card-item">
          <div class="sc-card-poster">
            <img v-if="posterUrl(item)" :src="posterUrl(item)" :alt="item.title" loading="lazy" />
            <VIcon v-else icon="mdi-filmstrip-box-multiple" size="30" class="sc-poster-ph" />
            <span class="sc-card-badge">
              <VChip size="x-small" variant="flat" :color="decisionColor(item.decision)">
                {{ decisionLabel(item.decision) }}
              </VChip>
            </span>
          </div>
          <div class="sc-card-body">
            <div class="sc-card-title" :title="item.title">
              <b>{{ item.title }}</b>
            </div>
            <div class="sc-card-meta">
              <span v-if="item.year">{{ item.year }}</span>
              <span v-if="item.media_type">{{ item.media_type }}</span>
              <span>{{ item.source }}</span>
              <span v-if="item.confidence">{{ item.confidence }}</span>
            </div>
            <div v-if="item.release_date" class="sc-card-meta">
              放送 {{ item.release_date }}
            </div>
            <div v-if="item.reason" class="sc-card-reason" :title="item.reason">
              {{ item.reason }}
            </div>
          </div>
        </div>
      </div>

      <div v-if="history.total > history.count" class="sc-pager">
        <VBtn size="small" variant="text" :disabled="history.page <= 1" @click="prevPage">上一页</VBtn>
        <span class="sc-hint">第 {{ history.page }} 页 · 共 {{ history.total }} 部作品</span>
        <VBtn
          size="small"
          variant="text"
          :disabled="history.page * history.count >= history.total"
          @click="nextPage"
        >
          下一页
        </VBtn>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sc-root {
  padding: 4px;
  font-size: 13px;
}
.sc-hint {
  font-size: 12px;
  opacity: 0.7;
}
.sc-error {
  font-size: 12px;
  color: rgb(var(--v-theme-error));
  margin-top: 4px;
}
.sc-dim {
  opacity: 0.65;
  font-size: 12px;
}
.sc-mono {
  font-variant-numeric: tabular-nums;
  font-size: 12px;
  opacity: 0.8;
}

/* 顶部标题栏 */
.sc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 12px;
  margin-bottom: 10px;
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 10px;
  background: rgba(var(--v-theme-surface), 0.45);
}
.sc-top-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.sc-logo {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 9px;
  color: rgb(var(--v-theme-on-primary));
  background: rgb(var(--v-theme-primary));
}
.sc-top-text {
  min-width: 0;
}
.sc-title {
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.3;
}
.sc-subtitle {
  font-size: 12px;
  opacity: 0.62;
  line-height: 1.4;
}
.sc-top-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

/* 顶部统计卡 */
.sc-stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}
.sc-stat {
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 10px;
  background: rgba(var(--v-theme-surface), 0.4);
}
.sc-stat-top {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  opacity: 0.75;
}
.sc-stat-value {
  margin-top: 3px;
  font-size: 21px;
  font-weight: 700;
  line-height: 1.2;
}
.sc-stat-sub {
  margin-top: 2px;
  font-size: 11px;
  opacity: 0.6;
}

/* 数据源一览 */
.sc-sources {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 8px;
  margin-top: 10px;
}
.sc-source-chip {
  padding: 8px 10px;
  border: 1px solid rgba(var(--v-border-color), 0.14);
  border-radius: 8px;
}
.sc-source-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
}
.sc-source-sub {
  margin-top: 2px;
  font-size: 11px;
  opacity: 0.6;
}

/* 卡片 */
.sc-card {
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 10px;
}
.sc-card-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.sc-card-title {
  font-size: 13px;
  font-weight: 600;
}
.sc-empty {
  padding: 20px 4px;
  font-size: 12px;
  text-align: center;
  opacity: 0.6;
}

/* 流水表格 */
/* 卡片网格：多列并排（对齐榜单页的观感） */
.sc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(258px, 1fr));
  gap: 12px;
}
.sc-card-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  border: 1px solid rgba(var(--v-border-color), 0.14);
  border-radius: 9px;
  background: rgba(var(--v-theme-surface), 0.35);
  min-width: 0;
}
.sc-card-poster {
  position: relative;
  flex: 0 0 88px;
  width: 88px;
  height: 126px;
  border-radius: 7px;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: rgba(var(--v-theme-on-surface), 0.08);
}
.sc-card-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.sc-card-badge {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  transform: scale(0.82);
  transform-origin: bottom center;
}
.sc-card-body {
  min-width: 0;
  flex: 1 1 auto;
}
.sc-card-title {
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.35;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.sc-card-meta {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 11.5px;
  opacity: 0.6;
}
.sc-card-reason {
  margin-top: 5px;
  font-size: 11.5px;
  line-height: 1.4;
  opacity: 0.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.sc-reason {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sc-poster {
  display: grid;
  place-items: center;
  width: 40px;
  height: 56px;
  border-radius: 6px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.08);
}
.sc-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.sc-poster-ph {
  opacity: 0.45;
}
.sc-media-title {
  display: flex;
  align-items: baseline;
  gap: 5px;
  flex-wrap: wrap;
}
.sc-media-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 2px;
}
/* 说明单独成列：两行截断 + 悬浮看全文，避免长句把行高撑起来 */
.sc-reason {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 11.5px;
  line-height: 1.45;
  max-height: 2.9em;
}
.sc-decision {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.sc-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 8px;
}

@media (max-width: 900px) {
  .sc-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  }
}
</style>
