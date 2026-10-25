<script setup>
/**
 * 详情页（插件管理里的弹窗 / 侧栏整页共用）。
 *
 * 展示运行状态、各数据源情况、最近流水，并提供「立即运行一次」。
 * 与仪表盘共用 /status 与 /history 接口。
 */
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
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
/** 正在清空发现流水 */
const clearing = ref(false)
//: 正在手动补订阅的那条流水键（同一时间只允许一条，避免重复点）
const subscribing = ref('')
const tip = ref({ show: false, ok: true, text: '' })
const status = ref(null)
/** 详情页视图：日历（默认）/ 发现流水。 */
const viewTab = ref('calendar')
/** 日历模式：today（默认，今天列表）/ month（整月网格）。 */
const calMode = ref('today')
/** 今天视图数据（GET /calendar/day）。 */
const todayDate = ref('')
const todayView = ref(null)
const todayLoading = ref(false)

/** 今天视图的筛选：'' / updated / pending。 */
const todayFilter = ref('')

/** 切换今天视图筛选。 */
function switchTodayFilter(value) {
  todayFilter.value = todayFilter.value === value ? '' : value
}

/** 筛选后的今天条目。 */
const todayItems = computed(() => {
  const items = todayView.value?.items || []
  if (!todayFilter.value) return items
  return items.filter((item) => item.kind === todayFilter.value)
})

/** 拉某天的列表（留空=今天）。 */
async function loadToday() {
  todayLoading.value = true
  try {
    const query = todayDate.value ? `calendar/day?date=${todayDate.value}` : 'calendar/day'
    const data = unwrap(await getPluginApi(props.api, props.pluginId, query))
    todayView.value = data
    todayDate.value = data?.today || todayDate.value
  } catch (error) {
    todayView.value = { today: '', total: 0, updated: 0, pending: 0, items: [] }
    setTip(error?.message || '读取今天日历失败', false)
  } finally {
    todayLoading.value = false
  }
}

/** 回到今天。 */
function goToday() {
  todayDate.value = ''
  loadToday()
}

/** 切换 今天 / 月历。 */
function switchCalMode(mode) {
  calMode.value = mode
  if (mode === 'today' && !todayView.value) loadToday()
  if (mode === 'month' && !calendar.value) loadCalendar()
}

/** 当前月份（YYYY-MM，默认本月）。 */
const calMonth = ref('')
/** 某天展开全部条目（key = YYYY-MM-DD）。 */
const expandedDays = ref({})
/** 整月日历数据（GET /calendar?month=）。 */
const calendar = ref(null)
const calendarLoading = ref(false)

/** 拉整月日历。 */
async function loadCalendar() {
  calendarLoading.value = true
  try {
    const query = `calendar?month=${calMonth.value || ''}`
    const data = unwrap(await getPluginApi(props.api, props.pluginId, query))
    calendar.value = data
    calMonth.value = data?.month || calMonth.value
  } catch (error) {
    calendar.value = { month: '', days: {}, total: 0, per_day_limit: 5 }
    setTip(error?.message || '读取日历失败', false)
    // 默认定位到今天（图 4 那种「一进来就看到今天」的体验）
    await nextTick()
    const today = document?.getElementById?.('sc-cal-today')
    if (today && typeof today.scrollIntoView === 'function') {
      today.scrollIntoView({ block: 'center' })
    }
  } finally {
    calendarLoading.value = false
  }
}

/** 上/下个月。 */
function shiftMonth(delta) {
  const text = calMonth.value || new Date().toISOString().slice(0, 7)
  const [year, month] = text.split('-').map(Number)
  const base = new Date(year, month - 1 + delta, 1)
  calMonth.value = `${base.getFullYear()}-${String(base.getMonth() + 1).padStart(2, '0')}`
  loadCalendar()
}

/** 月份标题：2026年10月。 */
const calMonthTitle = computed(() => {
  const text = calMonth.value || ''
  if (!/^\d{4}-\d{2}$/.test(text)) return '—'
  const [year, month] = text.split('-')
  return `${year}年${Number(month)}月`
})

/** 今天的 YYYY-MM-DD：优先用服务器返回的（避免浏览器 UTC 偏一天）。 */
const todayText = computed(
  () => calendar.value?.today || status.value?.today || new Date().toISOString().slice(0, 10),
)

/** 月历格子：周一开头，补齐前后空白。 */
const calWeeks = computed(() => {
  const text = calMonth.value
  if (!/^\d{4}-\d{2}$/.test(text || '')) return []
  const [year, month] = text.split('-').map(Number)
  const first = new Date(year, month - 1, 1)
  const daysInMonth = new Date(year, month, 0).getDate()
  const lead = (first.getDay() + 6) % 7 // 周一=0
  const cells = []
  for (let i = 0; i < lead; i += 1) cells.push({ empty: true, key: `lead-${i}` })
  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = `${text}-${String(day).padStart(2, '0')}`
    cells.push({
      day,
      date,
      key: date,
      items: calendar.value?.days?.[date] || [],
    })
  }
  while (cells.length % 7 !== 0) cells.push({ empty: true, key: `tail-${cells.length}` })
  const weeks = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
  return weeks
})

/** 切到本月。 */
function goThisMonth() {
  calMonth.value = ''
  loadCalendar()
}

/** 展开/收起某天。 */
function toggleDay(date) {
  expandedDays.value = { ...expandedDays.value, [date]: !expandedDays.value[date] }
}

/** 每格默认展示的条数。 */
const perDayLimit = computed(() => calendar.value?.per_day_limit || 5)

/** 某一格应该显示的条目。 */
function dayItems(cell) {
  const items = cell?.items || []
  if (expandedDays.value[cell.date]) return items
  return items.slice(0, perDayLimit.value)
}

/** 某一格还有多少条被折叠。 */
function hiddenCount(cell) {
  const items = cell?.items || []
  if (expandedDays.value[cell.date]) return 0
  return Math.max(items.length - perDayLimit.value, 0)
}

/** 条目上的「第 N 集」文案。 */
function episodeText(item) {
  const eps = item?.episodes || []
  if (eps.length) return `第 ${eps.join('、')} 集`
  const start = Number(item?.start_episode || 1)
  const done = Number(item?.total_episode || 0) - Number(item?.lack_episode || 0)
  return `第 ${Math.max(start, done || start)} 集`
}

/** 电影发行基准日类型 -> 中文（与后端 RELEASE_KIND_LABELS 逐字对应）。 */
const RELEASE_KIND_LABELS = {
  digital: '数字发行',
  physical: '实体发行',
  theatrical: '影院上映',
  premiere: '首映',
  tv: '电视首播',
  general: '上映',
}

/** 电影条目：哪一种发行日（普通=数字、洗版=实体）。 */
function releaseKindText(kind) {
  return RELEASE_KIND_LABELS[kind] || '上映'
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
  skipped_recorded: '流水已记录（不再自动订）',
  skipped_blacklist: '命中排除规则',
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

/** 清空发现流水。
 *
 * 这是「流水记过就不再自动重订」的解锁方式：清空之后，之前订过又被删掉的
 * 订阅会在下一轮重新被发现。所以必须二次确认，且把后果写清。
 */
async function clearHistory() {
  if (!window.confirm(
    '清空发现流水？\n\n' +
    '清空后，之前订阅过（后来被你删掉）的作品会重新被自动订阅。',
  )) return
  clearing.value = true
  try {
    const result = unwrap(await postPluginApi(props.api, props.pluginId, 'history/clear', {}))
    setTip(`已清空 ${result?.removed ?? 0} 条流水`)
    history.value.page = 1
    await loadHistory()
    await loadStatus()
  } catch (error) {
    setTip(error?.message || '清空流水失败', false)
  } finally {
    clearing.value = false
  }
}

/**
 * 拼宿主详情页地址（新标签打开）。
 *
 * 宿主前端用 hash 路由：`#/media?media_source=…&media_id=…&type=…&title=…&year=…`。
 * `media_source` 必须是宿主的枚举值（`themoviedb` / `douban` / …），`type` 是**中文**
 * 的媒体类型（`电视剧` / `电影`）—— 这两点错了详情页会打不开或认错媒体。
 */
function detailUrl(item) {
  const mediaSource = String(item?.media_source || '')
  const mediaId = String(item?.media_id || '')
  if (!mediaSource || !mediaId) return ''
  const params = new URLSearchParams()
  params.set('media_source', mediaSource)
  params.set('media_id', mediaId)
  params.set('type', String(item?.media_type || '') === 'tv' ? '电视剧' : '电影')
  if (item?.title) params.set('title', String(item.title))
  if (item?.year) params.set('year', String(item.year))
  // 去掉当前 hash，避免拼成 `#/subscribe#/media?...`
  const base = window.location.href.split('#')[0]
  return `${base}#/media?${params.toString()}`
}

function openDetail(item) {
  const url = detailUrl(item)
  if (!url) return
  window.open(url, '_blank', 'noopener')
}

/** 只有拿到了确定性身份（来源 + ID）的流水才能一键订阅。 */
function canSubscribe(item) {
  return Boolean(item?.key) && Boolean(item?.media_source) && Boolean(item?.media_id)
}

/** 「已订阅过」的给「重新订阅」，其余给「加入订阅」。 */
function subscribeLabel(item) {
  const decision = String(item?.decision || '')
  return decision === 'added' || decision === 'skipped_already_subscribed'
    ? '重新订阅'
    : '加入订阅'
}

/**
 * 从流水手动补订阅。
 *
 * 后端刻意绕开窗口/评分/日限额/流水去重 —— 用户点名要订的东西不该被门槛拦住。
 * 订阅已存在时不改状态，只回报宿主里的当前状态。
 */
async function subscribeFromHistory(item) {
  const key = String(item?.key || '')
  if (!key || subscribing.value) return
  if (!canSubscribe(item)) {
    setTip('这条流水没有确定性身份，无法直接订阅', false)
    return
  }
  subscribing.value = key
  try {
    const result = unwrap(
      await postPluginApi(
        props.api,
        props.pluginId,
        'history/subscribe',
        { key },
        { timeoutMs: 120000 },
      ),
    )
    if (result?.action === 'added') {
      setTip(result?.message || '已加入订阅')
      await loadHistory()
      await loadStatus()
    } else {
      // 「订阅中」不是错误，用普通提示，别刷红
      setTip(result?.message || '没有写入订阅', true)
    }
  } catch (error) {
    setTip(error?.message || '订阅失败', false)
  } finally {
    subscribing.value = ''
  }
}

async function refreshAll() {
  if (viewTab.value === 'calendar' && calMode.value === 'today') loadToday()
  await Promise.all([loadStatus(), loadHistory()])
}

async function runOnce() {
  if (busy.value) return
  busy.value = 'run'
  try {
    const start = unwrap(
      await postPluginApi(props.api, props.pluginId, 'run_once', {}, { timeoutMs: 60000 }),
    )
    if (!start?.started) {
      setTip(start?.message || '已有发现任务正在运行，本次跳过')
      return
    }
    setTip('已在后台开始执行，正在等结果（可能要一两分钟）…')
    // 整条流水线跑得比网关超时久，只能轮询结果（真机 502 的修法）
    let state = null
    for (let i = 0; i < 450; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 4000))
      state = unwrap(
        await getPluginApi(props.api, props.pluginId, 'run_once/result', { timeoutMs: 60000 }),
      )
      if (state?.error) throw new Error(state.error)
      if (!state?.running) break
    }
    const s = state?.result?.summary || {}
    setTip(
      `本次完成：拉取 ${s.fetched ?? 0} 条 / 新增 ${s.added ?? 0} 条 / `
        + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`,
    )
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
  loadToday()
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

    <!-- 日历（复刻 MoviePilot 日历：月历网格 + 每天条目） -->
    <div v-if="viewTab === 'calendar'" class="sc-card sc-cal-card">
      <div class="sc-cal-head">
        <button
          type="button"
          class="sc-calmode"
          :class="{ 'sc-calmode-active': calMode === 'today' }"
          @click="switchCalMode('today')"
        >
          今天
        </button>
        <button
          type="button"
          class="sc-calmode"
          :class="{ 'sc-calmode-active': calMode === 'month' }"
          @click="switchCalMode('month')"
        >
          月历
        </button>
        <template v-if="calMode === 'today'">
          <input v-model="todayDate" type="date" class="sc-cal-date-input" @change="loadToday()" />
          <VBtn v-if="todayView?.today !== status?.today" size="x-small" variant="text" @click="goToday">
            今天
          </VBtn>
          <button
            type="button"
            class="sc-calmode"
            :class="{ 'sc-calmode-active': todayFilter === '' }"
            @click="switchTodayFilter('')"
          >
            全部 {{ todayView?.total || 0 }}
          </button>
          <button
            type="button"
            class="sc-calmode"
            :class="{ 'sc-calmode-active': todayFilter === 'updated' }"
            @click="switchTodayFilter('updated')"
          >
            已入库 {{ todayView?.updated || 0 }}
          </button>
          <button
            type="button"
            class="sc-calmode"
            :class="{ 'sc-calmode-active': todayFilter === 'pending' }"
            @click="switchTodayFilter('pending')"
          >
            待入库 {{ todayView?.pending || 0 }}
          </button>
          <VBtn size="x-small" variant="text" class="sc-cal-refresh" :loading="todayLoading" @click="loadToday">
            刷新
          </VBtn>
        </template>
        <template v-else>
        <VBtn size="x-small" variant="text" icon="mdi-chevron-left" @click="shiftMonth(-1)" />
        <span class="sc-cal-month">{{ calMonthTitle }}</span>
        <VBtn size="x-small" variant="text" icon="mdi-chevron-right" @click="shiftMonth(1)" />
        <VBtn size="x-small" variant="text" @click="goThisMonth">本月</VBtn>
        <span class="sc-dim sc-cal-total">本月 {{ calendar?.total || 0 }} 条</span>
        <VBtn size="x-small" variant="text" class="sc-cal-refresh" :loading="calendarLoading" @click="loadCalendar">
          刷新
        </VBtn>
        </template>
      </div>

      <!-- 今天：海报墙（默认视图） -->
      <div v-if="calMode === 'today'" class="sc-today-scroll">
        <div v-if="!todayItems.length" class="sc-cal-empty">
          <VIcon icon="mdi-calendar-blank-outline" size="34" />
          <div>{{ todayFilter ? '当前筛选下没有条目' : '这一天没有需要处理的更新' }}</div>
          <div class="sc-dim">切到「月历」可以看整月安排</div>
        </div>
        <div v-else class="sc-today-grid">
          <div v-for="item in todayItems" :key="item.id + '-' + item.kind" class="sc-today-item">
            <div class="sc-today-poster">
              <img v-if="item.poster" :src="posterUrl(item)" alt="" loading="lazy" @error="markPosterFailed($event)" />
              <VIcon v-else icon="mdi-filmstrip-box-multiple" size="22" />
              <span class="sc-today-badge" :class="item.kind === 'updated' ? 'sc-today-badge-ok' : 'sc-today-badge-wait'">
                {{ item.kind === 'updated' ? '今日更新' : '今日待播' }}
              </span>
            </div>
            <div class="sc-today-title" :title="item.name">{{ item.name }}</div>
            <div class="sc-today-sub">{{ episodeText(item) }}</div>
            <div class="sc-today-sub" :class="item.kind === 'updated' ? 'sc-cal-done' : 'sc-cal-wait'">
              {{ item.kind === 'updated' ? '已入库' : '未入库' }}
              ({{ item.total_episode - item.lack_episode }}/{{ item.total_episode }})
            </div>
            <div v-if="item.release_kind" class="sc-today-sub sc-dim">
              {{ releaseKindText(item.release_kind) }}
            </div>
            <div
              v-if="item.searched === true"
              class="sc-today-sub sc-cal-done"
              title="按自动启停的判定，今天会被订阅刷新搜到"
            >
              <VIcon icon="mdi-radar" size="11" /> 今天会搜
            </div>
            <div
              v-else-if="item.searched === false"
              class="sc-today-sub sc-cal-wait"
              :title="item.search_note || '按自动启停的判定，今天不会被搜'"
            >
              <VIcon icon="mdi-pause-circle-outline" size="11" /> 今天不搜<span v-if="item.search_note">（{{ item.search_note }}）</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="calMode === 'month'" class="sc-cal-weekhead">
        <span v-for="w in ['周一', '周二', '周三', '周四', '周五', '周六', '周日']" :key="w">{{ w }}</span>
      </div>

      <div v-if="calMode === 'month'" class="sc-cal-scroll">
        <div v-for="(week, wi) in calWeeks" :key="wi" class="sc-cal-week">
          <div
            v-for="cell in week"
            :key="cell.key"
            :id="cell.date === todayText ? 'sc-cal-today' : undefined"
            class="sc-cal-day"
            :class="{
              'sc-cal-day-empty': cell.empty,
              'sc-cal-day-today': cell.date === todayText,
            }"
          >
            <template v-if="!cell.empty">
              <div class="sc-cal-daynum">{{ cell.day }}</div>
              <div
                v-for="item in dayItems(cell)"
                :key="cell.date + '-' + item.id + '-' + item.kind"
                class="sc-cal-ev"
              >
                <div class="sc-cal-evposter">
                  <img
                    v-if="item.poster"
                    :src="posterUrl(item)"
                    alt=""
                    loading="lazy"
                    @error="markPosterFailed($event)"
                  />
                  <VIcon v-else icon="mdi-filmstrip-box-multiple" size="16" />
                </div>
                <div class="sc-cal-evbody">
                  <div class="sc-cal-evtitle" :title="item.name">{{ item.name }}</div>
                  <div class="sc-cal-evline">
                    <VIcon icon="mdi-card-text-outline" size="11" />{{ episodeText(item) }}
                  </div>
                  <div class="sc-cal-evline" :class="item.kind === 'updated' ? 'sc-cal-done' : 'sc-cal-wait'">
                    <VIcon :icon="item.kind === 'updated' ? 'mdi-check' : 'mdi-close'" size="11" />
                    {{ item.kind === 'updated' ? '已入库' : '未入库' }}
                    ({{ item.total_episode - item.lack_episode }}/{{ item.total_episode }})
                  </div>
                  <div class="sc-cal-evline sc-cal-time">
                    <VIcon icon="mdi-clock-outline" size="11" />{{ item.air_time || item.air_date }}
                  </div>
                </div>
              </div>
              <button
                v-if="hiddenCount(cell)"
                type="button"
                class="sc-cal-more"
                @click="toggleDay(cell.date)"
              >
                <VIcon icon="mdi-unfold-more-horizontal" size="12" /> +{{ hiddenCount(cell) }}
              </button>
              <button
                v-else-if="expandedDays[cell.date]"
                type="button"
                class="sc-cal-more"
                @click="toggleDay(cell.date)"
              >
                <VIcon icon="mdi-unfold-less-horizontal" size="12" /> 收起
              </button>
            </template>
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
        <VBtn
          size="x-small"
          variant="text"
          color="warning"
          prepend-icon="mdi-delete-sweep-outline"
          :loading="clearing"
          :disabled="clearing || loading || !history.total"
          @click="clearHistory"
        >
          清空流水
        </VBtn>
      </div>

      <div v-if="!history.items.length" class="sc-empty">
        还没有流水。点「立即运行一次」即可看到发现结果。
      </div>

      <!-- 卡片网格：多列并排，像榜单页那样一眼扫过 -->
      <div v-else class="sc-grid">
        <div v-for="(item, index) in history.items" :key="index" class="sc-card-item">
          <div
            class="sc-card-poster"
            :class="{ 'sc-poster-link': Boolean(detailUrl(item)) }"
            :title="detailUrl(item) ? '在宿主里打开详情页' : ''"
            @click="openDetail(item)"
          >
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
                v-if="canSubscribe(item)"
                size="x-small"
                variant="text"
                :loading="subscribing === item.key"
                :disabled="Boolean(subscribing)"
                prepend-icon="mdi-plus-circle-outline"
                @click="subscribeFromHistory(item)"
              >
                {{ subscribeLabel(item) }}
              </VBtn>
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
/* 有确定性身份的海报可以点开宿主详情页 */
.sc-poster-link {
  cursor: pointer;
}
.sc-poster-link:hover img {
  opacity: 0.86;
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

/* 日历：月历网格（复刻 MoviePilot 日历页） */
.sc-cal-card {
  display: flex;
  flex-direction: column;
  min-height: 320px;
  max-height: calc(100dvh - 420px);
  overflow: hidden;
}
.sc-cal-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  padding-bottom: 6px;
}
.sc-cal-month {
  font-size: 17px;
  font-weight: 700;
}
.sc-cal-total {
  font-size: 11.5px;
}
.sc-cal-refresh {
  margin-left: auto;
}
.sc-cal-weekhead {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
  flex: 0 0 auto;
  padding: 2px 0 4px;
  font-size: 11.5px;
  text-align: center;
  opacity: 0.7;
}
.sc-cal-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
}
.sc-cal-week {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
  margin-bottom: 4px;
}
.sc-cal-day {
  min-height: 92px;
  height: fit-content;
  border: 1px solid rgba(var(--v-border-color), 0.18);
  border-radius: 8px;
  padding: 4px 4px 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: rgba(var(--v-border-color), 0.05);
}
.sc-cal-day-empty {
  border: none;
  background: transparent;
}
.sc-cal-day-today {
  border-color: rgb(var(--v-theme-primary));
  box-shadow: inset 0 0 0 1px rgb(var(--v-theme-primary));
}
.sc-cal-daynum {
  font-size: 11.5px;
  opacity: 0.75;
  text-align: right;
}
.sc-cal-ev {
  display: flex;
  gap: 4px;
  align-items: flex-start;
}
.sc-cal-evposter {
  width: 30px;
  height: 42px;
  border-radius: 4px;
  overflow: hidden;
  flex: 0 0 auto;
  background: rgba(var(--v-border-color), 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}
.sc-cal-evposter img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.sc-cal-evbody {
  min-width: 0;
  flex: 1 1 auto;
}
.sc-cal-evtitle {
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.25;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.sc-cal-evline {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 10.5px;
  opacity: 0.8;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
}
.sc-cal-done {
  color: rgb(var(--v-theme-success));
  opacity: 1;
}
.sc-cal-wait {
  color: rgb(var(--v-theme-warning));
  opacity: 1;
}
.sc-cal-time {
  opacity: 0.6;
}
.sc-cal-more {
  border: 1px dashed rgba(var(--v-theme-primary), 0.6);
  background: transparent;
  color: rgb(var(--v-theme-primary));
  border-radius: 6px;
  font-size: 10.5px;
  padding: 2px 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}
@media (max-width: 900px) {
  .sc-cal-card {
    max-height: calc(100dvh - 340px);
  }
  .sc-cal-day {
    min-height: 72px;
  }
  .sc-cal-evposter {
    display: none;
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

/* 今天 / 月历 模式切换 */
.sc-calmode {
  border: 1px solid rgba(var(--v-border-color), 0.3);
  background: transparent;
  color: inherit;
  font-size: 12.5px;
  padding: 3px 12px;
  border-radius: 999px;
  cursor: pointer;
  opacity: 0.75;
}
.sc-calmode-active {
  background: rgb(var(--v-theme-primary));
  border-color: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  opacity: 1;
  font-weight: 600;
}
/* 今天的海报墙 */
.sc-today-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
}
.sc-today-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 10px 8px;
  align-items: start;
}
.sc-today-item {
  min-width: 0;
}
.sc-today-poster {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  aspect-ratio: 2 / 3;
  background: rgba(var(--v-border-color), 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}
.sc-today-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.sc-today-badge {
  position: absolute;
  left: 4px;
  top: 4px;
  font-size: 10.5px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
  color: #14141c;
}
.sc-today-badge-ok {
  background: rgb(var(--v-theme-success));
}
.sc-today-badge-wait {
  background: rgb(var(--v-theme-warning));
}
.sc-today-title {
  font-size: 12.5px;
  font-weight: 600;
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sc-today-sub {
  font-size: 11px;
  opacity: 0.75;
}
</style>
