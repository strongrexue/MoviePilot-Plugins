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
/** 详情页视图：日历（默认）/ 发现流水。 */
const viewTab = ref('calendar')
/** 所选日期（默认今天，可查历史/未来）。 */
const calDate = ref('')

/** 日历数据（来自 GET /calendar?date=）。 */
const calendar = ref(null)
const calendarLoading = ref(false)

/** 拉今日日历。 */
async function loadCalendar() {
  calendarLoading.value = true
  try {
    const query = calDate.value ? `calendar?date=${calDate.value}` : 'calendar'
    const data = unwrap(await getPluginApi(props.api, props.pluginId, query))
    calendar.value = data
    // 后端会回填真实日期（空参数时等于今天）
    calDate.value = data?.today || calDate.value
  } catch (error) {
    calendar.value = { today: '', total: 0, updated: 0, pending: 0, items: [] }
  } finally {
    calendarLoading.value = false
  }
}

/** 回到今天。 */
function goToday() {
  calDate.value = ''
  loadCalendar()
}

/** 日历筛选：全部 / 今日已入库 / 待入库 / 洗版。 */
const calFilter = ref('')

/** 切换日历筛选（再点一次取消）。 */
function switchCalFilter(value) {
  calFilter.value = calFilter.value === value ? '' : value
}

/** 过滤后的日历条目。 */
const calendarItems = computed(() => {
  const items = calendar.value?.items || []
  if (!calFilter.value) return items
  return items.filter((item) => item.kind === calFilter.value)
})

/** 切换视图 tab。 */
function switchView(tab) {
  viewTab.value = tab
  if (tab === 'calendar' && !calendar.value) loadCalendar()
}

const history = ref({ items: [], total: 0, page: 1, count: 20 })
const filter = ref('')
const sourceFilter = ref('')
const keyword = ref('')

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
/**
 * 把数据库里的 poster 值归一化成 TMDB **图片路径**（`/abc.jpg`）。
 *
 * 宿主识别有时返回完整 URL（`https://image.tmdb.org/t/p/original/xxx.jpg`），
 * 存进流水后如果直接当 src 用，浏览器会去直连 image.tmdb.org ——
 * 国内网络下必然失败，表现为「只有少数卡片有图」。
 */
function posterPath(item) {
  const raw = item?.poster
  if (!raw) return ''
  const text = String(raw)
  const match = text.match(/\/t\/p\/[^/]+(\/.+)$/)
  if (match) return match[1]
  // 豆瓣 / Bangumi 等非 TMDB 海报是绝对 URL：原样交给后端代理
  if (/^https?:\/\//i.test(text)) return text
  return text.startsWith('/') ? text : ''
}

function posterUrl(item) {
  const path = posterPath(item)
  if (!path) return ''
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
    if (sourceFilter.value) params.set('source', sourceFilter.value)
    if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
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
  if (viewTab.value === 'calendar') loadCalendar()
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

/** 顶部状态 tab：只列出确实有数据的决策，按条数倒序。 */
const decisionTabs = computed(() => {
  const counts = history.value?.counts || {}
  return Object.entries(counts)
    .filter(([, value]) => Number(value) > 0)
    .map(([value, count]) => ({ value, count, label: decisionLabel(value) }))
    .sort((a, b) => b.count - a.count)
})

/** 切换状态筛选（tab）。 */
function switchFilter(value) {
  if (filter.value === value) return
  filter.value = value
  history.value.page = 1
  loadHistory()
}

/** 订阅卡片配色（写进宿主 UserCustomCSS，MP 订阅页跟着变色）。 */
const themeSaving = ref(false)
const theme = ref({
  colors: { subscribing: '#FFC107', pending: '#F97316', paused: '#9CA3AF' },
})

const themeRows = [
  { key: 'subscribing', label: '订阅中' },
  { key: 'pending', label: '待定' },
  { key: 'paused', label: '暂停' },
]

async function loadTheme() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'card_theme'))
    if (data) {
      theme.value = { colors: { ...theme.value.colors, ...(data.colors || {}) } }
    }
  } catch (error) {
    /* 配色读取失败不影响主功能 */
  }
}

async function saveTheme() {
  themeSaving.value = true
  try {
    unwrap(
      await postPluginApi(props.api, props.pluginId, 'card_theme/save', {
        colors: theme.value.colors,
      }),
    )
    setTip('配色已保存：刷新 MoviePilot 页面后生效')
  } catch (error) {
    setTip(error?.message || '配色保存失败', false)
  } finally {
    themeSaving.value = false
  }
}

async function resetTheme() {
  themeSaving.value = true
  try {
    unwrap(await postPluginApi(props.api, props.pluginId, 'card_theme/save', { reset: true }))
    setTip('已恢复默认：若颜色仍在，请重启 MoviePilot（设置服务有内存缓存）')
  } catch (error) {
    setTip(error?.message || '恢复默认失败', false)
  } finally {
    themeSaving.value = false
  }
}

/** 数据源显示名。 */
function sourceLabel(key) {
  const map = { tmdb: 'TMDB', anilist: 'AniList', douban_rss: '豆瓣榜单', hot_media: '热门媒体' }
  return map[key] || key
}


onMounted(async () => {
  await loadTheme()
})


/** 「按源」tab：TMDB / AniList / 豆瓣，带条数。 */
const sourceTabs = computed(() => {
  const counts = history.value?.source_counts || {}
  const labelOf = { tmdb: 'TMDB', anilist: 'AniList', douban_rss: '豆瓣', hot_media: '热门媒体' }
  return Object.entries(counts)
    .filter(([, value]) => Number(value) > 0)
    .map(([value, count]) => ({ value, count, label: labelOf[value] || value }))
    .sort((a, b) => b.count - a.count)
})

/** 切换数据源筛选。 */
/** 手动修正映射：输入 TMDB ID，写入映射缓存（下次运行必定命中）。 */
async function fixMapping(item) {
  const input = window.prompt(
    `手动指定「${item.title}」的 TMDB 条目 ID（从 TMDB 网址里取数字，如 /tv/12345）：`,
    item.media_id || '',
  )
  if (!input) return
  const id = String(input).trim().replace(/\D/g, '')
  if (!id) {
    setTip('请输入纯数字的 TMDB ID', false)
    return
  }
  try {
    const mediaType = item.media_type === 'movie' ? 'movie' : 'tv'
    unwrap(
      await postPluginApi(props.api, props.pluginId, 'mapping_cache/fix', {
        key: '',
        title: item.title,
        year: item.year || '',
        media_type: mediaType,
        media_source: 'themoviedb',
        media_id: id,
      }),
    )
    setTip(`已修正：${item.title} -> themoviedb/${id}（下次运行生效）`)
    await refreshAll()
  } catch (error) {
    setTip(error?.message || '修正失败', false)
  }
}

function searchKeyword() {
  history.value.page = 1
  loadHistory()
}

function switchSource(value) {
  if (sourceFilter.value === value) return
  sourceFilter.value = value
  history.value.page = 1
  loadHistory()
}

/** 海报加载失败：隐藏 <img>，露出底下的占位图标（否则浏览器会画出 alt 文本）。 */
function markPosterFailed(event) {
  const img = event?.target
  if (img) img.style.display = 'none'
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
  loadCalendar()
  refreshAll()
  refreshTimer = setInterval(refreshAll, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div class="sc-root" :class="{ 'sc-root-page': appPage }">
    <VAlert
      v-if="(status?.config_issues || []).length"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-3"
      :title="`已自动关闭 ${status.config_issues.length} 个不会产出内容的数据源`"
      :text="status.config_issues.join('；')"
    />
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
          <b>{{ sourceLabel(s.source) }}</b>
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

    <!-- 订阅卡片配色：写进宿主自定义 CSS，MP 订阅页卡片跟着变色 -->
    <div class="sc-theme-card">
      <div class="sc-theme-head">
        <VIcon icon="mdi-palette-outline" size="16" />
        <span class="sc-theme-title">订阅卡片配色</span>
        <span class="sc-dim">保存后刷新 MoviePilot 页面生效；只影响卡片外观，不改订阅</span>
      </div>
      <div class="sc-theme-body">
        <div class="sc-theme-row" v-for="row in themeRows" :key="row.key">
          <span class="sc-theme-label">{{ row.label }}</span>
          <input type="color" v-model="theme.colors[row.key]" class="sc-theme-color" />
          <code class="sc-dim">{{ theme.colors[row.key] }}</code>
        </div>
        <div class="sc-theme-actions">
          <VBtn size="x-small" color="primary" :loading="themeSaving" @click="saveTheme">保存</VBtn>
          <VBtn size="x-small" variant="text" :disabled="themeSaving" @click="resetTheme">
            恢复默认
          </VBtn>
        </div>
      </div>
    </div>

    <!-- 视图 tab：日历（默认）/ 发现流水 -->
    <div class="sc-maintabs">
      <button
        type="button"
        class="sc-maintab"
        :class="{ 'sc-maintab-active': viewTab === 'calendar' }"
        @click="switchView('calendar')"
      >
        <VIcon icon="mdi-calendar-month-outline" size="16" />
        日历
      </button>
      <button
        type="button"
        class="sc-maintab"
        :class="{ 'sc-maintab-active': viewTab === 'history' }"
        @click="switchView('history')"
      >
        <VIcon icon="mdi-history" size="16" />
        发现流水
      </button>
      <span class="sc-dim sc-maintabs-hint">可选日期 · 默认今天 · 与 MoviePilot 日历同源</span>
    </div>

    <!-- 今日日历（海报墙，板块内滚动） -->
    <div v-if="viewTab === 'calendar'" class="sc-card sc-cal-card">
      <div class="sc-cal-head">
        <div class="sc-cal-date-row">
          <span class="sc-dim">日期</span>
          <input
            v-model="calDate"
            type="date"
            class="sc-cal-date-input"
            @change="loadCalendar()"
          />
          <VBtn v-if="calendar?.today !== status?.today" size="x-small" variant="text" @click="goToday">
            今天
          </VBtn>
        </div>
        <div class="sc-cal-chips">
          <button
            type="button"
            class="sc-cal-chip"
            :class="{ 'sc-cal-chip-active': calFilter === '' }"
            @click="switchCalFilter('')"
          >
            全部 {{ calendar?.total || 0 }}
          </button>
          <button
            type="button"
            class="sc-cal-chip sc-cal-chip-ok"
            :class="{ 'sc-cal-chip-active': calFilter === 'updated' }"
            @click="switchCalFilter('updated')"
          >
            已入库 {{ calendar?.updated || 0 }}
          </button>
          <button
            type="button"
            class="sc-cal-chip sc-cal-chip-wait"
            :class="{ 'sc-cal-chip-active': calFilter === 'pending' }"
            @click="switchCalFilter('pending')"
          >
            待入库 {{ calendar?.pending || 0 }}
          </button>
        </div>
        <VBtn
          size="x-small"
          variant="text"
          class="sc-cal-refresh"
          :loading="calendarLoading"
          @click="loadCalendar"
        >
          刷新
        </VBtn>
      </div>

      <div v-if="!calendarItems.length" class="sc-cal-empty">
        <VIcon icon="mdi-calendar-blank-outline" size="34" />
        <div>{{ calFilter ? '当前筛选下没有条目' : '这一天没有需要处理的更新' }}</div>
        <div class="sc-dim">
          {{ calFilter ? '点上方「全部」看这一天的全部条目' : '换一个日期看看，或等订阅有新的播出/入库' }}
        </div>
      </div>

      <div v-else class="sc-cal-scroll">
        <div class="sc-cal-grid">
          <div
            v-for="item in calendarItems"
            :key="item.id + '-' + item.kind"
            class="sc-cal-item"
          >
            <div class="sc-cal-poster">
              <img
                v-if="item.poster"
                :src="posterUrl(item)"
                alt=""
                loading="lazy"
                @error="markPosterFailed($event)"
              />
              <VIcon v-else icon="mdi-filmstrip-box-multiple" size="26" class="sc-poster-ph" />
              <span
                class="sc-cal-badge"
                :class="item.kind === 'updated' ? 'sc-cal-badge-ok' : 'sc-cal-badge-wait'"
              >
                {{ item.kind === 'updated' ? '今日更新' : '今日待播' }}
              </span>
            </div>
            <div class="sc-cal-title" :title="item.name">{{ item.name }}</div>
            <div class="sc-cal-sub">
              <template v-if="(item.episodes || []).length">第 {{ item.episodes.join('、') }} 集</template>
              <template v-else>第 {{ item.start_episode + Math.max(item.total_episode - item.lack_episode - item.start_episode, 0) }} 集</template>
              <span v-if="item.air_time"> · {{ item.air_time }}</span>
            </div>
            <div class="sc-cal-meta">
              <span v-if="item.total_episode">
                {{ item.kind === 'updated' ? '已入库' : '未入库' }}
                ({{ item.total_episode - item.lack_episode }}/{{ item.total_episode }})
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 发现流水：表格式，一眼看全 -->
    <div v-if="viewTab === 'history'" class="sc-card">
      <div class="sc-card-head">
        <span class="sc-card-title">发现流水</span>
        <!-- 状态 tab：点一下即筛选，比下拉框少一步操作 -->

        <div class="sc-tabs sc-tabs-source">
          <span class="sc-tabs-label">数据源</span>
          <button
            type="button"
            class="sc-tab"
            :class="{ 'sc-tab-active': !sourceFilter }"
            @click="switchSource('')"
          >
            全部
          </button>
          <button
            v-for="tab in sourceTabs"
            :key="tab.value"
            type="button"
            class="sc-tab"
            :class="{ 'sc-tab-active': sourceFilter === tab.value }"
            @click="switchSource(tab.value)"
          >
            {{ tab.label }} <span class="sc-tab-count">{{ tab.count }}</span>
          </button>
        </div>
        <div class="sc-search">
          <VIcon icon="mdi-magnify" size="16" class="sc-dim" />
          <input
            v-model="keyword"
            class="sc-search-input"
            type="text"
            placeholder="搜索片名 / 原因（回车）"
            @keyup.enter="searchKeyword"
          />
          <VBtn
            v-if="keyword"
            size="x-small"
            variant="text"
            icon="mdi-close"
            @click="keyword = ''; searchKeyword()"
          />
        </div>
        <div class="sc-tabs">
          <button
            type="button"
            class="sc-tab"
            :class="{ 'sc-tab-active': !filter }"
            @click="switchFilter('')"
          >
            全部 <span class="sc-tab-count">{{ history.total || 0 }}</span>
          </button>
          <button
            v-for="tab in decisionTabs"
            :key="tab.value"
            type="button"
            class="sc-tab"
            :class="{ 'sc-tab-active': filter === tab.value }"
            @click="switchFilter(tab.value)"
          >
            {{ tab.label }} <span class="sc-tab-count">{{ tab.count }}</span>
          </button>
        </div>
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
            <img
              v-if="posterUrl(item)"
              :src="posterUrl(item)"
              alt=""
              loading="lazy"
              @error="markPosterFailed($event)"
            />
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
            <div class="sc-card-actions">
              <VBtn
                size="x-small"
                variant="text"
                prepend-icon="mdi-pencil-outline"
                @click="fixMapping(item)"
              >
                修正映射
              </VBtn>
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
  display: flex;
  flex-direction: column;
  gap: 10px;
}
/* 作为「发现」分区整页渲染时：撑满视口，让流水区吃掉剩余高度，
   避免页面下方一大片空白。 */
.sc-root-page {
  min-height: calc(100dvh - 150px);
}
/* 插件管理页的弹窗模式：同样固定高度 + 内部滚动，
   否则整页跟着滚、翻页按钮被推到屏幕外。 */
/* 插件详情上下文：内容超出视口时整块滚动。
   以前是 overflow: hidden + 只让最后一张卡片内部滚 —— 订阅总览搬进来后
   会被直接裁掉（真机：页面锁死、动都不动）。 */
.sc-root:not(.sc-root-page) {
  /* 插件详情容器自身是定高 + 裁剪的，这里必须撑满它并自己滚，
     否则内容被外层直接裁掉（真机：页面锁死、内部没法滚）。 */
  height: 100%;
  max-height: calc(100dvh - 160px);
  min-height: 0;
  overflow-y: auto;
}
.sc-root-page .sc-card:last-child {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.sc-root-page .sc-card:last-child .sc-grid {
  min-height: 0;
  overflow-y: auto;
  align-content: start;
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
/* 卡片尺寸对齐参考插件（maoyandianying：minmax(390px,1fr)，海报 8rem≈128px） */
.sc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 14px;
  align-content: stretch;
  grid-auto-rows: minmax(150px, 1fr);
}
.sc-card-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), 0.14);
  border-radius: 9px;
  background: rgba(var(--v-theme-surface), 0.35);
  min-width: 0;
}
.sc-card-poster {
  position: relative;
  flex: 0 0 128px;
  width: 128px;
  aspect-ratio: 2 / 3;
  height: auto;
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
  font-size: 15px;
  font-weight: 600;
  line-height: 1.35;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.sc-card-meta {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12.5px;
  opacity: 0.6;
}
.sc-card-reason {
  margin-top: 6px;
  font-size: 12px;
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
.sc-card-actions {
  margin-top: 4px;
  display: flex;
  justify-content: flex-end;
}
.sc-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.sc-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border: 1px solid rgba(var(--v-border-color), 0.18);
  border-radius: 999px;
  background: transparent;
  color: inherit;
  font-size: 12px;
  cursor: pointer;
  opacity: 0.75;
  transition: background 0.15s, opacity 0.15s;
}
.sc-tab:hover {
  background: rgba(var(--v-theme-primary), 0.08);
  opacity: 1;
}
.sc-tab-active {
  background: rgba(var(--v-theme-primary), 0.16);
  border-color: rgba(var(--v-theme-primary), 0.4);
  opacity: 1;
  font-weight: 600;
}
.sc-theme-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 12px;
}
.sc-theme-label {
  min-width: 52px;
}
.sc-theme-color {
  width: 34px;
  height: 22px;
  padding: 0;
  border: 1px solid rgba(var(--v-border-color), 0.3);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
}
.sc-theme-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
/* 固定列宽（而不是 1fr）：列宽恒定才能精确算「2 行」的高度，
   否则行高随窗口宽度变化，卡片会被切在中间。 */
/* 窄屏（手机）：一格 132px 时 20 张会排成十几行，固定 492px 的内部滚动
   在触屏上不好用，直接放开高度、跟随页面滚动。 */
@media (max-width: 900px) {
}

.sc-search {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border: 1px solid rgba(var(--v-border-color), 0.18);
  border-radius: 999px;
  min-width: 190px;
}
.sc-search-input {
  flex: 1 1 auto;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: inherit;
  font-size: 12px;
}
.sc-tabs-source {
  margin-bottom: 4px;
}
.sc-tabs-label {
  font-size: 11.5px;
  opacity: 0.55;
  align-self: center;
  margin-right: 2px;
}
.sc-tab-count {
  font-size: 11px;
  opacity: 0.7;
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

/* 订阅卡片配色卡片 */
.sc-theme-card {
  border: 1px solid rgba(var(--v-border-color), 0.2);
  border-radius: 10px;
  padding: 10px 12px;
  background: rgba(var(--v-border-color), 0.05);
}
.sc-theme-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.sc-theme-title {
  font-size: 13px;
  font-weight: 600;
}
.sc-theme-body {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
}
.sc-theme-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.sc-theme-label {
  min-width: 44px;
}
.sc-theme-color {
  width: 36px;
  height: 24px;
  padding: 0;
  border: 1px solid rgba(var(--v-border-color), 0.3);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
}
.sc-theme-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

/* 视图 tab（日历 / 发现流水） */
.sc-maintabs {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sc-maintab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid rgba(var(--v-border-color), 0.3);
  background: transparent;
  color: inherit;
  font-size: 13px;
  padding: 6px 16px;
  border-radius: 999px;
  cursor: pointer;
  opacity: 0.75;
}
.sc-maintab-active {
  background: rgb(var(--v-theme-primary));
  border-color: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  opacity: 1;
  font-weight: 600;
}
.sc-maintabs-hint {
  margin-left: auto;
  font-size: 11.5px;
}

/* 今日日历：摘要固定、海报墙内部滚动 */
.sc-cal-card {
  display: flex;
  flex-direction: column;
  min-height: 260px;
  max-height: calc(100dvh - 420px);
  overflow: hidden;
}
.sc-cal-head {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 0 0 auto;
  padding-bottom: 8px;
}
.sc-cal-date-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.sc-cal-date {
  font-size: 18px;
  font-weight: 700;
}
.sc-cal-refresh {
  margin-left: auto;
}
.sc-cal-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.sc-cal-chip {
  font-size: 11.5px;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid rgba(var(--v-border-color), 0.3);
  background: transparent;
  color: inherit;
  cursor: pointer;
  opacity: 0.8;
}
.sc-cal-chip:hover {
  opacity: 1;
}
.sc-cal-chip-active {
  background: rgba(var(--v-border-color), 0.22);
  border-color: rgb(var(--v-theme-primary));
  opacity: 1;
  font-weight: 600;
}
.sc-cal-chip-ok {
  color: rgb(var(--v-theme-success));
  border-color: rgba(var(--v-theme-success), 0.5);
}
.sc-cal-chip-wait {
  color: rgb(var(--v-theme-warning));
  border-color: rgba(var(--v-theme-warning), 0.5);
}
.sc-cal-chip-best {
  color: rgb(var(--v-theme-secondary));
}
.sc-cal-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
}
.sc-cal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 10px 8px;
  align-items: start;
}
.sc-cal-item {
  min-width: 0;
}
.sc-cal-poster {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  aspect-ratio: 2 / 3;
  background: rgba(var(--v-border-color), 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}
.sc-cal-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.sc-cal-badge {
  position: absolute;
  left: 4px;
  top: 4px;
  font-size: 10.5px;
  padding: 1px 6px;
  border-radius: 4px;
  color: #14141c;
  font-weight: 600;
}
.sc-cal-badge-ok {
  background: rgb(var(--v-theme-success));
}
.sc-cal-badge-wait {
  background: rgb(var(--v-theme-warning));
}
.sc-cal-title {
  font-size: 12.5px;
  font-weight: 600;
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sc-cal-sub {
  font-size: 11px;
  opacity: 0.7;
}
.sc-cal-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  opacity: 0.75;
}
.sc-cal-best {
  color: rgb(var(--v-theme-secondary));
}
.sc-cal-empty {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  opacity: 0.8;
  padding: 24px 0;
}

@media (max-width: 900px) {
  .sc-cal-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .sc-cal-card {
    max-height: calc(100dvh - 360px);
  }
  .sc-cal-head {
    flex-wrap: wrap;
    gap: 8px;
  }
  .sc-maintabs-hint {
    display: none;
  }
}

.sc-cal-date-input {
  background: transparent;
  border: 1px solid rgba(var(--v-border-color), 0.35);
  border-radius: 8px;
  color: inherit;
  font-size: 15px;
  font-weight: 700;
  padding: 3px 8px;
  color-scheme: dark;
}
.sc-cal-date-input:focus {
  outline: 2px solid rgb(var(--v-theme-primary));
}
</style>
