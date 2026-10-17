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
  skipped_source_disabled: '源未启用',
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

    <VRow dense>
      <VCol cols="12" md="4">
        <VCard variant="tonal" class="h-100">
          <VCardTitle class="text-subtitle-1">运行状态</VCardTitle>
          <VCardText v-if="status">
            <div class="sc-kv"><span>插件版本</span><b>v{{ status.plugin_version }}</b></div>
            <div class="sc-kv">
              <span>启用</span>
              <VChip size="x-small" :color="status.enabled ? 'success' : 'default'" variant="flat">
                {{ status.enabled ? '是' : '否' }}
              </VChip>
            </div>
            <div class="sc-kv">
              <span>dry-run</span>
              <b>{{ status.dry_run ? '是（不写入）' : '否' }}</b>
            </div>
            <div class="sc-kv">
              <span>首次试运行</span>
              <b>{{ status.first_run_completed ? '已完成' : '未完成（下次强制 dry-run）' }}</b>
            </div>
            <div class="sc-kv"><span>今日写入</span><b>{{ status.written_today }} / {{ status.daily_limit }}</b></div>
            <div class="sc-kv"><span>时区</span><b>{{ status.timezone }}</b></div>
            <div class="sc-kv"><span>最近运行</span><b>{{ status.last_run || '—' }}</b></div>
            <div class="sc-kv"><span>映射缓存</span><b>{{ status.mapping_cache_size }} 条</b></div>
            <div class="sc-kv">
              <span>当前任务</span>
              <VChip size="x-small" :color="status.busy ? 'warning' : 'default'" variant="flat">
                {{ status.busy ? '运行中' : '空闲' }}
              </VChip>
            </div>
          </VCardText>
          <VCardText v-else class="sc-hint">状态加载中…</VCardText>
        </VCard>
      </VCol>

      <VCol cols="12" md="8">
        <VCard variant="outlined" class="h-100">
          <VCardTitle class="text-subtitle-1">数据源</VCardTitle>
          <VCardText>
            <div v-for="s in (status?.sources || [])" :key="s.source" class="sc-source">
              <div class="d-flex align-center ga-2 flex-wrap">
                <b>{{ s.source }}</b>
                <VChip size="x-small" variant="flat" :color="s.enabled ? 'success' : 'default'">
                  {{ s.enabled ? '已启用' : '未启用' }}
                </VChip>
                <VChip v-if="!s.implemented" size="x-small" variant="flat" color="warning">
                  当前版本未实现
                </VChip>
                <span class="sc-hint">最近 {{ s.last_count }} 条 · {{ s.last_run || '从未运行' }}</span>
              </div>
              <div v-if="s.last_error" class="sc-error">失败：{{ s.last_error }}</div>
            </div>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <div class="d-flex flex-wrap ga-2 my-3">
      <VBtn
        color="primary"
        size="small"
        prepend-icon="mdi-radar"
        :loading="busy === 'run'"
        @click="runOnce"
      >
        立即运行一次
      </VBtn>
      <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="refreshAll">
        刷新
      </VBtn>
      <VBtn size="small" variant="text" prepend-icon="mdi-cog" @click="emit('switch')">设置</VBtn>
      <VBtn v-if="!appPage" size="small" variant="text" prepend-icon="mdi-close" @click="emit('close')">
        关闭
      </VBtn>
    </div>

    <VCard variant="outlined">
      <VCardTitle class="d-flex align-center flex-wrap ga-2 text-subtitle-1">
        <span>发现流水</span>
        <VSelect
          v-model="filter"
          :items="[{ title: '全部', value: '' }, ...Object.entries(DECISION_LABELS).map(([value, title]) => ({ title, value }))]"
          density="compact"
          hide-details
          style="max-width: 180px"
          @update:model-value="history.page = 1; loadHistory()"
        />
        <VChip size="x-small" variant="tonal">共 {{ history.total }} 条</VChip>
      </VCardTitle>
      <VCardText>
        <div v-if="!history.items.length" class="sc-hint">
          还没有流水。插件启用后点「立即运行一次」即可看到发现结果。
        </div>
        <div v-for="(item, index) in history.items" :key="index" class="sc-row">
          <div class="d-flex align-center flex-wrap ga-2">
            <VChip size="x-small" variant="flat" :color="decisionColor(item.decision)">
              {{ decisionLabel(item.decision) }}
            </VChip>
            <b>{{ item.title }}</b>
            <span v-if="item.year" class="sc-hint">({{ item.year }})</span>
            <span class="sc-hint">{{ item.source }}</span>
            <VChip v-if="item.confidence" size="x-small" variant="text">身份 {{ item.confidence }}</VChip>
            <span v-if="item.release_date" class="sc-hint">放送 {{ item.release_date }}</span>
          </div>
          <div v-if="item.reason" class="sc-hint">{{ item.reason }}</div>
        </div>
      </VCardText>
      <VCardActions v-if="history.total > history.count" class="justify-center">
        <VBtn size="small" variant="text" :disabled="history.page <= 1" @click="prevPage">上一页</VBtn>
        <span class="sc-hint mx-2">第 {{ history.page }} 页 · 共 {{ history.total }} 条</span>
        <VBtn
          size="small"
          variant="text"
          :disabled="history.page * history.count >= history.total"
          @click="nextPage"
        >
          下一页
        </VBtn>
      </VCardActions>
    </VCard>
  </div>
</template>

<style scoped>
.sc-root {
  padding: 4px;
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
.sc-kv {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  padding: 3px 0;
}
.sc-source {
  padding: 6px 0;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.08);
}
.sc-source:last-child {
  border-bottom: none;
}
.sc-row {
  padding: 6px 0;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.08);
}
.sc-row:last-child {
  border-bottom: none;
}
</style>
