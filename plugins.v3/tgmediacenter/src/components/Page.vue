<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from './api'
import { decisionColor, decisionLabel } from './decision'

/**
 * 插件详情页（运行详情）：TG / 115 / 缓存三张状态卡 + 监控与转发统计 +
 * 最近流水（监控 / 转发 可切换，分页 + 决策筛选 + 关键词搜索）+ 快捷操作。
 * 决策徽章显示中文文案（映射在 ./decision.js）。
 *
 * 数据只走一个聚合接口 ``/overview``（一次请求拿齐各模块状态与最近流水）：
 * 详情页是"总览"，逐个模块并发拉取既慢又容易半屏空白；后端对每个模块单独
 * 容错，某块失败只影响那块。
 *
 * 纪律（沿用全项目约定）：
 * - 模板/脚本用到的变量全部在 script setup 声明 ref；
 * - 重入保护只留在按钮处理器，内部 fetch 函数无保护；
 * - 操作完成后重新拉 overview，不用本地推测状态。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  // 作为 MP 左侧「发现」分区的整页入口渲染时置 true（1.8.0）：
  // 整页没有"关闭"语义，隐藏关闭按钮；「设置」仍由外层弹出配置弹窗。
  appPage: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'switch'])

const loading = ref(false)
const busy = ref('')
const message = ref('')
const messageOk = ref(true)
const data = ref(null)

let refreshTimer = null

function setMessage(text, ok = true) {
  message.value = text || ''
  messageOk.value = ok
}

// ------------------------------------------------------------------ 数据加载（无重入保护）

async function loadOverview() {
  loading.value = true
  try {
    data.value = unwrap(await getPluginApi(props.api, props.pluginId, 'overview', { timeoutMs: 15000 }))
  } catch (error) {
    setMessage(error?.message || '状态加载失败', false)
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  setMessage('')
  await loadOverview()
}

// ------------------------------------------------------------------ 快捷操作

async function runAction(key, path, body, okText) {
  if (busy.value) return
  busy.value = key
  setMessage('正在执行…')
  try {
    const response = unwrap(await postPluginApi(props.api, props.pluginId, path, body || {}, { timeoutMs: 60000 }))
    setMessage(response?.message || okText || '已完成')
    await loadOverview()
  } catch (error) {
    setMessage(error?.message || '操作失败', false)
  } finally {
    busy.value = ''
  }
}

function connectTg() {
  runAction('tg', 'telegram/connect', {}, 'TG 客户端已连接')
}

function refreshDialogs() {
  runAction('dialogs', 'telegram/refresh_dialogs', {}, '对话列表已刷新')
}

function checkPan115() {
  runAction('pan115', 'pan115/check', {}, '115 连接正常')
}

function syncCache() {
  runAction('cache', 'cache/sync', {}, '缓存同步已触发')
}

async function startBackfill() {
  if (busy.value) return
  busy.value = 'backfill'
  setMessage('正在启动增量补扫…')
  try {
    const response = unwrap(await postPluginApi(
      props.api, props.pluginId, 'cache/backfill/start', { full: false },
      { timeoutMs: 30000 },
    ))
    setMessage(response?.message || (response?.started ? '补扫已启动' : '补扫未启动'), Boolean(response?.started))
    await loadOverview()
  } catch (error) {
    setMessage(error?.message || '启动补扫失败', false)
  } finally {
    busy.value = ''
  }
}

// ------------------------------------------------------------------ 展示辅助

const tg = computed(() => data.value?.tg || {})
const pan115 = computed(() => data.value?.pan115 || {})
const cache = computed(() => data.value?.cache || {})
const monitor = computed(() => data.value?.monitor || {})
const forward = computed(() => data.value?.forward || {})
const pipeline = computed(() => monitor.value.pipeline || {})
// 最近流水：监控 / 转发 两个来源，分页 + 筛选 + 搜索（与设置页同款交互）。
// 详情页之前走 overview 的 recent_hits 摘要（写死 10 条、无翻页），1.6.7 改为
// 直连 /monitor/hits 与 /forward/hits 分页接口，彻底去掉这个"锁"。
const hitTab = ref('monitor')            // 'monitor' | 'forward'
const hits = ref([])
const hitsLoading = ref(false)
const hitsTotal = ref(0)
const hitsPage = ref(1)
const hitsPageSize = 10                  // 详情页每页 10 条
const decisionFilter = ref('')
// 关键词用可写 computed 包一层：Vuetify clearable 清除会置 null，归一避免 .trim() 抛错
const hitKeywordRaw = ref('')
const hitKeyword = computed({
  get: () => String(hitKeywordRaw.value ?? ''),
  set: (value) => { hitKeywordRaw.value = value == null ? '' : String(value) },
})

// 决策下拉：value 用后端权威英文常量（与 /monitor/hits、/forward/hits 的 decision 过滤
// 参数完全一致，保证一定能筛到）；title 统一走 decisionLabel()，与流水「决策」徽章
// 逐字对齐（此前硬编的中文名与徽章对不上，导致用户选不准、以为筛不到）。
// 监控 / 转发各取各自实际会出现的取值集合。
const MONITOR_DECISION_VALUES = [
  'hit', 'skipped_not_missing', 'skipped_not_subscribed',
  'skipped_unrecognized', 'skipped_keyword', 'skipped_no_link',
  'skipped_unknown', 'skipped_extension', 'failed',
]
const FORWARD_DECISION_VALUES = ['hit', 'skipped_keyword', 'skipped_extension']
const monitorDecisions = MONITOR_DECISION_VALUES.map(v => ({ value: v, title: decisionLabel(v) }))
const forwardDecisions = FORWARD_DECISION_VALUES.map(v => ({ value: v, title: decisionLabel(v) }))
const decisionOptions = computed(() => [
  { value: '', title: '全部决策' },
  ...(hitTab.value === 'forward' ? forwardDecisions : monitorDecisions),
])

const hitsPath = computed(() => (hitTab.value === 'forward' ? 'forward/hits' : 'monitor/hits'))

async function loadHits() {
  hitsLoading.value = true
  try {
    // 总数缩小时把越界页码夹回最后一页（轮询期间结果被删的场景）
    const maxPage = hitsTotal.value > 0
      ? Math.max(1, Math.ceil(hitsTotal.value / hitsPageSize))
      : 1
    if (hitsPage.value > maxPage) hitsPage.value = maxPage
    const params = new URLSearchParams()
    params.set('page', String(hitsPage.value))
    params.set('page_size', String(hitsPageSize))
    if (decisionFilter.value) params.set('decision', decisionFilter.value)
    if (hitKeyword.value.trim()) params.set('keyword', hitKeyword.value.trim())
    const res = unwrap(await getPluginApi(
      props.api, props.pluginId, `${hitsPath.value}?${params.toString()}`, { timeoutMs: 15000 },
    ))
    hits.value = res?.items || []
    hitsTotal.value = res?.total || 0
  } catch (error) {
    setMessage(error?.message || '流水加载失败', false)
    hits.value = []
  } finally {
    hitsLoading.value = false
  }
}

function onHitTabChange() {
  hitsPage.value = 1
  decisionFilter.value = ''
  loadHits()
}

function onDecisionFilter() {
  hitsPage.value = 1
  loadHits()
}

function prevHits() {
  if (hitsPage.value <= 1) return
  hitsPage.value -= 1
  loadHits()
}

function nextHits() {
  if (hitsPage.value * hitsPageSize >= hitsTotal.value) return
  hitsPage.value += 1
  loadHits()
}

// 关键词输入防抖 300ms：边打字边查会把后端打满（流水可能上万行）
let keywordTimer = null
watch(hitKeyword, () => {
  clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => {
    hitsPage.value = 1
    loadHits()
  }, 300)
})

// ------------------------------------------------------------------ 流水清理（由设置页迁入）

// 清理入口从设置页的「命中流水 / 转发流水」卡搬到这里：详情页已有 监控/转发 切换、
// 决策筛选、关键词搜索与分页，用户在这里就能确认"当前视图删多少"。
// clearTarget：'filtered' 删除筛选结果 / 'all' 清空本类流水。
// 两个入口都只删「当前视图」——payload 带 decision + keyword（与设置页严格一致），
// 后端按 kind 隔离，监控与转发流水互不影响。
const clearDialog = ref(false)
const clearTarget = ref('filtered')
const clearing = ref(false)

const clearKindLabel = computed(() => (hitTab.value === 'forward' ? '转发' : '监控'))
const otherKindLabel = computed(() => (hitTab.value === 'forward' ? '监控' : '转发'))
// 清理接口随当前分类走：monitor → monitor/hits/clear，forward → forward/hits/clear
const clearPath = computed(() => (
  hitTab.value === 'forward' ? 'forward/hits/clear' : 'monitor/hits/clear'
))

// 当前是否有筛选条件（对话框据此说明"删多少"，与后端删除口径严格一致）
const hasFilter = computed(() => Boolean(decisionFilter.value || hitKeyword.value.trim()))
const filterText = computed(() => [
  decisionFilter.value ? `决策=${decisionLabel(decisionFilter.value)}` : '',
  hitKeyword.value.trim() ? `关键词=${hitKeyword.value.trim()}` : '',
].filter(Boolean).join(' / '))

function askClear(target) {
  if (!hitsTotal.value) {
    setMessage(target === 'all' ? '当前视图没有可清空的流水' : '当前筛选没有可删除的流水')
    return
  }
  clearTarget.value = target
  clearDialog.value = true
}

async function runClear() {
  // 防重复点击：确认按钮同时置 loading，这里再加一道闸
  if (clearing.value) return
  clearing.value = true
  try {
    // 无论点哪个按钮都只删「当前视图」：带动当前决策 + 关键词，没有筛选才是清空本类全部
    const payload = { decision: decisionFilter.value || '', keyword: hitKeyword.value.trim() }
    const response = unwrap(await postPluginApi(
      props.api, props.pluginId, clearPath.value, payload, { timeoutMs: 30000 },
    ))
    // 先给成功提示再刷新：loadHits / loadOverview 只在失败时覆盖 message，
    // 成功时保留这条提示（refreshAll 会先清空 message，故这里直接用 loadOverview）
    clearDialog.value = false
    hitsPage.value = 1
    setMessage(response?.message || '已清理流水')
    await Promise.all([loadHits(), loadOverview()])
  } catch (error) {
    setMessage(error?.message || '清理流水失败', false)
  } finally {
    clearing.value = false
  }
}

// 来源会话 ID → 标题：合并监控与转发两个状态卡的 watched_detail（两 tab 共用一个映射）
const chatTitleMap = computed(() => {
  const map = {}
  for (const which of ['monitor', 'forward']) {
    const detail = data.value?.[which]?.pipeline?.watched_detail || []
    for (const w of detail) {
      if (w.resolved && w.title) map[w.chat_id] = w.title
    }
  }
  return map
})

const tgState = computed(() => {
  const item = tg.value
  if (!item.api_configured) return { color: 'warning', text: '未配置 API' }
  if (item.connected && item.authorized) return { color: 'success', text: '已连接' }
  if (item.session_present) return { color: 'warning', text: '已登录但未连接' }
  return { color: 'error', text: '未登录' }
})

const pan115State = computed(() => {
  const item = pan115.value
  if (!item.enabled) return { color: 'default', text: '未启用' }
  if (item.authorized) return { color: 'success', text: '已登录' }
  return { color: 'warning', text: '未登录' }
})

const cacheState = computed(() => {
  const item = cache.value
  if (!item.enabled) return { color: 'default', text: '未启用' }
  if (item.sync?.running) return { color: 'info', text: '同步中' }
  return { color: 'success', text: '运行中' }
})

const pipelineState = computed(() => {
  if (!monitor.value.enabled && !forward.value.enabled) return { color: 'default', text: '未启用' }
  if (pipeline.value.running && pipeline.value.handler_registered) return { color: 'success', text: '运行中' }
  if (pipeline.value.running) return { color: 'warning', text: '运行中（监听未注册）' }
  return { color: 'warning', text: '未运行' }
})

function spaceLine() {
  const space = pan115.value.space || {}
  if (!space.total) return '—'
  return `${space.used || '?'} / ${space.total}`
}

function fmtTime(value) {
  return String(value || '').replace('T', ' ') || '—'
}

function mediaName(item) {
  if (!item.title) return '—'
  const year = item.year ? ` (${item.year})` : ''
  let name = `${item.title}${year}`
  if (item.season || item.episode) {
    const s = String(item.season ?? 1).padStart(2, '0')
    const e = String(item.episode ?? 0).padStart(2, '0')
    const end = Number(item.episode_end ?? 0)
    // 多集区间（如 S01E05-E06）：结束集 > 起始集时拼区间
    if (end > (item.episode ?? 0)) {
      name += ` S${s}E${e}-E${String(end).padStart(2, '0')}`
    } else {
      name += ` S${s}E${e}`
    }
  }
  return name
}

onMounted(async () => {
  await Promise.all([loadOverview(), loadHits()])
  // 轻量轮询：详情页常开着看状态，30 秒刷新一次；流水刷新保持当前页（不重置页码）
  refreshTimer = window.setInterval(() => {
    loadOverview()
    loadHits()
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (keywordTimer) {
    window.clearTimeout(keywordTimer)
    keywordTimer = null
  }
})
</script>

<template>
  <VCard flat class="tg-page">
    <VToolbar density="comfortable" class="tg-toolbar">
      <VAvatar color="primary" variant="tonal" rounded="lg" class="ms-3 me-2">
        <VIcon icon="mdi-send-circle-outline" />
      </VAvatar>
      <div class="tg-heading">
        <div class="text-h6">胖虎媒体中心 · 运行详情</div>
        <div class="text-caption text-medium-emphasis">
          TG 客户端 → 消息流水线 → 缓存 / 监控 / 转发
        </div>
      </div>
      <VSpacer />
      <VChip v-if="data?.plugin_version" size="small" variant="tonal" color="primary" label class="me-2">
        v{{ data.plugin_version }}
      </VChip>
      <VBtn variant="text" size="small" :loading="loading" prepend-icon="mdi-refresh" @click="refreshAll">
        刷新
      </VBtn>
      <VBtn variant="text" size="small" prepend-icon="mdi-cog-outline" @click="emit('switch')">设置</VBtn>
      <VBtn v-if="!appPage" icon variant="text" size="small" @click="emit('close')">
        <VIcon icon="mdi-close" />
      </VBtn>
    </VToolbar>
    <VDivider />
    <VProgressLinear v-if="loading" indeterminate color="primary" height="2" />

    <VCardText class="pa-3">
      <VAlert
        v-if="message"
        :type="messageOk ? 'info' : 'warning'"
        variant="tonal"
        density="compact"
        class="mb-3"
      >{{ message }}</VAlert>

      <div class="tg-grid">
        <!-- TG 凭证 -->
        <VCard flat class="tg-card">
          <VCardItem density="compact">
            <template #prepend><VIcon icon="mdi-send-outline" size="20" /></template>
            <VCardTitle class="text-subtitle-2">TG 客户端</VCardTitle>
            <template #append>
              <VChip size="x-small" variant="tonal" :color="tgState.color" label>{{ tgState.text }}</VChip>
            </template>
          </VCardItem>
          <VCardText class="tg-lines">
            <div><span class="tg-key">账号</span><span>{{ tg.phone_masked || '未配置' }}</span></div>
            <div><span class="tg-key">监听会话</span><span>{{ tg.dialog_count ?? 0 }} 个</span></div>
            <div><span class="tg-key">对话缓存</span><span>{{ fmtTime(tg.dialogs_updated_at) }}</span></div>
            <div><span class="tg-key">全局冷却</span><span>{{ tg.user_cooldown_seconds ?? 5 }} 秒 / 次</span></div>
            <div>
              <span class="tg-key">FloodWait</span>
              <span :class="{ 'tg-warn': (monitor.flood_remaining ?? 0) > 0 }">
                {{ (monitor.flood_remaining ?? 0) > 0 ? `退避中（约 ${monitor.flood_remaining} 秒）` : '无' }}
              </span>
            </div>
          </VCardText>
        </VCard>

        <!-- 115 网盘 -->
        <VCard flat class="tg-card">
          <VCardItem density="compact">
            <template #prepend><VIcon icon="mdi-cloud-outline" size="20" /></template>
            <VCardTitle class="text-subtitle-2">115 网盘</VCardTitle>
            <template #append>
              <VChip size="x-small" variant="tonal" :color="pan115State.color" label>{{ pan115State.text }}</VChip>
            </template>
          </VCardItem>
          <VCardText class="tg-lines">
            <div><span class="tg-key">账号</span><span>{{ pan115.account || '—' }}</span></div>
            <div><span class="tg-key">登录设备</span><span>{{ pan115.login_device || '—' }}</span></div>
            <div><span class="tg-key">空间</span><span>{{ spaceLine() }}</span></div>
            <div><span class="tg-key">转存目录</span><span class="tg-mono">{{ pan115.target_cid || '默认根目录' }}</span></div>
            <div><span class="tg-key">上次检测</span><span>{{ fmtTime(pan115.last_check) }}</span></div>
          </VCardText>
        </VCard>

        <!-- 消息缓存 -->
        <VCard flat class="tg-card">
          <VCardItem density="compact">
            <template #prepend><VIcon icon="mdi-database-outline" size="20" /></template>
            <VCardTitle class="text-subtitle-2">消息缓存</VCardTitle>
            <template #append>
              <VChip size="x-small" variant="tonal" :color="cacheState.color" label>{{ cacheState.text }}</VChip>
            </template>
          </VCardItem>
          <VCardText class="tg-lines">
            <div><span class="tg-key">缓存频道</span><span>{{ cache.chats ?? 0 }} 个</span></div>
            <div><span class="tg-key">消息总数</span><span>{{ cache.total ?? 0 }} 条</span></div>
            <div><span class="tg-key">最近同步</span><span>{{ fmtTime(cache.sync?.finished_at || cache.sync?.started_at) }}</span></div>
            <div>
              <span class="tg-key">新增订阅回搜</span>
              <span>
                {{ cache.subscribe?.enabled === false ? '已关闭' : '已开启' }}
                <template v-if="cache.subscribe?.last_check_at">
                  · 上次 {{ fmtTime(cache.subscribe.last_check_at) }}
                  （新增 {{ cache.subscribe.last_check_new ?? 0 }} / 推送 {{ cache.subscribe.last_check_pushed ?? 0 }}）
                </template>
              </span>
            </div>
            <div v-if="cache.subscribe?.last_error || cache.sync?.last_error" class="tg-warn">
              {{ cache.subscribe?.last_error || cache.sync?.last_error }}
            </div>
          </VCardText>
        </VCard>

        <!-- 流水线 -->
        <VCard flat class="tg-card">
          <VCardItem density="compact">
            <template #prepend><VIcon icon="mdi-sitemap-outline" size="20" /></template>
            <VCardTitle class="text-subtitle-2">消息流水线</VCardTitle>
            <template #append>
              <VChip size="x-small" variant="tonal" :color="pipelineState.color" label>{{ pipelineState.text }}</VChip>
            </template>
          </VCardItem>
          <VCardText class="tg-lines">
            <div><span class="tg-key">监控规则</span><span>{{ monitor.rules_count ?? 0 }} 条（关心 {{ monitor.watched_chats ?? 0 }} 个会话）</span></div>
            <div><span class="tg-key">转发规则</span><span>{{ forward.rules_count ?? 0 }} 条（关心 {{ forward.watched_chats ?? 0 }} 个会话）</span></div>
            <div><span class="tg-key">累计处理</span><span>{{ pipeline.processed ?? 0 }} 条 · 监控命中 {{ pipeline.hit ?? 0 }} · 转发命中 {{ pipeline.forward_hit ?? 0 }}</span></div>
            <div><span class="tg-key">推送队列</span><span>待处理 {{ pipeline.push_pending ?? 0 }} · 成功 {{ pipeline.push_done ?? 0 }} · 失败 <span :class="{ 'tg-warn': (pipeline.push_failed ?? 0) > 0 }">{{ pipeline.push_failed ?? 0 }}</span></span></div>
            <div><span class="tg-key">最近事件</span><span>{{ fmtTime(pipeline.last_event_at) }}</span></div>
          </VCardText>
        </VCard>
      </div>

      <!-- 快捷操作 -->
      <div class="tg-actions">
        <VBtn size="small" variant="tonal" :loading="busy === 'tg'" prepend-icon="mdi-connection" @click="connectTg">
          连接 TG
        </VBtn>
        <VBtn size="small" variant="tonal" :loading="busy === 'dialogs'" prepend-icon="mdi-account-multiple-outline" @click="refreshDialogs">
          刷新对话列表
        </VBtn>
        <VBtn size="small" variant="tonal" :loading="busy === 'pan115'" prepend-icon="mdi-cloud-check-outline" @click="checkPan115">
          检测 115
        </VBtn>
        <VBtn size="small" variant="tonal" :loading="busy === 'cache'" prepend-icon="mdi-sync" @click="syncCache">
          同步缓存
        </VBtn>
        <VBtn
          size="small"
          variant="tonal"
          :loading="busy === 'backfill'"
          :disabled="Boolean(cache?.backfill?.running)"
          prepend-icon="mdi-refresh-circle"
          @click="startBackfill"
        >
          立即增量补扫
        </VBtn>
      </div>

      <!-- 最近流水：监控 / 转发 可切换，分页 + 筛选 + 搜索 -->
      <VCard flat class="tg-card mt-3">
        <VCardItem density="compact">
          <VCardTitle class="text-subtitle-2">最近流水</VCardTitle>
          <template #append>
            <VBtnToggle
              v-model="hitTab"
              density="comfortable"
              variant="outlined"
              divided
              mandatory
              @update:model-value="onHitTabChange"
            >
              <VBtn value="monitor" size="small">监控</VBtn>
              <VBtn value="forward" size="small">转发</VBtn>
            </VBtnToggle>
          </template>
        </VCardItem>
        <VCardText>
          <div class="tg-hits-tools">
            <VSelect
              v-model="decisionFilter"
              :items="decisionOptions"
              item-title="title"
              item-value="value"
              density="compact"
              variant="outlined"
              hide-details
              class="tg-filter"
              @update:model-value="onDecisionFilter"
            />
            <VTextField
              v-model="hitKeyword"
              placeholder="按片名 / 规则 / 说明搜索"
              prepend-inner-icon="mdi-magnify"
              density="compact"
              variant="outlined"
              hide-details
              clearable
              class="tg-hits-search"
            />
            <!-- 清理入口（从设置页迁入）：只作用于当前视图，无流水时禁用 -->
            <VSpacer />
            <VBtn
              size="small"
              variant="tonal"
              color="error"
              prepend-icon="mdi-delete-sweep-outline"
              :disabled="!hitsTotal || clearing"
              @click="askClear('filtered')"
            >
              删除筛选结果
            </VBtn>
            <VBtn
              size="small"
              variant="text"
              color="error"
              :disabled="!hitsTotal || clearing"
              @click="askClear('all')"
            >
              清空本类流水
            </VBtn>
          </div>
          <VTable density="compact" class="tg-hits">
            <thead>
              <tr>
                <th class="tg-nowrap">时间</th>
                <th>规则</th>
                <th class="tg-nowrap">来源</th>
                <th>媒体</th>
                <th class="tg-nowrap">决策</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in hits" :key="`${hitTab}-${item.id}`">
                <td class="tg-nowrap tg-dim">{{ fmtTime(item.created_at) }}</td>
                <td>{{ item.rule_name }}</td>
                <td class="tg-nowrap">{{ chatTitleMap[item.chat_id] || item.chat_id }}</td>
                <td>{{ mediaName(item) }}</td>
                <td class="tg-nowrap">
                  <VChip size="x-small" variant="tonal" :color="decisionColor(item.decision)" label>
                    {{ decisionLabel(item.decision) }}
                  </VChip>
                </td>
                <td class="tg-dim">{{ item.detail }}</td>
              </tr>
              <tr v-if="!hits.length">
                <td colspan="6" class="tg-empty">暂无流水</td>
              </tr>
            </tbody>
          </VTable>
          <div class="tg-pager">
            <VBtn
              size="small"
              variant="text"
              :disabled="hitsPage <= 1 || hitsLoading"
              prepend-icon="mdi-chevron-left"
              @click="prevHits"
            >
              上一页
            </VBtn>
            <span class="tg-pager-info">第 {{ hitsPage }} 页 · 共 {{ hitsTotal }} 条</span>
            <VBtn
              size="small"
              variant="text"
              :disabled="hitsPage * hitsPageSize >= hitsTotal || hitsLoading"
              append-icon="mdi-chevron-right"
              @click="nextHits"
            >
              下一页
            </VBtn>
          </div>
          <div class="tg-note">
            「来源」列与资源监控流水同口径：监听会话 ID 反查标题；清理流水用上方
            「删除筛选结果 / 清空本类流水」，两者都只作用于当前视图。
          </div>
        </VCardText>
      </VCard>

      <!-- 清理流水确认（删除不可恢复，必须二次确认） -->
      <VDialog v-model="clearDialog" max-width="460">
        <VCard>
          <VCardTitle class="text-subtitle-1">
            {{ clearTarget === 'all' ? '清空本类流水' : '删除筛选结果' }}
          </VCardTitle>
          <VCardText class="text-body-2">
            <div class="mb-2">
              删除范围：当前视图（{{ clearKindLabel }}分类<template v-if="filterText"> · {{ filterText }}</template><template v-else> · 无筛选条件</template>），共
              <strong>{{ hitsTotal }}</strong> 条。
            </div>
            <template v-if="hasFilter">
              当前有筛选条件，将只删除筛选出的 <strong>{{ hitsTotal }}</strong> 条流水，删除后不可恢复；
              未筛选部分不受影响。如需清空本类全部，请先清除筛选条件。
            </template>
            <template v-else>
              将删除本类的<strong>全部{{ clearKindLabel }}流水</strong>（共 {{ hitsTotal }} 条），删除后不可恢复；
              {{ otherKindLabel }}流水不受影响。
            </template>
          </VCardText>
          <VCardActions>
            <VSpacer />
            <VBtn variant="text" :disabled="clearing" @click="clearDialog = false">取消</VBtn>
            <VBtn color="error" :loading="clearing" :disabled="clearing" @click="runClear">删除</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>
    </VCardText>
  </VCard>
</template>

<style scoped>
.tg-page {
  background: transparent;
  width: 100%;
  border-radius: 16px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  overflow: hidden;
}
.tg-toolbar { background: transparent; padding-right: 8px; }
.tg-heading { min-width: 0; }
.tg-heading .text-h6,
.tg-heading .text-caption { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tg-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.tg-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.tg-lines { display: flex; flex-direction: column; gap: 5px; font-size: 12.5px; }
.tg-lines > div { display: flex; gap: 8px; align-items: baseline; }
.tg-key { flex: 0 0 62px; color: rgba(var(--v-theme-on-surface), 0.6); }
.tg-mono { font-family: monospace; word-break: break-all; }
.tg-warn { color: rgb(var(--v-theme-warning)); }
.tg-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.tg-hits { font-size: 12.5px; }
.tg-hits .tg-nowrap { white-space: nowrap; }
.tg-dim { opacity: 0.75; }
.tg-empty { text-align: center; padding: 16px; opacity: 0.6; }
.tg-note { margin-top: 8px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.6; }
.tg-hits-tools { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.tg-filter { flex: 0 0 160px; max-width: 200px; }
.tg-hits-search { flex: 1 1 220px; max-width: 320px; }
.tg-pager { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.tg-pager-info { font-size: 12px; opacity: 0.7; }
</style>
