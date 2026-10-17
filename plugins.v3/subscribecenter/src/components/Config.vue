<script setup>
/**
 * 配置页。
 *
 * 设计要点：
 * - 表单值与后端 `default_config()` 键集合严格一致（宿主的保存是**整份覆盖**，
 *   少一个键就会被静默清掉）；
 * - 保存走两条路：emit('save') 交给宿主编排，同时自己 PUT 一次兜底 ——
 *   宿主在不同挂载方式下对 save 事件的处理不一致（参考 embycovercenter 的结论），
 *   自持保存能保证「点了保存就一定落库」；
 * - 顶部显示前端/后端版本号，不一致时明确提示硬刷新（remoteEntry.js 无哈希）。
 *
 * 版面（0.9.0 重做）：
 * - 左侧分区导航 + 右侧卡片内容 + 底部吸底操作栏；
 * - 首屏「总览」用数据卡呈现关键状态，不必滚到底就看清；
 * - 每个开关一行（标题/说明在左、开关在右），避免一长串灰色文字堆叠。
 */
import { computed, onMounted, ref } from 'vue'
import { FRONTEND_VERSION } from './version'
import { defaultConfig } from './configDefaults'
import {
  getPluginApi,
  getPluginConfig,
  postPluginApi,
  savePluginConfig,
  unwrap,
} from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'SubscribeCenter' },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close'])

const form = ref(defaultConfig())
const loading = ref(false)
const busy = ref('')
const status = ref(null)
const tip = ref({ show: false, ok: true, text: '' })
const previewItems = ref([])
const activeSection = ref('overview')

/** 决策常量 -> 中文标签（与后端 core/constants.py 逐字对应）。 */
const DECISION_LABELS = {
  added: '新增',
  skipped_dry_run: 'dry-run',
  pending_review: '待确认',
  skipped_special: '特别篇',
  skipped_finished: '已播完',
  skipped_no_date: '无日期',
  skipped_want: '想看不足',
  skipped_rating: '评分不足',
  skipped_popularity: '关注度不足',
  skipped_out_of_window: '超出窗口',
  skipped_not_future: '档期已过',
  skipped_duplicate: '重复',
  skipped_daily_limit: '触达上限',
  skipped_already_subscribed: '已订阅',
  skipped_already_completed: '已完成过',
}

/** 后端版本号；与前端不一致时提示硬刷新。 */
const backendVersion = computed(() => String(status.value?.plugin_version || ''))
const versionMismatch = computed(() => {
  if (!backendVersion.value) return ''
  return backendVersion.value === FRONTEND_VERSION
    ? ''
    : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backendVersion.value}`
})

/** 已实现的数据源（其余源在当前版本会在日志里明确跳过）。 */
const IMPLEMENTED = ['tmdb', 'anilist', 'douban_rss']

/** 豆瓣 RSS 地址：后端存字符串数组，界面用多行文本编辑。 */
const doubanSourcesText = computed({
  get() {
    const value = form.value.douban_rss_sources
    return Array.isArray(value) ? value.join('\n') : String(value || '')
  },
  set(value) {
    form.value.douban_rss_sources = String(value || '')
      .split(/[\n,，]+/)
      .map((entry) => entry.trim())
      .filter(Boolean)
  },
})

const sourceRows = [
  { key: 'enable_tmdb', label: 'TMDB', hint: '全球电影/剧集，自带 TMDB ID（身份最可靠）' },
  {
    key: 'enable_anilist',
    label: 'AniList',
    hint: '番剧 + 国漫；官方 GraphQL，自带开播日、在播状态与热度',
  },
  { key: 'enable_douban_rss', label: '豆瓣 RSS', hint: '经 RSSHub；上映日期与豆瓣 ID 均可解析' },
]

/** 基础开关：一行一个，左标题右开关。 */
const switchRows = [
  {
    key: 'enabled',
    label: '启用插件',
    hint: '关闭后定时任务与手动运行都会跳过',
  },
  {
    key: 'discovery_page_enabled',
    label: '在「发现」分区显示入口',
    hint: '关闭只是不显示入口，插件仍会按时运行',
  },
  {
    key: 'dry_run',
    label: 'dry-run（只记录不写入）',
    hint: '调参阶段建议开启：跑完整流程但不真的建订阅',
  },
  {
    key: 'notify',
    label: '发送运行摘要通知',
    hint: '每次运行结束后推送一条汇总消息',
  },
]

const enabledSourceCount = computed(
  () => sourceRows.filter((row) => form.value[row.key]).length,
)

const sectionNav = computed(() => [
  { key: 'overview', label: '总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'source', label: '数据源', icon: 'mdi-radar', badge: `${enabledSourceCount.value}/${sourceRows.length}` },
  { key: 'threshold', label: '窗口与阈值', icon: 'mdi-tune-variant' },
  { key: 'schedule', label: '写入与调度', icon: 'mdi-calendar-clock' },
  { key: 'preview', label: '预览结果', icon: 'mdi-eye-outline', badge: previewItems.value.length || '' },
])

const overviewCards = computed(() => {
  const written = status.value?.written_today
  const limit = status.value?.daily_limit
  return [
    {
      icon: 'mdi-download-network-outline',
      label: '今日写入',
      value: written != null ? `${written}` : '—',
      sub:
        limit == null
          ? '上限未取到'
          : Number(limit) <= 0
            ? '不限制写入条数'
            : `上限 ${limit} 条`,
      color: 'primary',
    },
    {
      icon: 'mdi-radar',
      label: '已启用数据源',
      value: `${enabledSourceCount.value}`,
      sub: `共 ${sourceRows.length} 个，已实现 ${IMPLEMENTED.length} 个`,
      color: 'info',
    },
    {
      icon: 'mdi-calendar-range',
      label: '发现窗口',
      value: `${form.value.tmdb_future_days ?? '—'} 天`,
      sub: `Bangumi ${form.value.bangumi_future_days ?? '—'} 天 · 豆瓣 ${form.value.douban_future_days ?? '—'} 天`,
      color: 'success',
    },
    {
      icon: 'mdi-source-branch',
      label: '组件版本',
      value: `v${FRONTEND_VERSION}`,
      sub: backendVersion.value ? `后端 v${backendVersion.value}` : '后端版本未知',
      color: versionMismatch.value ? 'warning' : 'default',
    },
  ]
})

/** 概览里的提醒条目（只显示确实需要注意的）。 */
const overviewAlerts = computed(() => {
  const list = []
  if (versionMismatch.value) {
    list.push({
      type: 'warning',
      text: `${versionMismatch.value}：浏览器仍在用缓存的旧联邦组件，请按 Ctrl+Shift+R 硬刷新后再操作。`,
    })
  }
  if (status.value && !status.value.first_run_completed) {
    list.push({
      type: 'info',
      text: '首次运行会强制 dry-run 一次：只记录不写入，确认结果后再放开。',
    })
  }
  if (!form.value.enabled) {
    list.push({ type: 'warning', text: '插件当前未启用，定时任务不会执行。' })
  }
  if (form.value.dry_run) {
    list.push({ type: 'info', text: 'dry-run 已开启：本次运行不会真的建订阅。' })
  }
  if (!cronValid()) {
    list.push({ type: 'error', text: '执行时间不是合法的 5 段式 cron（分 时 日 月 周）。' })
  }
  const pending = sourceRows.filter(
    (row) => form.value[row.key] && !IMPLEMENTED.includes(row.key.replace('enable_', '')),
  )
  if (pending.length) {
    list.push({
      type: 'info',
      text: `已启用但当前版本不会运行：${pending.map((row) => row.label).join('、')}`,
    })
  }
  return list
})

/** 豆瓣榜单列表（每榜独立配置）。 */
const doubanLists = computed(() => form.value.douban_rss_sources || [])

/** 添加一条自定义榜单。 */
function addDoubanList() {
  if (!Array.isArray(form.value.douban_rss_sources)) form.value.douban_rss_sources = []
  form.value.douban_rss_sources.push({
    name: '自定义榜单',
    url: '',
    enabled: true,
    max_items: 30,
    future_days: 3,
    min_want: 0,
  })
}

/** 删除一条榜单。 */
function removeDoubanList(index) {
  const list = form.value.douban_rss_sources
  if (Array.isArray(list) && index >= 0 && index < list.length) list.splice(index, 1)
}

/** 统计启用条数（卡片标题用）。 */
const doubanEnabledCount = computed(
  () => doubanLists.value.filter((entry) => entry && entry.enabled).length,
)

function setTip(text, ok = true) {
  tip.value = { show: true, ok, text }
}

function mergeConfig(value) {
  const base = defaultConfig()
  if (value && typeof value === 'object') {
    for (const key of Object.keys(base)) {
      if (value[key] !== undefined && value[key] !== null) base[key] = value[key]
    }
  }
  return base
}

function buildPayload() {
  // 只提交 default_config 里声明过的键，避免把宿主的其它数据带回去
  const payload = {}
  for (const key of Object.keys(defaultConfig())) payload[key] = form.value[key]
  return payload
}

function cronValid() {
  return String(form.value.cron || '').trim().split(/\s+/).length === 5
}

async function loadConfig() {
  loading.value = true
  try {
    const value = await getPluginConfig(props.api, props.pluginId)
    form.value = mergeConfig(value && Object.keys(value).length ? value : props.initialConfig)
  } catch (error) {
    form.value = mergeConfig(props.initialConfig)
    setTip(error?.message || '配置读取失败', false)
  } finally {
    loading.value = false
  }
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status'))
  } catch (error) {
    // 状态失败不影响保存配置，只在控制台留痕
    console.warn('[SubscribeCenter] 状态读取失败：', error?.message || error)
  }
}

async function save() {
  if (busy.value) return
  if (!cronValid()) {
    setTip('cron 必须是 5 段式（分 时 日 月 周），例如 0 3 * * *', false)
    return
  }
  busy.value = 'save'
  try {
    const payload = buildPayload()
    // 两条路都走：宿主编排 + 自持保存
    emit('save', payload)
    await savePluginConfig(props.api, props.pluginId, payload)
    setTip('设置已保存')
    await loadStatus()
  } catch (error) {
    setTip(error?.message || '保存失败', false)
  } finally {
    busy.value = ''
  }
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
          + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`
          + (s.dry_run ? '（dry-run，未写入）' : ''),
      )
    }
    await loadStatus()
  } catch (error) {
    setTip(error?.message || '运行失败', false)
  } finally {
    busy.value = ''
  }
}

/**
 * 只读预览：跑完整流水线但**不写订阅、不消耗每日额度**。
 * 这是调参的主要工具 —— 改门槛/窗口后先预览，满意再真跑。
 */
async function preview() {
  if (busy.value) return
  busy.value = 'preview'
  previewItems.value = []
  try {
    const result = unwrap(
      await postPluginApi(props.api, props.pluginId, 'preview', {}, { timeoutMs: 600000 }),
    )
    if (result?.skipped) {
      setTip('已有发现任务正在运行，本次跳过')
      return
    }
    previewItems.value = result?.items || []
    activeSection.value = 'preview'
    const s = result?.summary || {}
    const reasons = Object.entries(result?.rejections || {})
      .map(([key, count]) => `${DECISION_LABELS[key] || key} ${count}`)
      .join(' · ')
    setTip(
      `预览完成（未写入）：会订 ${previewItems.value.length} 条 / 拉取 ${s.fetched ?? 0} 条`
        + (reasons ? `；被拦下：${reasons}` : ''),
    )
  } catch (error) {
    setTip(error?.message || '预览失败', false)
  } finally {
    busy.value = ''
  }
}

onMounted(() => {
  loadConfig()
  loadStatus()
})
</script>

<template>
  <div class="sc-root">
    <VAlert
      v-if="tip.show"
      :type="tip.ok ? 'success' : 'error'"
      variant="tonal"
      density="compact"
      closable
      class="sc-tip mb-2"
      :text="tip.text"
      @click:close="tip.show = false"
    />

    <!-- 顶部标题栏 -->
    <div class="sc-header">
      <div class="sc-header-main">
        <div class="sc-logo">
          <VIcon icon="mdi-movie-open-star-outline" size="22" />
        </div>
        <div>
          <div class="sc-title">
            胖虎订阅中心
            <VChip size="x-small" variant="flat" color="primary" class="ml-2">
              v{{ FRONTEND_VERSION }}
            </VChip>
          </div>
          <div class="sc-subtitle">
            发现片源 → 解析身份 → 去重 → 写订阅。版本控制与洗版由 MoviePilot 接管，本插件不介入。
          </div>
        </div>
      </div>
      <VSwitch
        v-model="form.enabled"
        :label="form.enabled ? '已启用' : '未启用'"
        color="success"
        density="compact"
        hide-details
        class="sc-header-switch"
      />
    </div>

    <div class="sc-body">
      <!-- 左侧分区导航 -->
      <nav class="sc-nav">
        <button
          v-for="item in sectionNav"
          :key="item.key"
          type="button"
          class="sc-nav-item"
          :class="{ 'sc-nav-active': activeSection === item.key }"
          @click="activeSection = item.key"
        >
          <VIcon :icon="item.icon" size="18" />
          <span class="sc-nav-label">{{ item.label }}</span>
          <span v-if="item.badge" class="sc-nav-badge">{{ item.badge }}</span>
        </button>
      </nav>

      <!-- 右侧内容 -->
      <section class="sc-content">
        <!-- 总览 -->
        <template v-if="activeSection === 'overview'">
          <div class="sc-cards">
            <div v-for="card in overviewCards" :key="card.label" class="sc-stat">
              <div class="sc-stat-top">
                <VIcon :icon="card.icon" size="18" :color="card.color" />
                <span class="sc-stat-label">{{ card.label }}</span>
              </div>
              <div class="sc-stat-value">{{ card.value }}</div>
              <div class="sc-stat-sub">{{ card.sub }}</div>
            </div>
          </div>

          <div v-if="overviewAlerts.length" class="sc-card">
            <div class="sc-card-title">需要注意</div>
            <div
              v-for="(alert, index) in overviewAlerts"
              :key="index"
              class="sc-alert-row"
              :class="`sc-alert-${alert.type}`"
            >
              <VIcon
                :icon="alert.type === 'error'
                  ? 'mdi-alert-circle-outline'
                  : alert.type === 'warning'
                    ? 'mdi-alert-outline'
                    : 'mdi-information-outline'"
                size="16"
              />
              <span>{{ alert.text }}</span>
            </div>
          </div>

          <div class="sc-card">
            <div class="sc-card-title">运行链路</div>
            <div class="sc-flow">
              <span class="sc-flow-node">拉取候选</span>
              <VIcon icon="mdi-arrow-right" size="14" />
              <span class="sc-flow-node">身份解析</span>
              <VIcon icon="mdi-arrow-right" size="14" />
              <span class="sc-flow-node">季号裁决</span>
              <VIcon icon="mdi-arrow-right" size="14" />
              <span class="sc-flow-node">阈值过滤</span>
              <VIcon icon="mdi-arrow-right" size="14" />
              <span class="sc-flow-node">去重</span>
              <VIcon icon="mdi-arrow-right" size="14" />
              <span class="sc-flow-node sc-flow-accent">写订阅</span>
            </div>
            <div class="sc-hint mt-2">
              季号由 TMDB 的真实数据裁决（哪一季还有未播集），不猜豆瓣/Bangumi 的命名含义。
            </div>
          </div>
        </template>

        <!-- 数据源 -->
        <template v-if="activeSection === 'source'">
          <div class="sc-card">
            <div class="sc-card-title">数据源</div>
            <div v-for="row in sourceRows" :key="row.key" class="sc-row">
              <div class="sc-row-main">
                <div class="sc-row-label">
                  {{ row.label }}
                  <VChip
                    v-if="IMPLEMENTED.includes(row.key.replace('enable_', ''))"
                    size="x-small"
                    variant="flat"
                    color="success"
                    class="ml-1"
                  >
                    已实现
                  </VChip>
                  <VChip v-else size="x-small" variant="tonal" class="ml-1">未实现</VChip>
                </div>
                <div class="sc-row-hint">{{ row.hint }}</div>
              </div>
              <VSwitch v-model="form[row.key]" density="compact" hide-details color="primary" />
            </div>
          </div>

          <div class="sc-card">
            <div class="sc-card-title">豆瓣 RSS 路线</div>
            <VTextField
              v-model="form.rsshub_domain"
              label="RSSHub 域名（总控）"
              density="compact"
              hide-details
              variant="outlined"
              placeholder="http://192.168.50.134:1200"
              class="mb-2"
              :disabled="!form.enable_douban_rss"
            />
            <div class="sc-hint mb-2">
              每条榜单只填**路由**（如 <code>/douban/movie/coming</code>），
              实际请求 = 域名 + 路由。换 RSSHub 地址只改这里，不用逐条改。
            </div>
            <div class="sc-list-head">
              <span class="sc-hint">已启用 {{ doubanEnabledCount }} / {{ doubanLists.length }} 条</span>
              <VBtn size="x-small" variant="tonal" prepend-icon="mdi-plus" @click="addDoubanList">
                添加榜单
              </VBtn>
            </div>
            <div
              v-for="(entry, index) in doubanLists"
              :key="index"
              class="sc-list-item"
              :class="{ 'sc-list-off': !entry.enabled }"
            >
              <div class="sc-list-row">
                <VSwitch
                  v-model="entry.enabled"
                  density="compact"
                  hide-details
                  color="primary"
                  class="sc-list-switch"
                />
                <VTextField
                  v-model="entry.name"
                  density="compact"
                  hide-details
                  variant="outlined"
                  placeholder="榜单名称"
                  style="max-width: 160px"
                />
                <VTextField
                  v-model="entry.url"
                  density="compact"
                  hide-details
                  variant="outlined"
                  placeholder="/douban/movie/coming 或完整 URL"
                  class="sc-list-url"
                />
                <VBtn
                  size="x-small"
                  variant="text"
                  color="error"
                  icon="mdi-delete-outline"
                  @click="removeDoubanList(index)"
                />
              </div>
              <div class="sc-list-row sc-list-params">
                <VTextField
                  v-model.number="entry.max_items"
                  label="每榜条数（0=沿用全局）"
                  type="number"
                  min="1"
                  max="200"
                  density="compact"
                  hide-details
                  variant="outlined"
                />
                <VTextField
                  v-model.number="entry.future_days"
                  label="窗口天数（0=沿用全局）"
                  type="number"
                  min="0"
                  max="120"
                  density="compact"
                  hide-details
                  variant="outlined"
                />
                <VTextField
                  v-model.number="entry.min_want"
                  label="最低想看（0=不限）"
                  type="number"
                  min="0"
                  step="100"
                  density="compact"
                  hide-details
                  variant="outlined"
                />
              </div>
            </div>
            <div class="sc-hint mt-2">
              <b>电影上映类</b>（<code>/douban/movie/coming</code>）带精确上映日期，按窗口过滤，最准。<br />
              <b>剧集类</b>（<code>/douban/tv/coming</code>、<code>/douban/list/tv_*</code>、
              <code>/douban/recommended/tv</code>）没有日期，按「TMDB 还有没有未播集」判断，等效追番。<br />
              <b>电影榜单类</b>没有日期，会被跳过。<code>ustop250</code> 与
              <code>/douban/movie/new</code> 在新版 RSSHub 已 404。
            </div>
          </div>
        </template>

        <!-- 窗口与阈值 -->
        <template v-if="activeSection === 'threshold'">
          <div class="sc-card">
            <div class="sc-card-title">
              <VIcon icon="mdi-movie-open-outline" size="16" /> TMDB
            </div>
            <VRow dense>
              <VCol cols="12" sm="4">
                <VTextField
                  v-model.number="form.tmdb_future_days"
                  label="发现窗口（天）"
                  type="number"
                  min="1"
                  max="90"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
              <VCol cols="12" sm="4">
                <VTextField
                  v-model.number="form.min_rating_tmdb"
                  label="最低评分"
                  type="number"
                  step="0.1"
                  min="0"
                  max="10"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
              <VCol cols="12" sm="4">
                <VTextField
                  v-model.number="form.min_popularity"
                  label="最低关注度"
                  type="number"
                  step="1"
                  min="0"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
            </VRow>
            <div class="sc-hint">
              只保留「今天 ~ 今天 + N 天」内的定档条目。<b>最低关注度</b>是新片唯一可用的质量信号
              （观众级大片 100+、院线片 10~50、冷门片 &lt;5），设 0 表示不过滤。
            </div>

            <VDivider class="my-3" />
            <VSwitch
              v-model="form.filter_original_language"
              label="只保留指定原始语言的条目"
              density="compact"
              hide-details
              color="primary"
            />
            <VTextField
              v-model="form.tmdb_original_languages"
              label="允许的原始语言（逗号分隔）"
              density="compact"
              hide-details
              variant="outlined"
              :disabled="!form.filter_original_language"
              placeholder="zh,ja,ko,en"
              class="mt-2"
            />
            <div class="sc-hint mt-1">
              语种码：zh 华语 / ja 日语 / ko 韩语 / en 英语。小语种片通常不会被下载，进订阅只会白占额度。
            </div>
          </div>

          <div class="sc-card">
            <div class="sc-card-title">
              <VIcon icon="mdi-animation-outline" size="16" /> AniList
            </div>
            <VRow dense>
              <VCol cols="12" sm="4">
                <VTextField
                  v-model.number="form.anilist_future_days"
                  label="发现窗口（天）"
                  type="number"
                  min="1"
                  max="90"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
              <VCol cols="12" sm="3">
                <VTextField
                  v-model.number="form.min_rating_anilist"
                  label="最低评分"
                  type="number"
                  step="0.1"
                  min="0"
                  max="10"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
              <VCol cols="12" sm="3">
                <VTextField
                  v-model.number="form.anilist_min_popularity"
                  label="最低热度"
                  type="number"
                  min="0"
                  step="100"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
              <VCol cols="12" sm="3" class="d-flex align-center">
                <VSwitch
                  v-model="form.anilist_include_donghua"
                  label="包含国漫"
                  density="compact"
                  hide-details
                  color="primary"
                />
              </VCol>
            </VRow>
            <div class="sc-hint">
              <b>番剧与国漫的最佳源。</b>两条发现通道缺一不可：<br />
              • <b>新番</b>：按「开播日」落窗口，覆盖当季 + 下季已定档；<br />
              • <b>连载中</b>：按「下一集播出时间」落窗口 —— <b>国漫只能靠这条</b>
              （《遮天》2023 年开播、208 集，开播日永远在窗口外）。<br />
              热度量纲与 TMDB 不同（冷门番上千、主流番 2~5 万），所以单独设门槛。
              国漫默认包含，只想订日番就关掉。
            </div>
          </div>

          <div class="sc-card">
            <div class="sc-card-title">
              <VIcon icon="mdi-movie-filter-outline" size="16" /> 豆瓣 RSS
            </div>
            <VRow dense>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model.number="form.douban_future_days"
                  label="发现窗口（天）"
                  type="number"
                  min="1"
                  max="90"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                  :disabled="!form.enable_douban_rss"
                />
              </VCol>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model.number="form.min_rating_douban"
                  label="最低评分"
                  type="number"
                  step="0.1"
                  min="0"
                  max="10"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                  :disabled="!form.enable_douban_rss"
                />
              </VCol>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model.number="form.douban_min_want"
                  label="最低想看人数（0 = 不限）"
                  type="number"
                  min="0"
                  step="100"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                  :disabled="!form.enable_douban_rss"
                />
              </VCol>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model.number="form.douban_max_items_per_feed"
                  label="每个榜单最多取 N 条"
                  type="number"
                  min="1"
                  max="200"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                  :disabled="!form.enable_douban_rss"
                />
              </VCol>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model.number="form.resolve_concurrency"
                  label="身份解析并发数"
                  type="number"
                  min="1"
                  max="16"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
            </VRow>
            <div class="sc-hint">
              豆瓣窗口独立于 TMDB（「即将上映」是策展列表，可以放宽）。想看人数只有 coming 类路线提供，
              榜单类没有该数据，<b>缺失时不拦</b>。候选多不需要手动减 —— 解析是并发的，
              实测 260 条约 20~30 秒。
            </div>
          </div>

          <div class="sc-card">
            <div class="sc-card-title">
              <VIcon icon="mdi-check-decagram-outline" size="16" /> 订阅行为
            </div>
            <div class="sc-row">
              <div class="sc-row-main">
                <div class="sc-row-label">已完成过的订阅允许重新订阅</div>
                <div class="sc-row-hint">
                  从媒体库删掉文件后想重新下时需要。真正<b>已经播完</b>的剧不会因此重复订阅。
                </div>
              </div>
              <VSwitch
                v-model="form.resubscribe_completed"
                density="compact"
                hide-details
                color="primary"
              />
            </div>
            <div class="sc-row">
              <div class="sc-row-main">
                <div class="sc-row-label">用 TMDB 分组精确订阅被压成单季的番剧</div>
                <div class="sc-row-hint">
                  如《药屋少女的呢喃》= 1 季 60 集，第 49~60 集才是第 3 季。开启后只订那 12 集，
                  <b>不会去补前 48 集旧番</b>。
                </div>
              </div>
              <VSwitch
                v-model="form.prefer_episode_group"
                density="compact"
                hide-details
                color="primary"
              />
            </div>
          </div>
        </template>

        <!-- 写入与调度 -->
        <template v-if="activeSection === 'schedule'">
          <div class="sc-card">
            <div class="sc-card-title">写入与调度</div>
            <VRow dense>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model.number="form.daily_limit"
                  label="每日写入上限（0 = 不限）"
                  type="number"
                  min="0"
                  :max="100000"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model.number="form.resolve_concurrency"
                  label="身份解析并发数"
                  type="number"
                  min="1"
                  max="16"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model="form.cron"
                  label="执行时间（5 段式 cron）"
                  :error="!cronValid()"
                  :error-messages="cronValid() ? [] : ['需要 5 段，例如 0 3 * * *']"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model="form.timezone"
                  label="时区"
                  density="compact"
                  hide-details
                  variant="outlined"
                  class="mb-2"
                />
              </VCol>
            </VRow>
            <div class="sc-hint">修改 cron 后需要重新保存配置才会重建定时任务。</div>

            <VDivider class="my-3" />
            <!-- 注意：这里要把 switchRows 里除 enabled 之外的全部渲染出来。
                 之前写成 slice(0, 1) 只渲染了第一项，导致「发现页入口」「dry-run」
                 「发送运行摘要通知」三个开关在界面上消失（真机反馈：通知开关没了）。 -->
            <div
              v-for="row in switchRows.filter((item) => item.key !== 'enabled')"
              :key="row.key"
              class="sc-row"
            >
              <div class="sc-row-main">
                <div class="sc-row-label">{{ row.label }}</div>
                <div class="sc-row-hint">{{ row.hint }}</div>
              </div>
              <VSwitch
                v-model="form[row.key]"
                density="compact"
                hide-details
                color="primary"
                :disabled="row.key !== 'notify' && !form.enabled"
              />
            </div>
            <div class="sc-row">
              <div class="sc-row-main">
                <div class="sc-row-label">清零今日写入计数（测试开关）</div>
                <div class="sc-row-hint">
                  保存后把「今日已写入 N 条」清零，方便同一天反复测；保存即自动置回关闭。
                  首次运行无论此开关如何都会强制 dry-run 一次。
                </div>
              </div>
              <VSwitch
                v-model="form.reset_daily_counter"
                density="compact"
                hide-details
                color="warning"
              />
            </div>
          </div>
        </template>

        <!-- 预览结果 -->
        <template v-if="activeSection === 'preview'">
          <div class="sc-card">
            <div class="sc-card-title sc-preview-head">
              <VIcon icon="mdi-eye-outline" size="16" /> 预览结果
              <VChip size="x-small" variant="flat" color="info" class="ml-2">
                会订 {{ previewItems.length }} 条
              </VChip>
              <VChip size="x-small" variant="tonal" class="ml-1">未写入 · 未消耗额度</VChip>
              <div class="sc-preview-action">
                <VBtn
                  variant="tonal"
                  color="info"
                  size="small"
                  :loading="busy === 'preview'"
                  :disabled="loading"
                  prepend-icon="mdi-eye-outline"
                  @click="preview"
                >
                  开始预览
                </VBtn>
              </div>
            </div>
            <div v-if="!previewItems.length" class="sc-empty">
              还没有预览结果。点上方「开始预览」跑一次 ——
              它跑完整流程但<b>不写订阅、不消耗每日额度</b>，是调参的主要手段。
            </div>
            <div v-for="(row, index) in previewItems" :key="index" class="sc-preview-row">
              <div class="d-flex align-center flex-wrap ga-2">
                <VChip size="x-small" variant="flat" color="info">{{ row.media_type }}</VChip>
                <b>{{ row.title }}</b>
                <span v-if="row.year" class="sc-hint">({{ row.year }})</span>
                <span v-if="row.release_date" class="sc-hint">放送 {{ row.release_date }}</span>
                <VChip size="x-small" variant="tonal" color="warning">
                  关注度 {{ row.popularity != null ? row.popularity.toFixed(1) : '—' }}
                </VChip>
                <span v-if="row.rating != null" class="sc-hint">评分 {{ row.rating }}</span>
              </div>
            </div>
          </div>
        </template>
      </section>
    </div>

    <!-- 吸底操作栏 -->
    <div class="sc-footer">
      <VBtn variant="text" size="small" @click="emit('close')">关闭</VBtn>
      <div class="sc-footer-right">
        <VBtn
          variant="tonal"
          size="small"
          :loading="busy === 'run'"
          :disabled="loading"
          prepend-icon="mdi-radar"
          @click="runOnce"
        >
          立即运行一次
        </VBtn>
        <VBtn
          color="primary"
          size="small"
          :loading="busy === 'save'"
          :disabled="loading"
          prepend-icon="mdi-content-save"
          @click="save"
        >
          保存配置
        </VBtn>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 根容器：占满可用空间。
   参考本仓库 tgmediacenter 的成熟写法 —— 顶部栏 + 主体(flex:1) + 吸底栏，
   主体 min-height:0 后内部滚动，既不会跳动也不会把滚动条顶出可视区。 */
.sc-root {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  max-width: 100%;
  height: min(820px, calc(100dvh - 48px));
  padding: 16px;
  box-sizing: border-box;
  font-size: 13px;
}

/* 顶部提示条：必须「不参与 flex 分配」，否则会被拉高成一大块 */
.sc-tip {
  flex: 0 0 auto;
  align-self: stretch;
  min-height: 0;
  height: auto;
  font-size: 12px;
}
.sc-tip :deep(.v-alert__content) {
  font-size: 12px;
  padding: 0;
}

/* 顶部 */
.sc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 10px;
  background: rgba(var(--v-theme-surface), 0.5);
}
.sc-header-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.sc-logo {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 9px;
  color: rgb(var(--v-theme-on-primary));
  background: rgb(var(--v-theme-primary));
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
  opacity: 0.66;
  line-height: 1.4;
}
.sc-header-switch {
  flex: 0 0 auto;
}

/* 主体布局 */
/* 主体：不设固定高度（宿主容器高度不可控，固定高度会让滚动条落到可视区外），
   改为右侧内容给 max-height，超出才内部滚动；左侧导航跟随滚动。 */
.sc-body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  gap: 12px;
  align-items: stretch;
}
.sc-nav {
  flex: 0 0 160px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px;
  min-height: 0;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 10px;
}
.sc-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 8px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  opacity: 0.78;
  transition: background 0.15s, opacity 0.15s;
}
.sc-nav-item:hover {
  background: rgba(var(--v-theme-primary), 0.08);
  opacity: 1;
}
.sc-nav-active {
  background: rgba(var(--v-theme-primary), 0.14);
  opacity: 1;
  font-weight: 600;
}
.sc-nav-label {
  flex: 1 1 auto;
  white-space: nowrap;
}
.sc-nav-badge {
  font-size: 11px;
  opacity: 0.7;
}
.sc-content {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-width: thin;
}
.sc-content::-webkit-scrollbar {
  width: 6px;
}
.sc-content::-webkit-scrollbar-thumb {
  border-radius: 3px;
  background: rgba(var(--v-border-color), 0.4);
}

/* 榜单列表编辑器 */
.sc-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.sc-list-item {
  padding: 8px;
  border: 1px solid rgba(var(--v-border-color), 0.14);
  border-radius: 9px;
  margin-bottom: 8px;
}
.sc-list-off {
  opacity: 0.5;
}
.sc-list-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sc-list-row + .sc-list-row {
  margin-top: 8px;
}
.sc-list-switch {
  flex: 0 0 auto;
}
.sc-list-url {
  flex: 1 1 auto;
  min-width: 0;
}
.sc-list-params > * {
  flex: 1 1 0;
  min-width: 0;
}

/* 卡片 */
.sc-card {
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 10px;
}
.sc-card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  opacity: 0.92;
}

/* 数据卡 */
.sc-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}
.sc-stat {
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 10px;
}
.sc-stat-top {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  opacity: 0.72;
}
.sc-stat-value {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}
.sc-stat-sub {
  margin-top: 2px;
  font-size: 11px;
  opacity: 0.6;
}

/* 提醒 */
.sc-alert-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 5px 0;
  font-size: 12px;
  line-height: 1.5;
}
.sc-alert-warning {
  color: rgb(var(--v-theme-warning));
}
.sc-alert-error {
  color: rgb(var(--v-theme-error));
}
.sc-alert-info {
  opacity: 0.75;
}

/* 流程 */
.sc-flow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  opacity: 0.85;
}
.sc-flow-node {
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 12px;
  background: rgba(var(--v-theme-on-surface), 0.06);
}
.sc-flow-accent {
  background: rgba(var(--v-theme-primary), 0.18);
  font-weight: 600;
}

/* 开关行 */
.sc-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 0;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.08);
}
.sc-row:last-child {
  border-bottom: none;
}
.sc-row-main {
  min-width: 0;
}
.sc-row-label {
  font-size: 13px;
  line-height: 1.5;
}
.sc-row-hint {
  font-size: 11.5px;
  line-height: 1.5;
  opacity: 0.62;
}

/* 预览 */
.sc-preview-head {
  flex-wrap: wrap;
}
.sc-preview-action {
  margin-left: auto;
}
.sc-preview-row {
  padding: 6px 0;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.08);
}
.sc-preview-row:last-child {
  border-bottom: none;
}
.sc-empty {
  padding: 18px 4px;
  font-size: 12px;
  text-align: center;
  opacity: 0.6;
}
.sc-hint {
  font-size: 12px;
  line-height: 1.55;
  opacity: 0.66;
}

/* 吸底操作栏 */
.sc-footer {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 10px;
  background: rgb(var(--v-theme-surface));
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.12);
}
.sc-footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 窄屏：导航变成横向条 */
@media (max-width: 720px) {
  .sc-root {
    width: calc(100vw - 24px);
    height: auto;
    max-height: none;
  }
  .sc-body {
    flex-direction: column;
  }
  .sc-nav {
    position: static;
  }
  .sc-content {
    height: auto;
    overflow-y: visible;
    padding-right: 0;
  }
  .sc-nav {
    flex: 1 1 auto;
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
  }
  .sc-nav-item {
    width: auto;
    white-space: nowrap;
  }
  .sc-nav-badge {
    display: none;
  }
  .sc-subtitle {
    display: none;
  }
}

code {
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  font-size: 11.5px;
}
</style>
