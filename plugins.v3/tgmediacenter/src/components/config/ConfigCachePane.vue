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
          关心会话的新消息实时入库，历史消息按时间范围回溯补齐；新增订阅自动回搜缓存并推送缺失（随「保存配置」生效）。
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
          <VChip
            size="x-small"
            variant="tonal"
            :color="status?.subscribe?.event_listener ? 'success' : 'warning'"
            label
            class="ml-2"
            :title="status?.subscribe?.event_listener ? '已监听宿主新增订阅事件，新增订阅秒级回搜' : '宿主事件总线不可用，仅按定时检查（默认每 5 分钟）'"
          >
            {{ status?.subscribe?.event_listener ? '实时回搜已启用' : '仅定时检查' }}
          </VChip>
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
            <div class="cache-hint">
              与「资源监控」的监听频道互相独立：只缓存不监控、或两者重叠都可以。
              看不到想要的会话，先到「TG 凭证」页刷新对话列表再点「刷新状态」。
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
            <VSwitch
              v-model="settings.backfill_enabled"
              color="primary"
              hide-details
              inset
              @update:model-value="syncSettingsToForm"
            >
              <template #label><span class="cache-switch-label">存量补扫（定时反扫缓存补缺集）</span></template>
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
            label="订阅兜底检查定时（cron）"
            density="compact"
            variant="outlined"
            hide-details
            @update:model-value="syncSettingsToForm"
          />
          <VTextField
            v-model="settings.backfill_cron"
            label="存量补扫定时（cron）"
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
        <VCardTitle class="text-subtitle-2">订阅回搜</VCardTitle>
      </VCardItem>
      <VCardText>
        <div class="cache-hint">
          实时路径：MoviePilot 新增订阅 → 插件收到订阅事件 → 防抖后<strong>按该订阅</strong>回搜缓存（删除后重新添加同样回搜，
          已推过的由命中流水拦掉，不会重复推送）。兜底路径：定时对比订阅快照（默认每 30 分钟，
          用于插件离线期间的新增订阅——事件不会补发）。命中后逐条判缺失（<strong>以媒体库逐集比对为准</strong>，
          未订阅的按门禁跳过；媒体库不可用时才退回订阅缺集数）→ 过滤无链接 / 已推送 →
          入推送队列（同一目标合并下发的链接数不超过 20 条）→ 通知结果（含跳过原因与媒体库未收录原因，一条没推也会说明原因）。
          首次运行只建立基线。
          <br>
          媒体库查询按<strong>片名+年份 → 仅片名 → 名称变体</strong>逐层放宽：
          宿主按「片名 + 年份」精确匹配，资源名里的年份/名称与媒体库刮削结果不一致时会被判成「库里没有」，
          逐层放宽容忍这类偏差（第三层用「片名 (年份)」等少量候选名各做一次定向查询，代价与媒体库规模无关；
          放宽命中会复核库内年份，同名不同年的翻拍剧不会被误判「已有」）。
        </div>
        <div class="cache-actions">
          <span class="cache-hint">缺失判断：</span>
          <VChip size="small" variant="tonal" :color="status?.matcher?.mediaserver_available ? 'success' : 'default'" label>
            媒体服务器{{ status?.matcher?.mediaserver ? `（${status.matcher.mediaserver}）` : '未配置' }}
          </VChip>
          <VChip size="small" variant="tonal" :color="status?.matcher?.queries_available ? 'info' : 'default'" label>
            订阅 {{ status?.matcher?.subscriptions ?? 0 }}
          </VChip>
          <span class="cache-hint">徽章随状态每 10 秒自动刷新</span>
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
        <div class="cache-hint">
          「立即检查」= 手动跑一次快照对比，用于升级后补跑、排查漏推送；
          日常新增订阅走上面的实时事件路径，不需要手动点。
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

    <!-- 存量补扫 -->
    <VCard flat class="cache-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">存量补扫</VCardTitle>
      </VCardItem>
      <VCardText>
        <div class="cache-hint">
          反扫缓存补缺集：定时捞出<strong>水位之后新入库</strong>的缓存消息，逐条判缺失
          （已订阅 + 媒体库缺，与监控同款判定）→ 过前向闸门（PT 在途不抢）→ 入队推送。
          判重按命中流水：一条消息无论被监控 / 回搜 / 补扫哪条路推过，都只推一次。
          <br>
          首次开启只建立水位基线（不翻历史）；想补历史缺口用「全量补扫」手动触发
          （后台分批跑，可随时停止）。推送仅在真的推了时发一条汇总通知，没推不打扰。
        </div>
        <div class="cache-actions">
          <VChip size="small" variant="tonal" :color="status?.backfill?.enabled ? 'success' : 'default'" label>
            {{ status?.backfill?.enabled ? '定时已开启' : '定时未开启' }}
          </VChip>
          <VChip size="small" variant="tonal" :color="status?.backfill?.running ? 'info' : 'default'" label>
            {{ status?.backfill?.running ? (status.backfill.full ? '全量扫描中' : '增量扫描中') : '空闲' }}
          </VChip>
          <VChip v-if="status?.backfill?.watermark" size="small" variant="tonal" label>
            水位 {{ status.backfill.watermark }}
          </VChip>
        </div>
        <div v-if="status?.backfill?.running" class="cache-actions">
          <span class="cache-hint">
            已扫 {{ status.backfill.processed ?? 0 }} 条 · 推送 {{ status.backfill.pushed ?? 0 }} 条 ·
            跳过 {{ status.backfill.skipped ?? 0 }} 条（30 秒自动刷新）
          </span>
          <VBtn
            variant="tonal"
            prepend-icon="mdi-stop-circle-outline"
            :loading="busy === 'backfillCancel'"
            @click="cancelBackfill"
          >
            停止补扫
          </VBtn>
        </div>
        <div class="cache-actions">
          <VBtn
            variant="tonal"
            prepend-icon="mdi-refresh-circle"
            :loading="busy === 'backfill'"
            :disabled="!status?.enabled || Boolean(status?.backfill?.running)"
            @click="startBackfill(false)"
          >
            立即增量补扫
          </VBtn>
          <VBtn
            variant="tonal"
            prepend-icon="mdi-database-search-outline"
            :loading="busy === 'backfill'"
            :disabled="!status?.enabled || Boolean(status?.backfill?.running)"
            @click="startBackfill(true)"
          >
            全量补扫一次
          </VBtn>
        </div>
        <div v-if="backfillSummary" class="cache-hint">{{ backfillSummary }}</div>
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

const settings = ref({
  chat_ids: [],
  destination: 'smart',
  sync_mode: 'relative',
  sync_days: 30,
  start_date: '',
  end_date: '',
  batch_size: 200,
  subscribe_enabled: true,
  backfill_enabled: false,
  backfill_cron: '*/30 * * * *',
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
  form.value.cache_backfill_enabled = Boolean(settings.value.backfill_enabled)
  form.value.cache_backfill_cron = settings.value.backfill_cron
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
    backfill_enabled: Boolean(source.backfill_enabled),
    backfill_cron: source.backfill_cron || '*/30 * * * *',
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
      backfill_enabled: Boolean(settings.value.backfill_enabled),
      backfill_cron: String(settings.value.backfill_cron || '').trim() || '*/30 * * * *',
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

// ------------------------------------------------------------------ 存量补扫

async function startBackfill(full) {
  if (busy.value) return
  busy.value = 'backfill'
  setMessage(full ? '正在启动全量补扫…' : '正在启动增量补扫…')
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'cache/backfill/start', { full: Boolean(full) },
      { timeoutMs: 30000 },
    ))
    setMessage(data?.message || (data?.started ? '补扫已启动' : '补扫未启动'), Boolean(data?.started))
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '启动补扫失败', false)
  } finally {
    busy.value = ''
  }
}

async function cancelBackfill() {
  if (busy.value) return
  busy.value = 'backfillCancel'
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'cache/backfill/cancel', {}, { timeoutMs: 15000 },
    ))
    setMessage(data?.message || '已请求停止补扫', Boolean(data?.stopped))
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '停止补扫失败', false)
  } finally {
    busy.value = ''
  }
}

const backfillSummary = computed(() => {
  const bf = status.value?.backfill
  if (!bf) return ''
  if (bf.running) return ''
  if (!bf.last_run_at) return '尚未运行过（开启定时后按 cron 自动增量；首次运行只建立水位基线）'
  return `上次运行 ${bf.last_run_at}：推送 ${bf.last_run_pushed ?? 0} 条，跳过 ${bf.last_run_skipped ?? 0} 条`
})

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
