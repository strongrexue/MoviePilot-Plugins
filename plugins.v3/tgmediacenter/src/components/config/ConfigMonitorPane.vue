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

    <!-- 运行状态：正文只有 2×2 统计块 + 一行小字；状态徽章与刷新按钮收进卡片头部右侧 -->
    <VCard flat class="mon-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">运行状态</VCardTitle>
        <VCardSubtitle class="text-caption">命中后推送到 115 网盘（固定）</VCardSubtitle>
        <template #append>
          <div class="mon-status-chips">
            <VChip size="small" variant="tonal" :color="status?.enabled ? 'success' : 'default'" label>
              监控{{ status?.enabled ? '已启用' : '未启用' }}
            </VChip>
            <VChip size="small" variant="tonal" :color="status?.pipeline?.running ? 'success' : 'warning'" label>
              流水线{{ status?.pipeline?.running ? '运行中' : '未运行' }}
            </VChip>
            <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="refreshAll">
              刷新状态
            </VBtn>
          </div>
        </template>
      </VCardItem>
      <VCardText>
        <div class="mon-stat-grid">
          <div class="mon-stat">
            <div class="mon-stat-label">监听规则</div>
            <div class="mon-stat-value">{{ status?.rules_count ?? 0 }}</div>
          </div>
          <div class="mon-stat">
            <div class="mon-stat-label">关心会话</div>
            <div class="mon-stat-value">{{ status?.watched_chats ?? 0 }}</div>
          </div>
          <div class="mon-stat">
            <div class="mon-stat-label">队列待处理</div>
            <div class="mon-stat-value">{{ status?.pipeline?.push_pending ?? 0 }}</div>
          </div>
          <div class="mon-stat">
            <div class="mon-stat-label">已推送</div>
            <div class="mon-stat-value">{{ status?.pipeline?.push_done ?? 0 }}</div>
          </div>
        </div>
        <!-- 唯一的一行小字：消息监听注册态（原第三个徽章）+ 启动时间 + 风控/冷却 -->
        <div class="mon-stat-foot">
          <span :class="status?.pipeline?.handler_registered ? '' : 'mon-foot-warn'">
            消息监听{{ status?.pipeline?.handler_registered ? '已注册' : '未注册' }}
          </span>
          <span v-if="status?.pipeline?.started_at">启动于 {{ status.pipeline.started_at }}</span>
          <span v-if="status?.gate_interval">转发冷却 {{ status.gate_interval }} 秒</span>
          <span v-if="status?.flood_remaining > 0" class="mon-flood">
            FloodWait 退避中（约 {{ status.flood_remaining }} 秒）
          </span>
        </div>
        <!-- 诊断：只在「仅缺失」不可判断时出现（收不到事件的两条告警已按需求移除） -->
        <div
          v-if="status?.enabled && !status?.matcher?.mediaserver && !((status?.matcher?.subscriptions ?? 0) > 0)"
          class="mon-diag-text"
        >
          缺失判断不可用（媒体服务器未配置、也没有订阅）：「仅缺失」规则会因无法判断而全部跳过。
        </div>
      </VCardText>
    </VCard>

    <!-- 规则编辑器：每条规则默认折叠，标题行即可切换 -->
    <VCard flat class="mon-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">监控规则</VCardTitle>
        <VCardSubtitle class="text-caption">命中即推送 115，规则内不再选目标</VCardSubtitle>
        <template #append>
          <VBtn size="small" variant="tonal" prepend-icon="mdi-plus" @click="addRule">添加规则</VBtn>
        </template>
      </VCardItem>
      <VCardText>
        <div v-if="!rules.length" class="mon-empty">
          还没有规则。点「添加规则」创建第一条：选择监听频道，保存后立即生效。
        </div>

        <VCard
          v-for="(rule, index) in rules"
          :key="rule.id || index"
          flat
          class="mon-rule"
        >
          <!-- 内边距全部交给头行 / 展开区自己控制（pa-0 清零 VCardText 默认 16px） -->
          <VCardText class="pa-0">
            <!-- 折叠态唯一一行：整行点击切换展开，▸/▾ 只是提示；padding 8px 10px，行高约 48-52px -->
            <div
              class="mon-rule-head"
              :class="{ 'mon-rule-head-open': isExpanded(rule) }"
              :title="isExpanded(rule) ? '点击收起这条规则的编辑表单' : '点击展开编辑这条规则'"
              @click="toggleRule(rule)"
            >
              <span class="mon-rule-toggle">{{ isExpanded(rule) ? '▾' : '▸' }}</span>
              <!-- 监听频道下拉保持可操作：阻止冒泡，选频道时不会误触整行折叠。
                   标签改用 VSelect 自带的 label（少一行小字，头行更矮） -->
              <div class="mon-rule-chatfield" @click.stop>
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
                  class="mon-rule-chats"
                />
              </div>
              <!-- 折叠态右侧概览：按当前规则内容动态显示，没设置任何过滤时给一句占位 -->
              <div class="mon-rule-tags">
                <VChip v-if="rule.match_only_if_missing" size="x-small" variant="tonal" color="info" label>
                  仅缺失
                </VChip>
                <VChip v-else-if="rule.match_subscribed_only" size="x-small" variant="tonal" color="info" label>
                  仅推已订阅
                </VChip>
                <VChip v-if="rule.match_custom_keywords && keywordCount(rule)" size="x-small" variant="tonal" color="primary" label>
                  关键词 {{ keywordCount(rule) }}
                </VChip>
                <VChip v-if="excludeCount(rule)" size="x-small" variant="tonal" color="warning" label>
                  排除 {{ excludeCount(rule) }}
                </VChip>
                <span
                  v-if="!rule.match_only_if_missing && !rule.match_subscribed_only && !(rule.match_custom_keywords && keywordCount(rule)) && !excludeCount(rule)"
                  class="mon-rule-tag-empty"
                >无额外过滤</span>
              </div>
              <div
                class="mon-rule-switch"
                title="规则总开关：关闭后这条规则暂停监听（不识别、不推送、也就没有通知）；改动随底部「保存规则」生效。"
                @click.stop
              >
                <VSwitch v-model="rule.enabled" color="success" hide-details inset density="compact" />
                <span class="mon-switch-label">启用</span>
              </div>
              <VBtn
                size="small"
                variant="text"
                color="error"
                @click.stop="removeRule(index)"
              >
                删除
              </VBtn>
            </div>

            <!-- 展开区（仅展开后可见）：基础块 + 关键词两列块——「关键词过滤」与「排除关键词」
                 合并到同一行两列（等宽、gap 8px，窄屏 <700px 回落单列）。
                 用 v-show 而不是 v-if：输入框实例始终挂载，
                 展开/折叠不会丢表单绑定（折叠/展开逻辑与 payload 一律未改动） -->
            <div v-show="isExpanded(rule)" class="mon-rule-body">
              <!-- ① 基础：名称 + （仅缺失开关 + 关键词过滤开关），2 列网格 -->
              <div class="mon-group">
                <div class="mon-group-head">基础</div>
                <div class="mon-group-fields">
                  <VTextField
                    v-model="rule.name"
                    label="规则名称"
                    density="compact"
                    variant="outlined"
                    hide-details
                  />
                  <div class="mon-switch-row">
                    <VSwitch v-model="rule.match_only_if_missing" color="primary" hide-details inset density="compact">
                      <template #label>
                        <span class="mon-switch-label">仅缺失时推送</span>
                      </template>
                    </VSwitch>
                    <!-- 行内说明：不另起一行，避免组内文字挤在一起 -->
                    <span class="mon-group-note">无法判断时跳过</span>
                    <!-- 订阅门禁（1.13.23）：从「仅缺失」里拆出来的独立开关。
                         关掉「仅缺失」是想推全部资源，但不该连带把未订阅的也推出去。 -->
                    <div class="mon-kw-switch">
                      <VSwitch
                        v-model="rule.match_subscribed_only"
                        color="primary"
                        hide-details
                        inset
                        density="compact"
                        title="开启后只推送已订阅的资源；识别不出片名的纯链接消息无法判断订阅身份，仍会推送"
                      />
                      <span class="mon-kw-switch-label">仅推已订阅</span>
                    </div>
                    <!-- 关键词过滤总开关：从「关键词过滤」组标题行移到这里（紧跟仅缺失、间距 8px），
                         绑定仍是同一个 match_custom_keywords，不新增字段 -->
                    <div class="mon-kw-switch">
                      <VSwitch
                        v-model="rule.match_custom_keywords"
                        color="primary"
                        hide-details
                        inset
                        density="compact"
                        title="开启后只有命中关键词的消息才会推送"
                      />
                      <!-- 11px 灰字小标签：区分两个并排开关各自的含义 -->
                      <span class="mon-kw-switch-label">关键词过滤</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- ②③ 关键词过滤 + 排除关键词：同一行两列，两列等宽、gap 8px；
                   两组标题行都只放标题文字（关键词过滤的开关已移到「基础」组），
                   两组的 11px 提示合并成一行放在两列下方。
                   v-model 与多值（multiple + chips）逻辑保持原样 -->
              <div class="mon-kw-wrap">
                <div class="mon-kw-row">
                  <!-- 左：关键词过滤（开关在「基础」组，这里只有标题 + 多值输入） -->
                  <div class="mon-group mon-kw-col">
                    <div class="mon-group-head">关键词过滤</div>
                    <VCombobox
                      v-model="rule.custom_keywords"
                      multiple
                      chips
                      closable-chips
                      label=""
                      placeholder="输入关键词后回车添加，可多个"
                      density="compact"
                      variant="outlined"
                      hide-details
                    />
                  </div>
                  <!-- 右：排除关键词（无开关，优先级高于关键词） -->
                  <div class="mon-group mon-kw-col">
                    <div class="mon-group-head">排除关键词</div>
                    <VCombobox
                      v-model="rule.exclude_keywords"
                      multiple
                      chips
                      closable-chips
                      label=""
                      placeholder="输入排除词后回车添加，可多个"
                      density="compact"
                      variant="outlined"
                      hide-details
                    />
                  </div>
                </div>
                <!-- 两组提示合并成一行 -->
                <div class="mon-group-hint">命中任一关键词即视为通过（留空表示不设限）；排除词命中即跳过，优先级高于关键词</div>
              </div>
            </div>
          </VCardText>
        </VCard>

        <!-- 折叠交互说明（放列表底部，不打扰展开后的表单） -->
        <div v-if="rules.length" class="mon-hint mon-rules-hint">
          默认折叠：点标题行展开编辑；折叠态用右侧小标签概览当前设置。
        </div>

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
          <span class="mon-hint">
            「保存规则」把所有改动（含每条规则标题行上的「启用」开关）立即写进配置并生效。
          </span>
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

    <div class="mon-hint">
      风控提示：TG 个人号对外操作有频率限制，插件按「聚合窗口 + 全局冷却 + FloodWait 退避」克制发送；
      长时间大流量监控请适当调大「TG 凭证」页的个人号冷却秒数。
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPluginApi, postPluginApi, putPluginApi, unwrap } from '../api'
// 规则测试的「决策」文案与详情页 / 仪表盘共用同一份映射（避免同一决策在不同页面文案不一致）
import { decisionLabel } from '../decision'

/**
 * ④ TG 资源监控面板。
 *
 * 数据流：规则存放在插件配置 `monitor_rules`（随主表单保存），但读写走
 * `/monitor/rules` 专用接口——保存即归一（补规则 ID）、即时生效（ensure_started），
 * 不必等插件重载。运行态只读。
 *
 * 命中流水卡已整体移除（流水入口挪到「运行详情页」，由另一个文件负责），
 * 本面板只保留：运行状态、规则编辑、规则测试。
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
// 推送目标固定为 115 网盘：规则里不再暴露「推送目标」，保存时一律发 pan115（后端 DESTINATION_VALUES 合法值）
const FIXED_DESTINATION = 'pan115'
// 决策枚举：仍由 loadRules 从 /monitor/rules 的返回里同步（loadRules 按约定未改动），
// 本面板已不再消费（原「命中流水」的决策筛选卡已删除）。
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
// 规则展开态按规则 id 存在本地映射里，不挂到 rule 对象上：
// rule 会随主表单整份保存，UI 状态不该混进配置（后端也不需要这个字段）
const expandedRules = ref({})
const dialogs = ref([])

const testText = ref('')
const testResult = ref(null)

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
    destination: FIXED_DESTINATION,
    match_only_if_missing: true,
    match_subscribed_only: true,
    match_custom_keywords: false,
    custom_keywords: [],
    exclude_keywords: [],
    rule_type: 'client',
    web_channel_usernames: [],
    enabled: true,
  }
}

// ------------------------------------------------------------------ 规则折叠态（纯前端 UI 状态）

// 展开态查表：没有记录的规则一律按折叠处理（旧规则默认折叠）
function isExpanded(rule) {
  return Boolean(rule?.id && expandedRules.value[rule.id])
}

// 标题行点击 / 箭头点击都走这里：整行任意空白处都能切换
function toggleRule(rule) {
  if (!rule?.id) return
  expandedRules.value[rule.id] = !expandedRules.value[rule.id]
}

// 折叠态概览标签的计数（空数组按 0 处理，避免旧数据缺字段报错）
function keywordCount(rule) {
  return (rule?.custom_keywords || []).length
}

function excludeCount(rule) {
  return (rule?.exclude_keywords || []).length
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
    if (data?.decisions?.length) decisions.value = data.decisions
    const list = Array.isArray(data?.rules) ? data.rules : []
    rules.value = list.map(rule => ({
      id: rule.id || newRuleId(),
      name: rule.name || '',
      source_ids: Array.isArray(rule.source_ids) ? rule.source_ids.map(Number) : [],
      // 推送目标不再可选，历史规则的其他取值也一并归一到 115
      destination: FIXED_DESTINATION,
      match_only_if_missing: rule.match_only_if_missing !== false,
      match_subscribed_only: rule.match_subscribed_only !== false,
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: Array.isArray(rule.custom_keywords) ? rule.custom_keywords : [],
      exclude_keywords: Array.isArray(rule.exclude_keywords) ? rule.exclude_keywords : [],
      rule_type: rule.rule_type || 'client',
      web_channel_usernames: Array.isArray(rule.web_channel_usernames) ? rule.web_channel_usernames : [],
      enabled: rule.enabled !== false,
    }))
    // 接口读回来的都是「已保存的旧规则」，默认全部折叠（新加的规则才自动展开）
    expandedRules.value = {}
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

// 流水卡已移除（入口挪到运行详情页）：不再拉取流水接口，
// 刷新只保留运行状态 / 规则 / 会话列表三个数据源。
async function refreshAll() {
  loading.value = true
  try {
    // 刷新成功不再弹「状态已刷新」这类提示（页面数据本身已更新）；失败仍由各 load* 里的
    // setMessage(..., false) 报错，这里不吞异常、也不再覆盖成功文案
    await Promise.all([loadStatus(), loadRules(), loadDialogs()])
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
  const rule = blankRule()
  rules.value.push(rule)
  // 新加的规则自动展开：用户刚点「添加规则」就是要填内容的
  expandedRules.value[rule.id] = true
  syncRulesToForm()
}

function removeRule(index) {
  const [removed] = rules.value.splice(index, 1)
  // 顺手清掉展开态，避免同 id 复用时状态串台
  if (removed?.id) delete expandedRules.value[removed.id]
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
      // 固定走 115 网盘，不再接受前端选项；target_id 留空（仅 TG 转发才需要）
      destination: FIXED_DESTINATION,
      target_id: '',
      match_only_if_missing: Boolean(rule.match_only_if_missing),
      match_subscribed_only: Boolean(rule.match_subscribed_only),
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: (rule.custom_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      exclude_keywords: (rule.exclude_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      rule_type: rule.rule_type || 'client',
      web_channel_usernames: rule.web_channel_usernames || [],
      enabled: rule.enabled !== false,
    }))
    const data = unwrap(await putPluginApi(props.api, props.pluginId, 'monitor/rules', { rules: payload }, { timeoutMs: 30000 }))
    if (Array.isArray(data?.rules)) {
      rules.value = data.rules
      // 保存后就变成「已保存的旧规则」，全部折叠回标题行，避免下次进来还是一堆展开的表单
      expandedRules.value = {}
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

onMounted(async () => {
  await refreshAll()
  // 轻量轮询：监控是长驻进程，状态卡保持新鲜
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
.mon-pane { display: flex; flex-direction: column; gap: 8px; }
/* 分区卡外观（照效果图）：有底色的圆角块 + 描边，块与块之间 8px。
   Vuetify 的 flat 卡片会把背景重置成与对话框同色，故用 !important 压过它，
   否则分区会粘成一片、看不出边界 */
.mon-card {
  background: rgba(var(--v-theme-on-surface), 0.04) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10) !important;
  border-radius: 10px;
}
.mon-card > .v-card-item { padding: 10px 12px; }
.mon-card > .v-card-text { padding: 10px 12px; }
/* 「规则测试」卡直接用 VCardTitle（没有 VCardItem），单独对齐内边距 */
.mon-card > .v-card-title { padding: 10px 12px 0; }
.mon-message { font-size: 13px; }
/* 状态卡头部右侧：两个徽章 + 刷新按钮，窄屏自动换行并右对齐 */
.mon-status-chips { display: flex; align-items: center; justify-content: flex-end; gap: 6px; flex-wrap: wrap; }
/* 统计条：一行 4 个（与订阅中心/豆瓣中心一致），窄屏回落 2×2 */
.mon-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
@media (max-width: 760px) {
  .mon-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.mon-stat {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  padding: 7px 9px;
  min-width: 0;
}
.mon-stat-label { font-size: 10.5px; line-height: 1.3; color: rgba(var(--v-theme-on-surface), 0.6); }
.mon-stat-value { font-size: 14px; font-weight: 700; line-height: 1.4; margin-top: 2px; }
/* 正文唯一的一行小字：消息监听注册态 + 启动时间 + 冷却/退避 */
.mon-stat-foot { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 8px; font-size: 11.5px; color: rgba(var(--v-theme-on-surface), 0.65); }
.mon-foot-warn { color: rgb(var(--v-theme-warning)); }
.mon-flood { color: rgb(var(--v-theme-warning)); }
/* 诊断：只剩「仅缺失判断不可用」一条小字（收不到事件的两条告警已移除） */
.mon-diag-text { margin-top: 6px; font-size: 11.5px; color: rgb(var(--v-theme-warning)); }
.mon-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 6px; }
.mon-rule {
  /* 与分区卡同款边框色 / 圆角，规则自己也是一块有边界的小卡 */
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10) !important;
  border-radius: 10px;
  margin-top: 8px;
  overflow: hidden;
}
/* 规则卡内的 VCardText 归零内边距：头行与展开区各自控制，避免双层 padding */
.mon-rule > .v-card-text { padding: 0; }
/* 折叠头行：整行可点，键盘/鼠标都能触发；padding 8px 10px、行高约 48-52px */
.mon-rule-head {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  padding: 8px 10px;
  min-height: 48px;
  cursor: pointer;
}
.mon-rule-head-open { cursor: default; }
.mon-rule-toggle {
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1;
  opacity: 0.75;
  user-select: none;
}
.mon-rule-head:hover .mon-rule-toggle {
  opacity: 1;
  background: rgba(var(--v-theme-on-surface), 0.08);
}
/* 下拉框容器：阻止冒泡，选频道/删 chip 时不会误触整行折叠 */
.mon-rule-chatfield { flex: 1 1 240px; min-width: 0; cursor: default; }
.mon-rule-chats { min-width: 0; }
/* 折叠态概览小标签：按规则内容动态出现，无任何过滤时给一句灰色占位 */
.mon-rule-tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.mon-rule-tag-empty { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.45); white-space: nowrap; }
.mon-rule-switch { display: flex; align-items: center; gap: 2px; cursor: default; }
.mon-switch-label { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.7); white-space: nowrap; }
.mon-rules-hint { margin-top: 8px; }
/* 展开区：3 个分组块纵向排列，块与块 8px；与头行之间一条极淡分隔线 */
.mon-rule-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 10px 10px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}
/* 分组块（设计语言同效果图：有底色 + 描边的圆角块） */
.mon-group {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 9px;
  background: rgba(var(--v-theme-on-surface), 0.02);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.mon-group-head { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; }
.mon-group-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 700px) { .mon-group-fields { grid-template-columns: 1fr; } }
/* 关键词过滤 / 排除关键词：同一行两列（等宽、gap 8px），窄屏（<700px）回落单列；
   两组的 11px 提示合并成一行放在两列下方，故外层再包一层竖向 flex + 6px */
.mon-kw-wrap { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.mon-kw-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
@media (max-width: 700px) { .mon-kw-row { grid-template-columns: 1fr; } }
/* 两列标题行都只剩标题文字：给同高下限，两列输入框才不会错位 */
.mon-kw-col > .mon-group-head { min-height: 24px; }
/* 移动进「基础」组的关键词过滤开关：紧跟「仅缺失时推送」，开关与 11px 灰字标签之间 8px */
.mon-kw-switch { display: flex; align-items: center; gap: 8px; min-width: 0; }
.mon-kw-switch-label { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.55); white-space: nowrap; }
/* 组内 11px 灰提示：贴着对应输入框，不再堆成一片 */
.mon-group-hint { font-size: 11px; line-height: 1.45; color: rgba(var(--v-theme-on-surface), 0.55); }
.mon-group-note { font-size: 11px; line-height: 1.45; color: rgba(var(--v-theme-on-surface), 0.5); }
/* 开关行与同排输入框（compact + outlined，40px）高度对齐 */
.mon-switch-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-height: 40px; min-width: 0; }
.mon-hint { margin-top: 0; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.5; }
.mon-empty {
  padding: 12px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.mon-test-result { margin-top: 8px; }
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
</style>
