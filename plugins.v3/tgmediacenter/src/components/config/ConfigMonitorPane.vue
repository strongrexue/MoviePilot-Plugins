<template>
  <div class="mon-pane">
    <!-- 启用开关 -->
    <VCard flat class="mon-card">
      <VCardItem>
        <template #prepend>
          <VSwitch v-model="form.monitor_enabled" color="primary" hide-details inset />
        </template>
        <VCardTitle class="text-subtitle-2">启用 TG 资源监控</VCardTitle>
        <VCardSubtitle class="text-caption">
          监听指定频道 / 群组的新消息，经净化与宿主识别后按规则决策，命中即入推送队列（开关随「保存配置」生效）。
        </VCardSubtitle>
      </VCardItem>
    </VCard>

    <VAlert
      v-if="message"
      :type="messageOk ? 'info' : 'warning'"
      variant="tonal"
      density="comfortable"
      class="mon-message"
    >{{ message }}</VAlert>

    <!-- 运行状态 -->
    <VCard flat class="mon-card">
      <VCardTitle class="text-subtitle-2">运行状态</VCardTitle>
      <VCardText>
        <div class="mon-status">
          <VChip size="small" variant="tonal" :color="status?.enabled ? 'success' : 'default'" label>
            监控{{ status?.enabled ? '已启用' : '未启用' }}
          </VChip>
          <VChip size="small" variant="tonal" :color="status?.pipeline?.running ? 'success' : 'warning'" label>
            流水线{{ status?.pipeline?.running ? '运行中' : '未运行' }}
          </VChip>
          <VChip size="small" variant="tonal" :color="status?.pipeline?.handler_registered ? 'success' : 'warning'" label>
            消息监听{{ status?.pipeline?.handler_registered ? '已注册' : '未注册' }}
          </VChip>
          <VChip size="small" variant="tonal" color="info" label>
            关心会话 {{ status?.watched_chats ?? 0 }}
          </VChip>
          <VChip size="small" variant="tonal" color="primary" label>
            规则 {{ status?.rules_count ?? 0 }}
          </VChip>
          <VChip size="small" variant="tonal" color="primary" label>
            队列待处理 {{ status?.pipeline?.push_pending ?? 0 }}
          </VChip>
          <VChip v-if="(status?.pipeline?.push_done ?? 0) > 0" size="small" variant="tonal" color="success" label>
            推送完成 {{ status.pipeline.push_done }}
          </VChip>
          <VChip v-if="(status?.pipeline?.push_failed ?? 0) > 0" size="small" variant="tonal" color="error" label>
            失败 {{ status.pipeline.push_failed }}
          </VChip>
        </div>
        <div class="mon-status-sub">
          <span v-if="status?.pipeline?.started_at">启动于 {{ status.pipeline.started_at }}</span>
          <span v-if="status?.pipeline?.buffered || status?.pipeline?.queued">
            缓冲 {{ status.pipeline.buffered }} · 待处理 {{ status.pipeline.queued }}
          </span>
          <span v-if="status?.gate_interval">转发冷却 {{ status.gate_interval }} 秒</span>
          <span v-if="status?.flood_remaining > 0" class="mon-flood">
            FloodWait 退避中（约 {{ status.flood_remaining }} 秒）
          </span>
        </div>
        <div class="mon-events">
          <span class="mon-events-title">事件：</span>
          <VChip size="x-small" variant="tonal" color="info" label>
            收到 {{ status?.pipeline?.events_received ?? 0 }}
          </VChip>
          <VChip size="x-small" variant="tonal" :color="(status?.pipeline?.events_watched ?? 0) > 0 ? 'success' : 'default'" label>
            命中监听 {{ status?.pipeline?.events_watched ?? 0 }}
          </VChip>
          <VChip size="x-small" variant="tonal" color="default" label>
            非监听 {{ status?.pipeline?.events_unwatched ?? 0 }}
          </VChip>
          <VChip size="x-small" variant="tonal" color="primary" label>
            已入队 {{ status?.pipeline?.messages_enqueued ?? 0 }}
          </VChip>
          <span v-if="status?.pipeline?.last_event_at" class="mon-events-last">
            最近事件 {{ status.pipeline.last_event_at }}
          </span>
        </div>
        <div v-if="(status?.watched_chat_ids?.length || 0) > 0" class="mon-sources">
          <span class="mon-events-title">关心会话：</span>
          <template v-if="(status?.pipeline?.watched_detail?.length || 0) > 0">
            <VChip
              v-for="item in status.pipeline.watched_detail"
              :key="`watch-${item.chat_id}`"
              size="x-small"
              variant="tonal"
              :color="item.resolved ? 'success' : 'error'"
              label
              class="mon-id-chip"
              :title="item.resolved ? `会话标题：${item.title}` : `反查失败：${item.error}`"
            >
              {{ item.chat_id }}<template v-if="item.resolved"> ▸ {{ item.title || '(无标题)' }}</template><template v-else> ▸ 反查失败</template>
              <span class="mon-id-purpose">［{{ purposeLabel(item.purposes) }}］</span>
            </VChip>
          </template>
          <template v-else>
            <VChip
              v-for="chatId in status.watched_chat_ids"
              :key="`watch-${chatId}`"
              size="x-small"
              variant="tonal"
              color="warning"
              label
              class="mon-id-chip"
            >
              {{ chatId }}
            </VChip>
          </template>
        </div>
        <div v-if="(status?.pipeline?.recent_sources?.length || 0) > 0" class="mon-sources">
          <span class="mon-events-title">来源 ID：</span>
          <VChip
            v-for="source in status.pipeline.recent_sources.slice(0, 12)"
            :key="`src-${source.chat_id}`"
            size="x-small"
            variant="tonal"
            :color="sourceColor(source)"
            label
            class="mon-id-chip"
            :title="`监控：${source.watched ? '是' : '否'} · 缓存：${source.cached ? '是' : '否'}`"
          >
            {{ source.chat_id }} ×{{ source.count }}
          </VChip>
          <span class="mon-events-last">绿=监控，蓝=仅缓存，灰=无关</span>
        </div>
        <VAlert
          v-if="status?.enabled && (status?.pipeline?.events_received > 0) && !(status?.pipeline?.events_watched > 0)"
          type="warning"
          variant="tonal"
          density="compact"
          class="mon-events-hint"
        >
          收到 {{ status.pipeline.events_received }} 条事件，但没有一条来自监听会话。
          常见原因：①监听 ID「反查失败」＝账号看不到该会话（ID 失效或选错，到「TG 凭证」页刷新对话后重选并保存规则）
          ②规则里选错频道（名字相近的频道多选）③账号已退出该频道（重新加入后刷新对话列表重选）。
        </VAlert>
        <VAlert
          v-if="status?.enabled && !(status?.pipeline?.events_received > 0)"
          type="warning"
          variant="tonal"
          density="compact"
          class="mon-events-hint"
        >
          还没收到任何 TG 事件：请确认 ①TG 凭证已登录且「已连接」 ②消息监听徽章为「已注册」
          ③规则监听的频道 ID 正确（可在「TG 凭证」页刷新对话列表后点条目复制 ID，或点「保存规则」后重试）。
          收到事件后这里会显示计数。
        </VAlert>
        <div class="mon-matcher">
          缺失判断：
          <VChip size="x-small" variant="tonal" :color="matcherReady ? 'success' : 'warning'" label class="mon-matcher-chip">
            媒体服务器{{ status?.matcher?.mediaserver ? `（${status.matcher.mediaserver}）` : (status?.matcher?.mediaserver_available ? '已就绪' : '未配置') }}
          </VChip>
          <VChip size="x-small" variant="tonal" color="info" label class="mon-matcher-chip">
            订阅 {{ status?.matcher?.subscriptions ?? 0 }}
          </VChip>
          <span v-if="!matcherReady" class="mon-matcher-warn">
            两项都不可用，「仅缺失」规则会因无法判断而全部跳过；请在 MoviePilot 配置媒体服务器或建立订阅。
          </span>
        </div>
        <div class="mon-actions">
          <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="refreshAll">
            刷新状态
          </VBtn>
        </div>
      </VCardText>
    </VCard>

    <!-- 规则编辑器 -->
    <VCard flat class="mon-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">监控规则</VCardTitle>
        <template #append>
          <VBtn size="small" variant="tonal" prepend-icon="mdi-plus" @click="addRule">添加规则</VBtn>
        </template>
      </VCardItem>
      <VCardText>
        <div v-if="!rules.length" class="mon-empty">
          还没有规则。点「添加规则」创建第一条：选择监听频道、推送目标，保存后立即生效。
        </div>

        <VCard
          v-for="(rule, index) in rules"
          :key="rule.id || index"
          flat
          class="mon-rule"
        >
          <VCardText>
            <div class="mon-rule-head">
              <VTextField
                v-model="rule.name"
                label="规则名称"
                density="compact"
                variant="outlined"
                hide-details
                class="mon-rule-name"
              />
              <div class="mon-rule-switch" title="关闭后该规则暂停监听（随「保存配置」生效）">
                <VSwitch v-model="rule.enabled" color="success" hide-details inset density="compact" />
                <span class="mon-switch-label">启用规则</span>
              </div>
              <VBtn
                size="small"
                variant="text"
                color="error"
                prepend-icon="mdi-delete-outline"
                @click="removeRule(index)"
              >
                删除
              </VBtn>
            </div>

            <div class="mon-rule-grid">
              <div class="mon-chats">
                <VSelect
                  v-model="rule.source_ids"
                  :items="selectItems"
                  item-title="title"
                  item-value="value"
                  label="监听频道 / 群组"
                  multiple
                  chips
                  closable-chips
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div class="mon-hint">
                  下拉项来自「TG 凭证」页的对话列表缓存；看不到想要的会话，先到「TG 凭证」页刷新对话列表再点「刷新状态」。
                </div>
              </div>

              <div class="mon-target">
                <VSelect
                  v-model="rule.destination"
                  :items="destinations"
                  item-title="title"
                  item-value="value"
                  label="推送目标"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <VSelect
                  v-if="rule.destination === 'tg_forward'"
                  v-model="rule.target_id"
                  :items="targetItems"
                  item-title="title"
                  item-value="value"
                  label="转发目标频道 / 群组"
                  density="compact"
                  variant="outlined"
                  hide-details
                  class="mon-target-id"
                />
                <div v-if="rule.destination === 'smart'" class="mon-hint">
                  智能：115 已启用且已登录时转存到 115，否则仅记录。
                </div>
                <div v-if="rule.destination === 'pan115'" class="mon-hint">
                  推送到 115（分享转存 / 磁力 / eD2k 离线），需在「115 网盘」页完成扫码登录。
                </div>
                <div v-if="rule.destination === 'tg_forward'" class="mon-hint">
                  转发原消息到所选会话；目标必须是当前账号能看到的会话。
                </div>
              </div>

              <div class="mon-match">
                <VSwitch v-model="rule.match_only_if_missing" color="primary" hide-details inset>
                  <template #label>
                    <span class="mon-switch-label">仅缺失时推送</span>
                  </template>
                </VSwitch>
                <div class="mon-hint">按 MP 媒体服务器与订阅状态判断；无法判断时命中会跳过。</div>
                <VSwitch v-model="rule.match_custom_keywords" color="primary" hide-details inset>
                  <template #label>
                    <span class="mon-switch-label">自定义关键词过滤</span>
                  </template>
                </VSwitch>
                <VCombobox
                  v-if="rule.match_custom_keywords"
                  v-model="rule.custom_keywords"
                  multiple
                  chips
                  closable-chips
                  label="关键词（任一命中即通过）"
                  density="compact"
                  variant="outlined"
                  hide-details
                  class="mon-keywords"
                />
              </div>
            </div>
          </VCardText>
        </VCard>

        <div v-if="rules.length" class="mon-actions">
          <VBtn
            color="primary"
            variant="flat"
            prepend-icon="mdi-content-save-outline"
            :loading="busy === 'save'"
            @click="saveRules"
          >
            保存规则（即时生效）
          </VBtn>
          <span class="mon-hint">规则保存在插件配置里；开关与其它模块设置随底部「保存配置」持久化。</span>
        </div>
      </VCardText>
    </VCard>

    <!-- 规则测试 -->
    <VCard flat class="mon-card">
      <VCardTitle class="text-subtitle-2">规则测试</VCardTitle>
      <VCardText>
        <VTextarea
          v-model="testText"
          label="粘贴一条频道消息原文"
          placeholder="剧名.S01E02.2160p.WEB-DL&#10;https://115.com/s/xxxxx?password=abcd"
          rows="3"
          density="compact"
          variant="outlined"
          hide-details
        />
        <div class="mon-actions">
          <VBtn
            variant="tonal"
            prepend-icon="mdi-test-tube"
            :loading="busy === 'test'"
            @click="runTest"
          >
            测试（不落库、不推送）
          </VBtn>
        </div>

        <div v-if="testResult" class="mon-test-result">
          <div class="mon-test-line">
            <strong>识别结果：</strong>
            <span v-if="testResult.recognized">
              《{{ testResult.recognized.title }}》
              <span v-if="testResult.recognized.year">（{{ testResult.recognized.year }}）</span>
              <span v-if="testResult.recognized.season"> S{{ String(testResult.recognized.season).padStart(2, '0') }}</span>
              <span v-if="testResult.recognized.episode">E{{ String(testResult.recognized.episode).padStart(2, '0') }}<template v-if="testResult.recognized.episode_end && testResult.recognized.episode_end !== testResult.recognized.episode">-E{{ String(testResult.recognized.episode_end).padStart(2, '0') }}</template></span>
              · {{ testResult.recognized.media_type === 'tv' ? '剧集' : '电影' }}
            </span>
            <span v-else class="mon-test-none">无法识别（标题格式特殊或宿主识别引擎不可用）</span>
          </div>
          <div v-if="testResult.links?.length" class="mon-test-line">
            <strong>解析到 {{ testResult.links.length }} 个链接</strong>
          </div>
          <VList density="compact" class="mon-test-list">
            <VListItem v-for="(trace, index) in testResult.rules" :key="index">
              <template #prepend>
                <VIcon
                  :icon="trace.decision === 'hit' ? 'mdi-check-circle-outline' : 'mdi-minus-circle-outline'"
                  size="18"
                  :color="trace.decision === 'hit' ? 'success' : 'warning'"
                />
              </template>
              <VListItemTitle class="mon-test-name">
                {{ trace.rule_name }}
                <VChip v-if="!trace.enabled" size="x-small" variant="tonal" color="default" label class="mon-test-off">已停用</VChip>
              </VListItemTitle>
              <VListItemSubtitle class="mon-test-msg">
                {{ decisionLabel(trace.decision) }} · {{ trace.reason }}
              </VListItemSubtitle>
            </VListItem>
          </VList>
        </div>
      </VCardText>
    </VCard>

    <!-- 命中流水 -->
    <VCard flat class="mon-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">命中流水</VCardTitle>
        <template #append>
          <VSelect
            v-model="decisionFilter"
            :items="[{ value: '', title: '全部决策' }, ...decisions]"
            item-title="title"
            item-value="value"
            density="compact"
            variant="outlined"
            hide-details
            class="mon-filter"
            @update:model-value="onDecisionFilter"
          />
        </template>
      </VCardItem>
      <VCardText>
        <VTable density="compact" class="mon-hits">
          <thead>
            <tr>
              <th class="mon-nowrap">时间</th>
              <th class="mon-nowrap">规则</th>
              <th class="mon-nowrap">来源</th>
              <th>媒体</th>
              <th class="mon-nowrap">决策</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in hits" :key="item.id">
              <td class="mon-hits-time">{{ fmtTime(item.created_at) }}</td>
              <td class="mon-nowrap">{{ item.rule_name }}</td>
              <td class="mon-hits-source">
                {{ chatTitleMap[item.chat_id] || item.chat_id }}
              </td>
              <td>
                <span v-if="item.title">{{ mediaName(item) }}</span>
                <span v-else class="mon-hits-none">—</span>
              </td>
              <td class="mon-nowrap">
                <VChip size="x-small" variant="tonal" :color="decisionColor(item.decision)" label>
                  {{ decisionLabel(item.decision) }}
                </VChip>
              </td>
              <td class="mon-hits-detail">{{ item.detail }}</td>
            </tr>
            <tr v-if="!hits.length">
              <td colspan="6" class="mon-hits-empty">暂无记录</td>
            </tr>
          </tbody>
        </VTable>
        <div class="mon-pager">
          <VBtn size="small" variant="text" :disabled="hitsPage <= 1" prepend-icon="mdi-chevron-left" @click="prevHits">
            上一页
          </VBtn>
          <span class="mon-pager-info">第 {{ hitsPage }} 页 · 共 {{ hitsTotal }} 条</span>
          <VBtn
            size="small"
            variant="text"
            :disabled="hitsPage * hitsPageSize >= hitsTotal"
            append-icon="mdi-chevron-right"
            @click="nextHits"
          >
            下一页
          </VBtn>
        </div>
      </VCardText>
    </VCard>

    <div class="mon-hint">
      风控提示：TG 个人号对外操作有频率限制，插件按「聚合窗口 + 全局冷却 + FloodWait 退避」克制发送；
      长时间大流量监控请适当调大「TG 凭证」页的个人号冷却秒数。
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPluginApi, postPluginApi, putPluginApi, unwrap } from '../api'

/**
 * ④ TG 资源监控面板。
 *
 * 数据流：规则存放在插件配置 `monitor_rules`（随主表单保存），但读写走
 * `/monitor/rules` 专用接口——保存即归一（补规则 ID）、即时生效（ensure_started），
 * 不必等插件重载。命中流水与运行态只读。
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
const destinations = ref([
  { value: 'smart', title: '智能（115 可用则转存，否则仅记录）' },
  { value: 'pan115', title: '115 网盘（分享转存 / 磁力 eD2k 离线）' },
  { value: 'tg_forward', title: 'TG 转发（转发原消息到目标会话）' },
  { value: 'none', title: '仅记录（不推送）' },
])
const decisions = ref([
  { value: 'hit', title: '已推送' },
  { value: 'skipped_not_missing', title: '不缺（已存在）' },
  { value: 'skipped_not_subscribed', title: '未订阅' },
  { value: 'skipped_unrecognized', title: '无法识别' },
  { value: 'skipped_keyword', title: '关键词未命中' },
  { value: 'skipped_no_link', title: '无链接' },
  { value: 'skipped_unknown', title: '无法判断缺失' },
  { value: 'failed', title: '处理失败' },
])
const rules = ref([])
const dialogs = ref([])

const testText = ref('')
const testResult = ref(null)

const hits = ref([])
const hitsTotal = ref(0)
const hitsPage = ref(1)
const hitsPageSize = 20
const decisionFilter = ref('')

let refreshTimer = null

function setMessage(text, ok = true) {
  message.value = text || ''
  messageOk.value = ok
}

function newRuleId() {
  return 'r' + Math.random().toString(16).slice(2, 10)
}

function blankRule() {
  return {
    id: newRuleId(),
    name: '',
    source_ids: [],
    destination: 'smart',
    target_id: '',
    match_only_if_missing: true,
    match_custom_keywords: false,
    custom_keywords: [],
    rule_type: 'client',
    web_channel_usernames: [],
    enabled: true,
  }
}

// ------------------------------------------------------------------ 数据加载（无重入保护，供按钮与内部调用共用）

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'monitor/status', { timeoutMs: 15000 }))
  } catch (err) {
    setMessage(err?.message || '读取监控状态失败', false)
  }
}

async function loadRules() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'monitor/rules', { timeoutMs: 15000 }))
    if (data?.destinations?.length) destinations.value = data.destinations
    if (data?.decisions?.length) decisions.value = data.decisions
    const list = Array.isArray(data?.rules) ? data.rules : []
    rules.value = list.map(rule => ({
      id: rule.id || newRuleId(),
      name: rule.name || '',
      source_ids: Array.isArray(rule.source_ids) ? rule.source_ids.map(Number) : [],
      destination: rule.destination || 'smart',
      target_id: rule.target_id || '',
      match_only_if_missing: rule.match_only_if_missing !== false,
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: Array.isArray(rule.custom_keywords) ? rule.custom_keywords : [],
      rule_type: rule.rule_type || 'client',
      web_channel_usernames: Array.isArray(rule.web_channel_usernames) ? rule.web_channel_usernames : [],
      enabled: rule.enabled !== false,
    }))
    syncRulesToForm()
  } catch (err) {
    setMessage(err?.message || '读取监控规则失败', false)
  }
}

async function loadDialogs() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'telegram/dialogs', { timeoutMs: 15000 }))
    dialogs.value = data?.dialogs || []
  } catch {
    // 对话列表拉不到不影响规则编辑（下拉为空，可刷新后再选）
    dialogs.value = []
  }
}

async function loadHits() {
  try {
    const params = new URLSearchParams()
    params.set('page', String(hitsPage.value))
    params.set('page_size', String(hitsPageSize))
    if (decisionFilter.value) params.set('decision', decisionFilter.value)
    const data = unwrap(await getPluginApi(
      props.api, props.pluginId, `monitor/hits?${params.toString()}`, { timeoutMs: 15000 },
    ))
    hits.value = data?.items || []
    hitsTotal.value = data?.total || 0
  } catch (err) {
    setMessage(err?.message || '读取命中流水失败', false)
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadStatus(), loadRules(), loadHits(), loadDialogs()])
    setMessage('状态已刷新')
  } finally {
    loading.value = false
  }
}

// ------------------------------------------------------------------ 规则编辑

function syncRulesToForm() {
  // 规则必须留在主表单里：宿主「保存配置」是整份覆盖，表单没有的字段会被清空
  form.value.monitor_rules = rules.value
}

function addRule() {
  rules.value.push(blankRule())
  syncRulesToForm()
}

function removeRule(index) {
  rules.value.splice(index, 1)
  syncRulesToForm()
}

async function saveRules() {
  if (busy.value) return
  busy.value = 'save'
  setMessage('正在保存规则…')
  try {
    const payload = rules.value.map(rule => ({
      id: rule.id,
      name: String(rule.name || '').trim() || '未命名规则',
      source_ids: rule.source_ids,
      destination: rule.destination,
      target_id: String(rule.target_id || '').trim(),
      match_only_if_missing: Boolean(rule.match_only_if_missing),
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: (rule.custom_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      rule_type: rule.rule_type || 'client',
      web_channel_usernames: rule.web_channel_usernames || [],
      enabled: rule.enabled !== false,
    }))
    const data = unwrap(await putPluginApi(props.api, props.pluginId, 'monitor/rules', { rules: payload }, { timeoutMs: 30000 }))
    if (Array.isArray(data?.rules)) {
      rules.value = data.rules
      syncRulesToForm()
    }
    setMessage(`已保存 ${payload.length} 条规则，监控已进入运行态`)
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '保存规则失败', false)
  } finally {
    busy.value = ''
  }
}

// ------------------------------------------------------------------ 规则测试

async function runTest() {
  if (busy.value) return
  busy.value = 'test'
  setMessage('正在测试…')
  testResult.value = null
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'monitor/test', { text: testText.value }, { timeoutMs: 30000 },
    ))
    testResult.value = data
    setMessage('测试完成（未落库、未推送）')
  } catch (err) {
    setMessage(err?.message || '测试失败', false)
  } finally {
    busy.value = ''
  }
}

// ------------------------------------------------------------------ 命中流水分页

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

// ------------------------------------------------------------------ 展示辅助

const dialogOptions = computed(() =>
  (dialogs.value || []).map(item => ({
    title: `${item.name}（${item.type}）`,
    value: Number(item.id),
  })),
)

// 下拉选项 = 对话列表 + 已保存但不在缓存里的 ID（老规则/缓存过期时保证 chips 仍能显示）
const selectItems = computed(() => {
  const items = dialogOptions.value.slice()
  const known = new Set(items.map(item => item.value))
  for (const rule of rules.value) {
    for (const raw of rule.source_ids || []) {
      const id = Number(raw)
      if (id && !known.has(id)) {
        items.push({ title: String(id), value: id })
        known.add(id)
      }
    }
  }
  return items
})

// 转发目标下拉（推送目标 = TG 转发时）：同一份对话缓存 + 已保存的目标值兜底
const targetItems = computed(() => {
  const items = dialogOptions.value.slice()
  const known = new Set(items.map(item => item.value))
  for (const rule of rules.value) {
    const id = Number(rule.target_id)
    if (id && !known.has(id)) {
      items.push({ title: String(id), value: id })
      known.add(id)
    }
  }
  return items
})

function decisionLabel(value) {
  const found = decisions.value.find(item => item.value === value)
  return found ? found.title : value
}

// 关心会话的用途标注（监控 / 缓存 / 两者）
function purposeLabel(purposes) {
  const list = Array.isArray(purposes) ? purposes : []
  return list.length ? list.join('+') : '监控'
}

// 来源会话配色：监控优先，其次缓存
function sourceColor(source) {
  if (source?.watched && source?.cached) return 'primary'
  if (source?.watched) return 'success'
  if (source?.cached) return 'info'
  return 'default'
}

function decisionColor(value) {
  if (value === 'hit') return 'success'
  if (value === 'failed') return 'error'
  if (value === 'skipped_unknown') return 'warning'
  if (value === 'skipped_not_subscribed') return 'grey'
  return 'default'
}

const matcherReady = computed(() => {
  const matcher = status.value?.matcher || {}
  return Boolean(matcher.mediaserver_available || (matcher.subscriptions ?? 0) > 0)
})

// 监听会话 ID → 反查标题（来自状态卡 watched_detail），命中流水「来源」列展示用
const chatTitleMap = computed(() => {
  const map = {}
  for (const w of (status.value?.pipeline?.watched_detail || [])) {
    if (w.resolved && w.title) map[w.chat_id] = w.title
  }
  return map
})

// 媒体列完整名：片名（年份）+ 电视剧 SxxExx（如「青与碧 (2026) S01E02」）
function mediaName(item) {
  if (!item.title) return ''
  const year = item.year ? ` (${item.year})` : ''
  let name = `${item.title}${year}`
  if (item.season || item.episode) {
    const s = String(item.season ?? 1).padStart(2, '0')
    const e = String(item.episode ?? 0).padStart(2, '0')
    name += ` S${s}E${e}`
  }
  return name
}

// 流水时间去掉 ISO 的 T 分隔（2026-10-13T11:01:08 → 2026-10-13 11:01:08）
function fmtTime(value) {
  return String(value || '').replace('T', ' ')
}

onMounted(async () => {
  await refreshAll()
  // 轻量轮询：监控是长驻进程，状态卡保持新鲜（命中流水变化慢，不轮询）
  refreshTimer = window.setInterval(loadStatus, 15000)
})

onUnmounted(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.mon-pane { display: flex; flex-direction: column; gap: 12px; }
.mon-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.mon-message { font-size: 13px; }
.mon-status { display: flex; gap: 6px; flex-wrap: wrap; }
.mon-status-sub { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px; font-size: 12px; opacity: 0.7; }
.mon-events { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 8px; font-size: 12px; }
.mon-events-title { opacity: 0.7; }
.mon-events-last { opacity: 0.6; }
.mon-events-hint { margin-top: 8px; font-size: 12px; }
.mon-sources { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 8px; font-size: 12px; }
.mon-id-chip { font-family: monospace; }
.mon-id-purpose { opacity: 0.75; }
.mon-flood { color: rgb(var(--v-theme-warning)); }
.mon-matcher { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 10px; font-size: 12px; }
.mon-matcher-chip { margin-left: 0; }
.mon-matcher-warn { color: rgb(var(--v-theme-warning)); line-height: 1.6; }
.mon-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
.mon-rule { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; margin-bottom: 10px; }
.mon-rule-head { display: flex; gap: 10px; align-items: center; }
.mon-rule-name { flex: 1 1 auto; }
.mon-rule-switch { display: flex; align-items: center; gap: 2px; }
.mon-switch-label { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.7); white-space: nowrap; }
.mon-rule-grid { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 14px; margin-top: 10px; }
@media (max-width: 900px) {
  .mon-rule-grid { grid-template-columns: 1fr; }
}
.mon-target { display: flex; flex-direction: column; gap: 8px; }
.mon-target-id { margin-top: 0; }
.mon-match { display: flex; flex-direction: column; gap: 4px; }
.mon-switch-label { font-size: 13px; }
.mon-keywords { margin-top: 4px; }
.mon-hint { margin-top: 6px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.6; }
.mon-empty {
  padding: 18px 12px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.mon-test-result { margin-top: 12px; }
.mon-test-line { font-size: 13px; margin-bottom: 4px; }
.mon-test-none { opacity: 0.7; }
.mon-test-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.mon-test-name { font-size: 13px; }
.mon-test-off { margin-left: 6px; }
.mon-test-msg { font-size: 12px; opacity: 0.75; }
.mon-filter { flex: 0 0 160px; max-width: 200px; }
.mon-hits { font-size: 12.5px; }
.mon-hits .mon-nowrap { white-space: nowrap; }
.mon-hits-time { white-space: nowrap; opacity: 0.75; }
.mon-hits-source { white-space: nowrap; opacity: 0.8; }
.mon-hits-se { margin-left: 6px; opacity: 0.75; }
.mon-hits-none { opacity: 0.4; }
.mon-hits-detail { opacity: 0.75; }
.mon-hits-empty { text-align: center; padding: 16px; opacity: 0.6; }
.mon-pager { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.mon-pager-info { font-size: 12px; opacity: 0.7; }
</style>
