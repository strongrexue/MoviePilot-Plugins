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
          把指定频道 / 群组的历史消息归档到本地库：关心会话的新消息实时入库，历史消息按时间范围回溯补齐；
          MoviePilot 新增订阅时自动回搜缓存，命中且缺失则推送（开关随底部「保存配置」生效）。
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
          <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="refreshAll">
            刷新状态
          </VBtn>
        </template>
      </VCardItem>
      <VCardText>
        <div class="cache-status">
          <VChip size="small" variant="tonal" :color="status?.enabled ? 'success' : 'default'" label>
            缓存{{ status?.enabled ? '已启用' : '未启用' }}
          </VChip>
          <VChip size="small" variant="tonal" color="info" label>
            缓存频道 {{ status?.chats ?? 0 }}
          </VChip>
          <VChip size="small" variant="tonal" color="primary" label>
            已缓存 {{ status?.total ?? 0 }} 条
          </VChip>
          <VChip
            size="small"
            variant="tonal"
            :color="status?.sync?.running ? 'warning' : 'success'"
            label
          >
            同步{{ status?.sync?.running ? '进行中' : '空闲' }}
          </VChip>
          <VChip
            size="small"
            variant="tonal"
            :color="status?.subscribe?.enabled ? 'success' : 'default'"
            label
          >
            订阅回搜{{ status?.subscribe?.enabled ? '已开启' : '已关闭' }}
          </VChip>
          <VChip v-if="status?.sync?.running" size="small" variant="tonal" color="info" label>
            已扫描 {{ status.sync.processed ?? 0 }} · 新增 {{ status.sync.inserted ?? 0 }}
          </VChip>
        </div>
        <div class="cache-status-sub">
          <span v-if="status?.sync?.running">
            正在同步频道 {{ chatLabel(status.sync.chat_id) }}（{{ syncModeLabel(status.sync.mode) }}）
            <template v-if="status.sync.started_at"> · 开始于 {{ fmtTime(status.sync.started_at) }}</template>
          </span>
          <span v-else-if="status?.sync?.finished_at">
            上次同步结束 {{ fmtTime(status.sync.finished_at) }} · 新增 {{ status.sync.inserted ?? 0 }} 条
          </span>
          <span v-else>尚未执行过历史回溯同步</span>
        </div>
        <div class="cache-status-sub">
          <span v-if="status?.subscribe?.last_check_at">
            订阅检查 {{ fmtTime(status.subscribe.last_check_at) }} ·
            新增订阅 {{ status.subscribe.last_check_new ?? 0 }} · 推送 {{ status.subscribe.last_check_pushed ?? 0 }} 条
          </span>
          <span v-else>订阅回搜尚未运行（首次运行只建立订阅基线）</span>
        </div>
        <VAlert
          v-if="status?.sync?.last_error || status?.subscribe?.last_error"
          type="warning"
          variant="tonal"
          density="compact"
          class="cache-hint"
        >
          {{ status?.sync?.last_error || status?.subscribe?.last_error }}
        </VAlert>
      </VCardText>
    </VCard>

    <!-- 缓存频道与范围 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">缓存频道与范围</VCardTitle>
      </VCardItem>
      <VCardText>
        <div class="cache-grid">
          <div class="cache-chats">
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
            <div class="cache-chats-add">
              <VTextField
                v-model="manualId"
                label="手动添加会话 ID"
                placeholder="-1001234567890"
                density="compact"
                variant="outlined"
                hide-details
                class="cache-chats-input"
                @keyup.enter="addManualId"
              />
              <VBtn size="small" variant="text" prepend-icon="mdi-plus" @click="addManualId">添加</VBtn>
            </div>
            <div class="cache-hint">
              与「资源监控」的监听频道互相独立：只缓存不监控、或两者重叠都可以。ID 与监控规则共用同一套会话 ID。
            </div>
          </div>

          <div class="cache-range">
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
            <VTextField
              v-if="settings.sync_mode === 'relative'"
              v-model="settings.sync_days"
              label="回溯天数"
              type="number"
              suffix="天"
              density="compact"
              variant="outlined"
              hide-details
              @update:model-value="syncSettingsToForm"
            />
            <div v-if="settings.sync_mode === 'absolute'" class="cache-dates">
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
            <div class="cache-hint">
              首次建议「最近 30 天」：全量拉几万条容易触发 TG 限流（FloodWait），插件会退避重试但耗时会拉长。
              同步按消息位点推进，重复执行只补新消息。
            </div>
          </div>

          <div class="cache-options">
            <VSelect
              v-model="settings.destination"
              :items="destinations"
              item-title="title"
              item-value="value"
              label="命中推送目标"
              density="compact"
              variant="outlined"
              hide-details
              @update:model-value="syncSettingsToForm"
            />
            <VTextField
              v-model="settings.batch_size"
              label="每批拉取条数"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              @update:model-value="syncSettingsToForm"
            />
            <VSwitch
              v-model="settings.subscribe_enabled"
              color="primary"
              hide-details
              inset
              @update:model-value="syncSettingsToForm"
            >
              <template #label><span class="cache-switch-label">订阅新增时回搜缓存</span></template>
            </VSwitch>
            <div class="cache-hint">
              推送目标决定「回搜命中」时怎么送：智能（115 可用则转存，否则仅记录）/ 115 / TG 转发 / 仅记录。
            </div>
          </div>
        </div>

        <div class="cache-grid cache-grid-cron">
          <VTextField
            v-model="settings.cron"
            label="增量同步定时（cron）"
            density="compact"
            variant="outlined"
            hide-details
            @update:model-value="syncSettingsToForm"
          />
          <VTextField
            v-model="settings.subscribe_cron"
            label="订阅检查定时（cron）"
            density="compact"
            variant="outlined"
            hide-details
            @update:model-value="syncSettingsToForm"
          />
          <div class="cache-hint">
            增量定时的作用不是「拉新消息」（实时通道已在写），而是补齐插件离线/掉线/限流期间漏掉的窗口，
            并刷新同步位点。改完需重新启用插件生效。
          </div>
        </div>

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

    <!-- 缓存管理 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">缓存管理</VCardTitle>
      </VCardItem>
      <VCardText>
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
        </div>
        <div class="cache-hint">
          回溯同步在后台线程执行，界面可随时刷新查看进度；清空只删缓存与同步位点，下次回溯会重新拉取。
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

    <!-- 缓存检索 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">缓存检索</VCardTitle>
      </VCardItem>
      <VCardText>
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
        <div class="cache-hint">
          检索本地缓存（不访问 TG）：先按归一标题匹配，再退回全文模糊；用于验证「订阅回搜能不能命中」。
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

    <!-- 订阅回搜 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">订阅回搜（对标 MA 新版）</VCardTitle>
      </VCardItem>
      <VCardText>
        <div class="cache-hint">
          流程：定时读取 MoviePilot 订阅 → 与上次快照对比出「新增订阅」→ 在缓存里按标题回搜 →
          逐条判缺失（订阅门禁 + 媒体库）→ 过滤无链接 / 已推送 → 入推送队列 → 通知结果。
          首次运行只建立基线，不会把存量订阅一次性全推。
        </div>
        <div class="cache-actions">
          <span class="cache-hint">缺失判断：</span>
          <VChip size="small" variant="tonal" :color="status?.matcher?.mediaserver_available ? 'success' : 'default'" label>
            媒体服务器{{ status?.matcher?.mediaserver ? `（${status.matcher.mediaserver}）` : '未配置' }}
          </VChip>
          <VChip size="small" variant="tonal" :color="status?.matcher?.queries_available ? 'info' : 'default'" label>
            订阅 {{ status?.matcher?.subscriptions ?? 0 }}
          </VChip>
        </div>
        <div class="cache-actions">
          <VBtn
            variant="tonal"
            prepend-icon="mdi-cloud-search-outline"
            :loading="busy === 'check'"
            :disabled="!status?.enabled || !status?.subscribe?.enabled"
            @click="checkSubscriptions"
          >
            立即检查新增订阅
          </VBtn>
          <span v-if="checkResult" class="cache-hint">{{ checkResult }}</span>
        </div>
        <div v-if="checkDetails.length" class="cache-details">
          <div v-for="(item, index) in checkDetails" :key="index" class="cache-detail">
            {{ item.name }}：候选 {{ item.candidates ?? 0 }} 条 · 推送 {{ item.pushed ?? 0 }} 条
            <template v-if="item.skipped"> · 跳过 {{ item.skipped }} 条</template>
            <template v-if="item.error"> · 失败：{{ item.error }}</template>
          </div>
        </div>
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
 * 数据流：缓存设置（频道 / 目标 / 范围 / cron）走 `/cache/settings` 专用接口，
 * 保存即归一、即时生效；但与「资源监控」一致，这些键**同时写回主表单**
 * （宿主「保存配置」是整份覆盖，表单里没有的键会被清掉）。
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
const manualId = ref('')

const settings = ref({
  chat_ids: [],
  destination: 'smart',
  sync_mode: 'relative',
  sync_days: 30,
  start_date: '',
  end_date: '',
  batch_size: 200,
  subscribe_enabled: true,
  cron: '0 */6 * * *',
  subscribe_cron: '*/5 * * * *',
})
const destinations = ref([
  { value: 'smart', title: '智能（115 可用则转存，否则仅记录）' },
  { value: 'pan115', title: '115 网盘（分享转存 / 磁力 eD2k 离线）' },
  { value: 'tg_forward', title: 'TG 转发（转发原消息到目标会话）' },
  { value: 'none', title: '仅记录（不推送）' },
])
const syncModes = ref([
  { value: 'all', title: '所有消息（全量）' },
  { value: 'relative', title: '最近 N 天' },
  { value: 'absolute', title: '指定日期区间' },
])

const keyword = ref('')
const searchItems = ref([])
const searchDone = ref(false)

const clearDialog = ref(false)
const checkResult = ref('')
const checkDetails = ref([])

let refreshTimer = null

function setMessage(text, ok = true) {
  message.value = text || ''
  messageOk.value = ok
}

// ------------------------------------------------------------------ 表单同步

function syncSettingsToForm() {
  // 这些键必须留在主表单里：宿主「保存配置」整份覆盖，表单没有的字段会被清空
  form.value.cache_chat_ids = (settings.value.chat_ids || []).map(Number).filter(Boolean)
  form.value.cache_destination = settings.value.destination
  form.value.cache_sync_mode = settings.value.sync_mode
  form.value.cache_sync_days = Number(settings.value.sync_days) || 30
  form.value.cache_batch_size = Number(settings.value.batch_size) || 200
  form.value.cache_subscribe_enabled = Boolean(settings.value.subscribe_enabled)
  form.value.cache_cron = settings.value.cron
  form.value.cache_subscribe_cron = settings.value.subscribe_cron
}

function applySettings(data) {
  const source = data && typeof data === 'object' ? data : {}
  settings.value = {
    chat_ids: Array.isArray(source.chat_ids) ? source.chat_ids.map(Number).filter(Boolean) : [],
    destination: source.destination || 'smart',
    sync_mode: source.sync_mode || 'relative',
    sync_days: Number(source.sync_days) || 30,
    start_date: '',
    end_date: '',
    batch_size: Number(source.batch_size) || 200,
    subscribe_enabled: source.subscribe_enabled !== false,
    cron: source.cron || '0 */6 * * *',
    subscribe_cron: source.subscribe_cron || '*/5 * * * *',
  }
  if (Array.isArray(source.destinations) && source.destinations.length) destinations.value = source.destinations
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
    setMessage('状态已刷新')
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
      destination: settings.value.destination,
      sync_mode: settings.value.sync_mode,
      sync_days: Number(settings.value.sync_days) || 30,
      batch_size: Number(settings.value.batch_size) || 200,
      subscribe_enabled: Boolean(settings.value.subscribe_enabled),
      cron: String(settings.value.cron || '').trim() || '0 */6 * * *',
      subscribe_cron: String(settings.value.subscribe_cron || '').trim() || '*/5 * * * *',
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

function isNumericId(value) {
  return /^-?\d+$/.test(String(value ?? '').trim())
}

function addManualId() {
  const parts = String(manualId.value || '').split(/[,，\s]+/).map(part => part.trim()).filter(Boolean)
  const added = []
  for (const part of parts) {
    if (!isNumericId(part)) continue
    const id = Number(part)
    if (id && !settings.value.chat_ids.includes(id)) {
      settings.value.chat_ids.push(id)
      added.push(id)
    }
  }
  manualId.value = ''
  syncSettingsToForm()
  if (!added.length) {
    setMessage('没有可添加的数字 ID（检查格式，如 -1001234567890）', false)
  } else {
    setMessage(`已添加 ${added.length} 个会话 ID（记得点「保存缓存设置」）`)
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

async function checkSubscriptions() {
  if (busy.value) return
  busy.value = 'check'
  checkDetails.value = []
  setMessage('正在检查新增订阅并回搜缓存…')
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'cache/check_subscriptions', {}, { timeoutMs: 60000 },
    ))
    checkResult.value = data?.message || ''
    checkDetails.value = data?.details || []
    setMessage(data?.message || '订阅检查完成', data?.checked !== false)
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '订阅检查失败', false)
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

// 下拉选项 = 对话列表 + 已选中的手动 / 状态里的 ID（否则手动加的 ID 在 chips 里显示不出名称）
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
.cache-pane { display: flex; flex-direction: column; gap: 12px; }
.cache-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.cache-message { font-size: 13px; }
.cache-status { display: flex; gap: 6px; flex-wrap: wrap; }
.cache-status-sub {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.7;
}
.cache-grid { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 14px; }
.cache-grid-cron { grid-template-columns: 1fr 1fr; margin-top: 12px; }
@media (max-width: 900px) {
  .cache-grid, .cache-grid-cron { grid-template-columns: 1fr; }
}
.cache-chats { display: flex; flex-direction: column; gap: 8px; }
.cache-chats-add { display: flex; gap: 6px; align-items: center; }
.cache-chats-input { flex: 1 1 auto; }
.cache-range { display: flex; flex-direction: column; gap: 8px; }
.cache-dates { display: flex; gap: 8px; }
.cache-options { display: flex; flex-direction: column; gap: 8px; }
.cache-switch-label { font-size: 13px; }
.cache-hint {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  line-height: 1.6;
}
.cache-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
.cache-table { font-size: 12.5px; margin-top: 12px; }
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
.cache-search { display: flex; gap: 8px; align-items: center; }
.cache-search-input { flex: 1 1 auto; }
.cache-details { margin-top: 10px; font-size: 12px; }
.cache-detail { opacity: 0.75; line-height: 1.7; }
.cache-dialog-text { font-size: 13px; line-height: 1.7; }
</style>
