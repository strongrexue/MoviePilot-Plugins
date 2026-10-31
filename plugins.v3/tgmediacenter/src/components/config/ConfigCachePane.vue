<template>
  <div class="cache-pane">
    <!-- 启用开关 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <template #prepend>
          <VSwitch v-model="form.cache_enabled" color="primary" hide-details inset />
        </template>
        <VCardTitle class="text-subtitle-2">启用消息缓存</VCardTitle>
        <VCardSubtitle class="text-caption">
          新消息实时入库，历史按范围回溯；命中缺失资源后按洗版规则推送 115。
        </VCardSubtitle>
      </VCardItem>
    </VCard>

    <VAlert
      v-if="message"
      :type="messageOk ? 'info' : 'warning'"
      variant="tonal"
      density="comfortable"
      class="cache-message"
    >{{ message }}</VAlert>

    <!-- 运行状态 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">运行状态</VCardTitle>
        <template #append>
          <div class="cache-head-actions">
            <VChip size="small" variant="tonal" :color="status?.enabled ? 'success' : 'default'" label>
              缓存{{ status?.enabled ? '已启用' : '未启用' }}
            </VChip>
            <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="refreshAll">
              刷新状态
            </VBtn>
          </div>
        </template>
      </VCardItem>
      <VCardText class="cache-body">
        <!-- 2×2 统计块：标签 10.5px 灰 + 值 14px 粗体（与面板同一底色/边框口径） -->
        <div class="cache-stats">
          <div class="cache-stat">
            <div class="cache-stat-label">已缓存消息</div>
            <div class="cache-stat-value">{{ fmtCount(status?.total ?? 0) }}</div>
          </div>
          <div class="cache-stat">
            <div class="cache-stat-label">缓存频道</div>
            <div class="cache-stat-value">{{ status?.chats ?? 0 }}</div>
          </div>
          <div class="cache-stat">
            <div class="cache-stat-label">同步</div>
            <div class="cache-stat-value">{{ status?.sync?.running ? '进行中' : '空闲' }}</div>
          </div>
          <div class="cache-stat">
            <div class="cache-stat-label">洗版回搜</div>
            <div class="cache-stat-value">{{ status?.settings?.wash_rules?.enabled ? '已启用' : '已关闭' }}</div>
          </div>
        </div>
        <!-- 明细小字：统计块下方一行（同步位点 / 回搜最近检查） -->
        <div class="cache-status-sub">
          <span v-if="status?.sync?.running">
            正在同步频道 {{ chatLabel(status.sync.chat_id) }}（{{ syncModeLabel(status.sync.mode) }}）
            <template v-if="status.sync.started_at"> · 开始于 {{ fmtTime(status.sync.started_at) }}</template>
            · 已扫描 {{ status.sync.processed ?? 0 }} · 新增 {{ status.sync.inserted ?? 0 }}
          </span>
          <span v-else-if="status?.sync?.finished_at">
            上次同步结束 {{ fmtTime(status.sync.finished_at) }} · 新增 {{ status.sync.inserted ?? 0 }} 条
          </span>
          <span v-else>尚未执行过历史回溯同步</span>
        </div>
        <VAlert
          v-if="status?.sync?.last_error"
          type="warning"
          variant="tonal"
          density="compact"
          class="cache-hint"
        >
          {{ status?.sync?.last_error }}
        </VAlert>
      </VCardText>
    </VCard>

    <!-- 缓存频道与范围 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">缓存频道与范围</VCardTitle>
      </VCardItem>
      <VCardText class="cache-body">
        <!-- 频道 / 范围同一网格：同一行控件等高，窄屏自动单列（「每批拉取条数」不再上界面，
             配置键 cache_batch_size 仍随设置读写与回传） -->
        <div class="cache-fields">
          <div class="cache-field">
            <VSelect
              v-model="settings.chat_ids"
              :items="selectItems"
              item-title="title"
              item-value="value"
              label="缓存频道 / 群组"
              multiple
              chips
              closable-chips
              density="compact"
              variant="outlined"
              hide-details
              @update:model-value="syncSettingsToForm"
            />
          </div>

          <div class="cache-field">
            <VSelect
              v-model="settings.sync_mode"
              :items="syncModes"
              item-title="title"
              item-value="value"
              label="历史回溯范围"
              density="compact"
              variant="outlined"
              hide-details
              @update:model-value="syncSettingsToForm"
            />
          </div>

          <div v-if="settings.sync_mode === 'relative'" class="cache-field">
            <VTextField
              v-model="settings.sync_days"
              label="回溯天数"
              type="number"
              suffix="天"
              density="compact"
              variant="outlined"
              hide-details
              @update:model-value="syncSettingsToForm"
            />
          </div>

          <div v-if="settings.sync_mode === 'absolute'" class="cache-field">
            <div class="cache-dates">
              <VTextField
                v-model="settings.start_date"
                label="起始日期"
                placeholder="2026-01-01"
                density="compact"
                variant="outlined"
                hide-details
                @update:model-value="syncSettingsToForm"
              />
              <VTextField
                v-model="settings.end_date"
                label="结束日期"
                placeholder="2026-01-31"
                density="compact"
                variant="outlined"
                hide-details
                @update:model-value="syncSettingsToForm"
              />
            </div>
          </div>
        </div>

        <!-- 此处只留保存动作 -->
        <div class="cache-actions">
          <VBtn
            color="primary"
            variant="flat"
            prepend-icon="mdi-content-save-outline"
            :loading="busy === 'save'"
            @click="saveSettings"
          >
            保存缓存设置（即时生效）
          </VBtn>
          <span class="cache-hint">设置直接写入插件配置；开关与其它模块设置随底部「保存配置」持久化。</span>
        </div>
      </VCardText>
    </VCard>

    <!-- 缓存检索 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">缓存检索</VCardTitle>
      </VCardItem>
      <VCardText class="cache-body">
        <div class="cache-field">
          <div class="cache-search">
            <VTextField
              v-model="keyword"
              label="片名关键词"
              placeholder="青与碧"
              density="compact"
              variant="outlined"
              hide-details
              class="cache-search-input"
              @keyup.enter="doSearch"
            />
            <VBtn variant="tonal" prepend-icon="mdi-magnify" :loading="busy === 'search'" @click="doSearch">
              检索
            </VBtn>
          </div>
          <div class="cache-summary">
            <div class="cache-summary-line">
              检索本地缓存（不访问 TG）：先按归一标题命中，再退回全文模糊，用来验证「订阅回搜能不能命中」。
            </div>
            <div class="cache-tags">
              <span class="cache-tag">手动触发</span>
              <span class="cache-tag">归一标题优先</span>
              <span class="cache-tag">全文模糊兜底</span>
              <span class="cache-tag">只读不推送</span>
            </div>
          </div>
          <div class="cache-note">
            命中只读展示缓存原文与链接数；空结果说明该片没被缓存覆盖，先到「缓存管理」跑一次回溯同步。
          </div>
        </div>

        <VTable v-if="searchItems.length" density="compact" class="cache-table">
          <thead>
            <tr>
              <th>媒体</th>
              <th class="cache-nowrap">来源</th>
              <th class="cache-nowrap">链接</th>
              <th class="cache-nowrap">消息时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in searchItems" :key="`s-${item.chat_id}-${item.message_id}`">
              <td>
                <div>{{ searchName(item) }}</div>
                <div class="cache-dim cache-text">{{ item.text }}</div>
              </td>
              <td class="cache-nowrap cache-dim">{{ chatLabel(item.chat_id) }}</td>
              <td class="cache-nowrap">
                <VChip v-if="(item.links || []).length" size="x-small" variant="tonal" color="success" label>
                  {{ item.links.length }} 个
                </VChip>
                <span v-else class="cache-dim">无</span>
              </td>
              <td class="cache-nowrap cache-dim">{{ fmtTime(item.message_date) || '—' }}</td>
            </tr>
          </tbody>
        </VTable>
        <div v-else-if="searchDone" class="cache-empty">没有命中缓存记录（换关键词，或先执行一次历史回溯同步）</div>
      </VCardText>
    </VCard>

    <!-- 缓存管理 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">缓存管理</VCardTitle>
      </VCardItem>
      <VCardText class="cache-body">
        <div class="cache-field">
          <div class="cache-actions">
            <VBtn
              variant="tonal"
              prepend-icon="mdi-database-arrow-down-outline"
              :loading="busy === 'sync'"
              :disabled="!status?.enabled || Boolean(status?.sync?.running)"
              @click="startSync"
            >
              开始回溯同步
            </VBtn>
            <VBtn
              variant="tonal"
              prepend-icon="mdi-stop-circle-outline"
              :disabled="!status?.sync?.running"
              @click="cancelSync"
            >
              停止同步
            </VBtn>
            <VBtn
              variant="tonal"
              color="error"
              prepend-icon="mdi-database-remove-outline"
              :disabled="!status?.enabled || !(status?.chats > 0)"
              @click="clearDialog = true"
            >
              清空缓存
            </VBtn>
            <!-- 增量同步定时并入按钮行（同一行、垂直居中，窄屏自动换行堆叠） -->
            <VTextField
              v-model="settings.cron"
              label="增量同步定时（cron）"
              density="compact"
              variant="outlined"
              hide-details
              class="cache-cron-input"
              @update:model-value="syncSettingsToForm"
            />
          </div>
          <div class="cache-hint">
            回溯同步在后台线程执行，界面可随时刷新查看进度；清空只删缓存与同步位点，下次回溯会重新拉取。
          </div>
        </div>

        <VTable density="compact" class="cache-table">
          <thead>
            <tr>
              <th>频道</th>
              <th class="cache-nowrap">ID</th>
              <th class="cache-nowrap">缓存条数</th>
              <th class="cache-nowrap">最新消息</th>
              <th class="cache-nowrap">同步位点</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in status?.channels || []" :key="`ch-${item.chat_id}`">
              <td>{{ item.name || '(未知频道)' }}</td>
              <td class="cache-nowrap cache-mono">{{ item.chat_id }}</td>
              <td class="cache-nowrap">{{ item.count }}</td>
              <td class="cache-nowrap cache-dim">{{ fmtTime(item.latest_date) || '—' }}</td>
              <td class="cache-nowrap cache-dim">{{ item.cursor || '—' }}</td>
            </tr>
            <tr v-if="!(status?.channels || []).length">
              <td colspan="5" class="cache-empty">还没有缓存频道，先在上方选择频道并保存设置</td>
            </tr>
          </tbody>
        </VTable>
      </VCardText>
    </VCard>

    <div class="cache-hint">
      存储占用：缓存的是净化后的消息全文与识别字段（片名 / 年份 / 季集 / 链接），单条约 1~2 KB；
      单频道万级消息约几十 MB，由 MoviePilot 的插件数据库承载，不会影响宿主业务数据。
    </div>

    <!-- 清空确认 -->
    <VDialog v-model="clearDialog" max-width="420">
      <VCard>
        <VCardTitle class="text-subtitle-1">确认清空缓存？</VCardTitle>
        <VCardText class="cache-dialog-text">
          将删除全部缓存频道（{{ status?.chats ?? 0 }} 个）已归档的消息与同步位点，共 {{ status?.total ?? 0 }} 条。
          此操作不可撤销，下次回溯会重新从 TG 拉取。
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="clearDialog = false">取消</VBtn>
          <VBtn color="error" variant="flat" :loading="busy === 'clear'" @click="doClear">确认清空</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>

</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPluginApi, postPluginApi, putPluginApi, unwrap } from '../api'

/**
 * ⑤ 历史消息缓存面板。
 *
 * 数据流：缓存设置（频道 / 范围 / cron）走 `/cache/settings` 专用接口，
 * 保存即归一、即时生效；但与「资源监控」一致，这些键**同时写回主表单**
 * （宿主「保存配置」是整份覆盖，表单里没有的键会被清掉）。
 * 推送目标固定 115 网盘（与「资源监控」同一口径），界面上不再提供选择。
 * 状态 / 统计 / 检索只读，回溯同步与订阅检查是触发型接口。
 *
 * 纪律（沿用全项目约定）：
 * - 模板/脚本用到的变量全部在 script setup 声明 ref（P1 踩过未声明引用的坑）；
 * - 重入保护只留在按钮处理器，内部 fetch 函数无保护（避免 busy 期间静默丢请求）；
 * - 新增配置项必须同步进 useConfigForm.js 的 configDefaults（保存是整份覆盖）。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
})

const form = computed(() => props.config.form)

const status = ref(null)
const loading = ref(false)
const busy = ref('')
const message = ref('')
const messageOk = ref(true)
const dialogs = ref([])

// 推送目标固定为 115 网盘：不再暴露「命中推送目标」下拉，保存时一律发 pan115（后端 DESTINATION_VALUES 合法值）
const FIXED_DESTINATION = 'pan115'

// ---------------------------------------------------------------- 洗版规则模型
// 与后端 services/quality.py 的默认规则保持一致；后端会返回归一化结果，
// 这里只负责「首次打开 / 后端缺字段」时的兜底结构，保证 UI 可编辑。
const settings = ref({
  chat_ids: [],
  sync_mode: 'relative',
  sync_days: 30,
  start_date: '',
  end_date: '',
  batch_size: 200,
  cron: '0 */6 * * *',
})
const syncModes = ref([
  { value: 'all', title: '所有消息（全量）' },
  { value: 'relative', title: '最近 N 天' },
  { value: 'absolute', title: '指定日期区间' },
])

const keyword = ref('')
const searchItems = ref([])
const searchDone = ref(false)

const clearDialog = ref(false)

let refreshTimer = null

function setMessage(text, ok = true) {
  message.value = text || ''
  messageOk.value = ok
}

// ------------------------------------------------------------------ 表单同步

function syncSettingsToForm() {
  // 这些键必须留在主表单里：宿主「保存配置」整份覆盖，表单没有的字段会被清空
  form.value.cache_chat_ids = (settings.value.chat_ids || []).map(Number).filter(Boolean)
  form.value.cache_destination = FIXED_DESTINATION
  form.value.cache_sync_mode = settings.value.sync_mode
  form.value.cache_sync_days = Number(settings.value.sync_days) || 30
  form.value.cache_batch_size = Number(settings.value.batch_size) || 200
  form.value.cache_cron = settings.value.cron
}

function applySettings(data) {
  const source = data && typeof data === 'object' ? data : {}
  settings.value = {
    chat_ids: Array.isArray(source.chat_ids) ? source.chat_ids.map(Number).filter(Boolean) : [],
    sync_mode: source.sync_mode || 'relative',
    sync_days: Number(source.sync_days) || 30,
    start_date: '',
    end_date: '',
    batch_size: Number(source.batch_size) || 200,
    cron: source.cron || '0 */6 * * *',
  }
  if (Array.isArray(source.sync_modes) && source.sync_modes.length) syncModes.value = source.sync_modes
  syncSettingsToForm()
}

// ------------------------------------------------------------------ 数据加载（无重入保护，供按钮与内部调用共用）

async function loadSettings() {
  try {
    applySettings(unwrap(await getPluginApi(props.api, props.pluginId, 'cache/settings', { timeoutMs: 15000 })))
  } catch (err) {
    setMessage(err?.message || '读取缓存设置失败', false)
  }
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'cache/status', { timeoutMs: 20000 }))
  } catch (err) {
    setMessage(err?.message || '读取缓存状态失败', false)
  }
}

async function loadDialogs() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'telegram/dialogs', { timeoutMs: 15000 }))
    dialogs.value = data?.dialogs || []
  } catch {
    // 对话列表拉不到不影响缓存设置（可手动输 ID）
    dialogs.value = []
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadSettings(), loadStatus(), loadDialogs()])
    // 刷新成功不再弹蓝色 info 提示（load* 内部失败仍会显示 warning，错误提示保留）
  } finally {
    loading.value = false
  }
}

// ------------------------------------------------------------------ 设置保存

async function saveSettings() {
  if (busy.value) return
  busy.value = 'save'
  setMessage('正在保存缓存设置…')
  try {
    const payload = {
      enabled: Boolean(form.value.cache_enabled),
      chat_ids: (settings.value.chat_ids || []).map(Number).filter(Boolean),
      // 推送目标固定 115 网盘，不再跟随界面（后端 destination 合法值：smart/pan115/tg_forward/none）
      destination: FIXED_DESTINATION,
      sync_mode: settings.value.sync_mode,
      sync_days: Number(settings.value.sync_days) || 30,
      batch_size: Number(settings.value.batch_size) || 200,
      cron: String(settings.value.cron || '').trim() || '0 */6 * * *',
    }
    applySettings(unwrap(await putPluginApi(
      props.api, props.pluginId, 'cache/settings', payload, { timeoutMs: 30000 },
    )))
    setMessage('缓存设置已保存（即时生效）')
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '保存缓存设置失败', false)
  } finally {
    busy.value = ''
  }
}

// ------------------------------------------------------------------ 同步与清空

async function startSync() {
  if (busy.value) return
  busy.value = 'sync'
  setMessage('正在启动历史回溯同步…')
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'cache/sync', {
      chat_ids: [],
      mode: settings.value.sync_mode,
      days: Number(settings.value.sync_days) || 30,
      start: settings.value.start_date || '',
      end: settings.value.end_date || '',
    }, { timeoutMs: 30000 }))
    setMessage(data?.message || (data?.started ? '同步已启动' : '同步未启动'), Boolean(data?.started))
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '启动同步失败', false)
  } finally {
    busy.value = ''
  }
}

async function cancelSync() {
  if (busy.value) return
  busy.value = 'cancel'
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'cache/cancel', {}, { timeoutMs: 15000 }))
    setMessage(data?.message || '已请求停止同步', Boolean(data?.stopped))
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '停止同步失败', false)
  } finally {
    busy.value = ''
  }
}

async function doClear() {
  if (busy.value) return
  busy.value = 'clear'
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'cache/clear', { chat_ids: [] }, { timeoutMs: 30000 }))
    clearDialog.value = false
    setMessage(data?.message || '缓存已清空')
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '清空缓存失败', false)
  } finally {
    busy.value = ''
  }
}

// ------------------------------------------------------------------ 检索与订阅检查

async function doSearch() {
  if (busy.value) return
  const word = String(keyword.value || '').trim()
  if (!word) {
    setMessage('请输入要检索的片名关键词', false)
    return
  }
  busy.value = 'search'
  searchDone.value = false
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'cache/search', { keyword: word, limit: 50 }, { timeoutMs: 20000 },
    ))
    searchItems.value = data?.items || []
    searchDone.value = true
    setMessage(`检索完成：命中 ${data?.total ?? searchItems.value.length} 条`)
  } catch (err) {
    searchItems.value = []
    searchDone.value = true
    setMessage(err?.message || '检索失败', false)
  } finally {
    busy.value = ''
  }
}

// ------------------------------------------------------------------ 展示辅助

const dialogOptions = computed(() =>
  (dialogs.value || []).map(item => ({
    title: `${item.name}（${item.type}）`,
    value: Number(item.id),
  })),
)

// 下拉选项 = 对话列表 + 已保存 / 状态里的 ID（缓存里没有的 ID 仍兜底显示，老配置不变空白）
const selectItems = computed(() => {
  const items = dialogOptions.value.slice()
  const known = new Set(items.map(item => item.value))
  const extra = [
    ...(settings.value.chat_ids || []),
    ...((status.value?.channels || []).map(item => item.chat_id)),
  ]
  for (const raw of extra) {
    const id = Number(raw)
    if (id && !known.has(id)) {
      const name = chatNameMap.value[id]
      items.push({ title: name ? `${name}（${id}）` : String(id), value: id })
      known.add(id)
    }
  }
  return items
})

const chatNameMap = computed(() => {
  const map = {}
  for (const item of (status.value?.channels || [])) {
    if (item.name) map[item.chat_id] = item.name
  }
  for (const item of (dialogs.value || [])) {
    const id = Number(item.id)
    if (id && !map[id]) map[id] = item.name
  }
  return map
})

function chatLabel(chatId) {
  const id = Number(chatId)
  if (!id) return '—'
  const name = chatNameMap.value[id]
  return name ? `${name}（${id}）` : String(id)
}

function syncModeLabel(mode) {
  const found = syncModes.value.find(item => item.value === mode)
  return found ? found.title : (mode || '')
}

// 媒体列：片名（年份）+ SxxExx
function searchName(item) {
  const year = item.year ? ` (${item.year})` : ''
  let name = `${item.title || '(未识别)'}${year}`
  if (item.season || item.episode) {
    const s = String(item.season ?? 1).padStart(2, '0')
    const e = String(item.episode ?? 0).padStart(2, '0')
    name += ` S${s}E${e}`
  }
  return name
}

function fmtTime(value) {
  return String(value || '').replace('T', ' ')
}

// 统计块数字：千分位（不依赖 locale，避免部分环境分隔符不一致）
function fmtCount(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '0'
  return String(Math.trunc(num)).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

onMounted(async () => {
  await refreshAll()
  // 同步在后台线程跑，状态卡保持新鲜（统计查询很轻，10 秒一次）
  refreshTimer = window.setInterval(loadStatus, 10000)
})

onUnmounted(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.cache-pane { display: flex; flex-direction: column; gap: 8px; }
/* 分区卡的外观与内边距：有底色 + 1px 描边的 10px 圆角块（对齐效果图的分区语言，不再与对话框同底）。
   Vuetify 的 flat 卡片会把背景重置成 surface，故用 !important 压过它；
   描边用 on-surface 的显式 alpha，避免主题变量缺失时整条 border 声明失效（计算值 0px） */
.cache-card {
  background: rgba(var(--v-theme-on-surface), 0.04) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10) !important;
  border-radius: 10px;
}
/* 内边距统一压到 10/12（压过 Vuetify 直系子元素的 16/24）；标题区与正文区相邻处只留一份，
   模板里不再用 pt-0 之类的工具类叠加 */
.cache-card > .v-card-item { padding: 10px 12px; }
.cache-card > .v-card-title { padding: 10px 12px; }
.cache-card > .v-card-text { padding: 10px 12px; }
.cache-card > .v-card-item + .v-card-text,
.cache-card > .v-card-title + .v-card-text { padding-top: 0; }
.cache-message { font-size: 13px; }
/* 卡片内容：纵向堆叠统一 8px（上下内边距由 .cache-card > .v-card-text 统一控制） */
.cache-body { display: flex; flex-direction: column; gap: 8px; }
/* 运行状态卡头部：状态徽章 + 刷新按钮同一行 */
.cache-head-actions { display: flex; align-items: center; gap: 6px; }
/* 统计条：一行 4 个（与订阅中心/豆瓣中心一致），窄屏回落 2×2 */
.cache-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
@media (max-width: 760px) {
  .cache-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.cache-stat {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  padding: 7px 9px;
  min-width: 0;
}
.cache-stat-label {
  font-size: 10.5px;
  line-height: 1.4;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.cache-stat-value { font-size: 14px; font-weight: 600; line-height: 1.35; }
.cache-status-sub {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
  font-size: 12px;
  line-height: 1.5;
  opacity: 0.7;
}
/* 统计块下方两段小字之间的分隔点 */
.cache-dot { opacity: 0.5; }
/* 频道 / 范围：等宽自适应列，窄屏自动单列（与「资源监控」同一网格口径） */
.cache-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 8px;
}
/* 订阅回搜 / 跳过首次搜索：并排两列面板，窄屏一列 */
@media (max-width: 600px) {
  .cache-toggles { grid-template-columns: 1fr; }
}
.cache-switch-row .cache-hint { flex: 1 1 260px; min-width: 0; }
/* 按钮行里的 cron 输入：约 200px 宽、垂直居中；窄屏换行时独占一行而不是被压扁 */
.cache-cron-input { flex: 0 0 200px; width: 200px; min-width: 0; }
/* 推送节流的两个数字输入（每批条数 / 批间隔）：固定宽度，说明文字填满剩余 */
.cache-num-input { flex: 0 0 140px; width: 140px; min-width: 0; }
@media (max-width: 760px) {
  .cache-cron-input { flex: 1 1 200px; width: auto; }
  .cache-num-input { flex: 1 1 140px; width: auto; }
}
/* 逻辑分组：组内纵向 4px（提示文字与上方控件固定 4px） */
.cache-field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.cache-dates { display: flex; gap: 6px; min-width: 0; }
.cache-dates > * { flex: 1 1 0; min-width: 0; }
/* 说明区统一口径：一行 11px 摘要 + 关键词 chip + 至多两行补充小字
   （对齐参考图「豆瓣中心」的紧凑信息带，替代原来 5-8 行的长段落） */
.cache-summary { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.cache-summary-line {
  font-size: 11px;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.72);
}
.cache-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.cache-tag {
  padding: 1px 7px;
  font-size: 11px;
  line-height: 1.5;
  white-space: nowrap;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10);
  background: rgba(255, 255, 255, 0.03);
  color: rgba(var(--v-theme-on-surface), 0.68);
}
/* 补充细节：11px 灰字，控制在 1-2 行 */
.cache-note {
  font-size: 11px;
  line-height: 1.55;
  color: rgba(var(--v-theme-on-surface), 0.52);
}
.cache-hint {
  font-size: 12px;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.cache-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
/* 行内按钮与开关不参与收缩：否则「按钮 + cron 输入」同排时按钮会被压扁、边框互相压住 */
.cache-actions > .v-btn,
.cache-actions > .v-switch { flex: 0 0 auto; }
.cache-table { font-size: 12.5px; }
.cache-table .cache-nowrap { white-space: nowrap; }
.cache-mono { font-family: monospace; }
.cache-dim { opacity: 0.7; }
.cache-text {
  max-width: 520px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11.5px;
}
.cache-empty { text-align: center; padding: 16px; opacity: 0.6; }
.cache-search { display: flex; gap: 6px; align-items: center; }
.cache-search-input { flex: 1 1 auto; }
.cache-details { font-size: 12px; }
.cache-detail { opacity: 0.75; line-height: 1.7; }
.cache-dialog-text { font-size: 13px; line-height: 1.7; }

/* ------------------------------------------------------------ 洗版规则（1.13.32） */
.wash-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 0 2px 6px;
  margin-bottom: 6px;
  border-bottom: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
}

.wash-rules {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
  padding: 8px 10px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10);
  border-radius: 10px;
}

.wash-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.wash-head strong {
  font-size: 13px;
}

.wash-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-bottom: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
  cursor: grab;
}

.wash-row:last-of-type {
  border-bottom: none;
}

.wash-row-locked {
  cursor: default;
}

.wash-grip {
  font-size: 11px;
  line-height: 1;
  letter-spacing: -1px;
  color: rgba(var(--v-theme-on-surface), 0.45);
}

.wash-grip-off {
  opacity: 0.25;
}

.wash-index {
  min-width: 14px;
  font-size: 11px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.55);
}

.wash-dim {
  min-width: 62px;
  font-size: 12px;
  font-weight: 600;
}

.wash-lock {
  font-size: 10px;
  padding: 0 5px;
  border-radius: 999px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.14);
}

.wash-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.wash-chip {
  font-size: 12px;
  height: 24px;
}

.wash-chip-off {
  opacity: 0.55;
  text-decoration: line-through;
}

.wash-chip-input {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.wash-input {
  width: 42px;
  border: none;
  border-bottom: 1px dashed rgba(var(--v-theme-on-surface), 0.45);
  background: transparent;
  color: inherit;
  font-size: 11px;
  height: 16px;
  outline: none;
}

.wash-input::-webkit-outer-spin-button,
.wash-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.wash-foot {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
}

.wash-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.wash-sources {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.wash-source {
  font-size: 11px;
}

.cache-tabs {
  margin-bottom: 2px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.10);
}

.cache-tab-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
</style>
