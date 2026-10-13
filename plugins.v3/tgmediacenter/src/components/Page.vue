<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from './api'
import { decisionColor, decisionLabel } from './decision'

/**
 * 插件详情页（运行详情）：TG / 115 / 缓存三张状态卡 + 监控与转发统计 +
 * 最近流水（只展示监控流水，转发流水在转发面板看）+ 快捷操作。
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

function checkSubscriptions() {
  runAction('subs', 'cache/check_subscriptions', {}, '订阅回搜已执行')
}

// ------------------------------------------------------------------ 展示辅助

const tg = computed(() => data.value?.tg || {})
const pan115 = computed(() => data.value?.pan115 || {})
const cache = computed(() => data.value?.cache || {})
const monitor = computed(() => data.value?.monitor || {})
const forward = computed(() => data.value?.forward || {})
const pipeline = computed(() => monitor.value.pipeline || {})
const recentHits = computed(() => data.value?.recent_hits || [])

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

function chatLabel(chatId) {
  const detail = pipeline.value.watched_detail || []
  const found = detail.find(item => item.chat_id === chatId)
  if (found && found.resolved && found.title) return found.title
  return String(chatId ?? '')
}

function mediaName(item) {
  if (!item.title) return '—'
  const year = item.year ? ` (${item.year})` : ''
  let name = `${item.title}${year}`
  if (item.season || item.episode) {
    const s = String(item.season ?? 1).padStart(2, '0')
    const e = String(item.episode ?? 0).padStart(2, '0')
    name += ` S${s}E${e}`
  }
  return name
}

onMounted(async () => {
  await loadOverview()
  // 轻量轮询：详情页常开着看状态，30 秒刷新一次（动作按钮执行后也会立即刷新）
  refreshTimer = window.setInterval(loadOverview, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
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
        <div class="text-h6">TG媒体中心 · 运行详情</div>
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
      <VBtn icon variant="text" size="small" @click="emit('close')">
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
              <span class="tg-key">订阅回搜</span>
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
        <VBtn size="small" variant="tonal" :loading="busy === 'subs'" prepend-icon="mdi-magnify-scan" @click="checkSubscriptions">
          检查新增订阅
        </VBtn>
      </div>

      <!-- 最近流水 -->
      <VCard flat class="tg-card mt-3">
        <VCardItem density="compact">
          <VCardTitle class="text-subtitle-2">最近流水</VCardTitle>
          <template #append>
            <span class="text-caption text-medium-emphasis">监控最近 10 条（转发流水在转发面板查看）</span>
          </template>
        </VCardItem>
        <VCardText>
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
              <tr v-for="item in recentHits" :key="`${item.kind}-${item.id}`">
                <td class="tg-nowrap tg-dim">{{ fmtTime(item.created_at) }}</td>
                <td>{{ item.rule_name }}</td>
                <td class="tg-nowrap">{{ chatLabel(item.chat_id) }}</td>
                <td>{{ mediaName(item) }}</td>
                <td class="tg-nowrap">
                  <VChip size="x-small" variant="tonal" :color="decisionColor(item.decision)" label>
                    {{ decisionLabel(item.decision) }}
                  </VChip>
                </td>
                <td class="tg-dim">{{ item.detail }}</td>
              </tr>
              <tr v-if="!recentHits.length">
                <td colspan="6" class="tg-empty">暂无流水</td>
              </tr>
            </tbody>
          </VTable>
          <div class="tg-note">
            「来源」列与资源监控流水同口径：监听会话 ID 反查标题；完整流水与筛选在「监控」设置页查看。
          </div>
        </VCardText>
      </VCard>
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
</style>
