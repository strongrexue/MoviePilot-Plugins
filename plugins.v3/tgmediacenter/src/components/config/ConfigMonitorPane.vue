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
        <!-- 诊断：只在有问题时出现，正常时与效果图完全一致 -->
        <VAlert
          v-if="status?.enabled && (status?.pipeline?.events_received ?? 0) > 0 && !((status?.pipeline?.events_watched ?? 0) > 0)"
          type="warning"
          variant="tonal"
          density="compact"
          class="mon-diag"
        >
          收到 {{ status.pipeline.events_received }} 条事件，但没有一条来自监听会话。
          常见原因：①监听 ID「反查失败」＝账号看不到该会话（ID 失效或选错，到「TG 凭证」页刷新对话后重选并保存规则）
          ②规则里选错频道 ③账号已退出该频道（重新加入后刷新对话列表重选）。
        </VAlert>
        <VAlert
          v-if="status?.enabled && !((status?.pipeline?.events_received ?? 0) > 0)"
          type="warning"
          variant="tonal"
          density="compact"
          class="mon-diag"
        >
          还没收到任何 TG 事件：请确认 ①TG 凭证已登录且「已连接」 ②消息监听为「已注册」③规则监听的频道正确。
        </VAlert>
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
          <VCardText class="pt-0">
            <!-- 标题行（折叠态唯一一行）：整行点击切换展开，▸/▾ 只是提示 -->
            <div
              class="mon-rule-head"
              :class="{ 'mon-rule-head-open': isExpanded(rule) }"
              :title="isExpanded(rule) ? '点击收起这条规则的编辑表单' : '点击展开编辑这条规则'"
              @click="toggleRule(rule)"
            >
              <span class="mon-rule-toggle">{{ isExpanded(rule) ? '▾' : '▸' }}</span>
              <!-- 监听频道下拉保持可操作：阻止冒泡，选频道时不会误触整行折叠 -->
              <div class="mon-rule-chatfield" @click.stop>
                <div class="mon-rule-chatlabel">监听频道 / 群组</div>
                <VSelect
                  v-model="rule.source_ids"
                  :items="selectItems"
                  item-title="title"
                  item-value="value"
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
                <VChip v-if="rule.match_custom_keywords && keywordCount(rule)" size="x-small" variant="tonal" color="primary" label>
                  关键词 {{ keywordCount(rule) }}
                </VChip>
                <VChip v-if="excludeCount(rule)" size="x-small" variant="tonal" color="warning" label>
                  排除 {{ excludeCount(rule) }}
                </VChip>
                <span
                  v-if="!rule.match_only_if_missing && !(rule.match_custom_keywords && keywordCount(rule)) && !excludeCount(rule)"
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

            <!-- 正文网格（仅展开后可见）：名称 / 缺失判断 / 关键词 / 排除词 四组。
                 用 v-show 而不是 v-if：输入框实例始终挂载，展开/折叠不会丢表单绑定 -->
            <div v-show="isExpanded(rule)" class="mon-rule-grid">
              <div class="mon-field">
                <VTextField
                  v-model="rule.name"
                  label="规则名称"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
              </div>

              <div class="mon-field">
                <div class="mon-switch-row">
                  <VSwitch v-model="rule.match_only_if_missing" color="primary" hide-details inset density="compact">
                    <template #label>
                      <span class="mon-switch-label">仅缺失时推送</span>
                    </template>
                  </VSwitch>
                </div>
                <div class="mon-hint">按 MP 媒体服务器与订阅状态判断；无法判断时命中会跳过。</div>
              </div>

              <div class="mon-field">
                <div class="mon-switch-row">
                  <VSwitch v-model="rule.match_custom_keywords" color="primary" hide-details inset density="compact">
                    <template #label>
                      <span class="mon-switch-label">自定义关键词过滤</span>
                    </template>
                  </VSwitch>
                </div>
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
                />
              </div>

              <div class="mon-field">
                <VCombobox
                  v-model="rule.exclude_keywords"
                  multiple
                  chips
                  closable-chips
                  label="排除关键词（任一命中即不推送）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div class="mon-hint">
                  排除词对整条消息做子串匹配（标题、题材、分类行都算），如「加更」「花絮」「预告」；
                  即使自定义关键词命中，只要含排除词就不推送。
                </div>
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
        <div class="mon-hits-tools">
          <VTextField
            v-model="hitKeyword"
            placeholder="按片名 / 规则 / 说明搜索"
            prepend-inner-icon="mdi-magnify"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            class="mon-hits-search"
          />
          <VBtn
            size="small"
            variant="tonal"
            color="error"
            prepend-icon="mdi-delete-outline"
            :disabled="!hitsTotal"
            @click="askClear('filtered')"
          >
            删除筛选结果
          </VBtn>
          <VBtn
            size="small"
            variant="text"
            color="error"
            :disabled="!hitsTotal"
            @click="askClear('all')"
          >
            清空本类流水
          </VBtn>
        </div>
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

    <!-- 清理流水确认（删除不可恢复，必须二次确认） -->
    <VDialog v-model="clearDialog" max-width="460">
      <VCard>
        <VCardTitle class="text-subtitle-1">
          {{ clearTarget === 'all' ? '清空监控流水' : '删除筛选结果' }}
        </VCardTitle>
        <VCardText class="text-body-2">
          <template v-if="hasFilter">
            当前有筛选条件，将只删除筛选出的 <strong>{{ hitsTotal }}</strong> 条流水
            <template v-if="filterText">（筛选：{{ filterText }}）</template>
            ，删除后不可恢复；未筛选部分不受影响。如需清空全部，请先清除筛选条件。
          </template>
          <template v-else>
            将删除本面板的<strong>全部监控流水</strong>（共 {{ hitsTotal }} 条），删除后不可恢复；
            通用转发的流水不受影响。
          </template>
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="clearDialog = false">取消</VBtn>
          <VBtn color="error" :loading="clearing" @click="runClear">删除</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getPluginApi, postPluginApi, putPluginApi, unwrap } from '../api'
// 流水「决策」文案与详情页 / 仪表盘共用同一份映射（避免同一决策在不同页面文案不一致）
import { decisionLabel, decisionColor } from '../decision'

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
// 推送目标固定为 115 网盘：规则里不再暴露「推送目标」，保存时一律发 pan115（后端 DESTINATION_VALUES 合法值）
const FIXED_DESTINATION = 'pan115'
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

const hits = ref([])
const hitsTotal = ref(0)
const hitsPage = ref(1)
const hitsPageSize = 20
const decisionFilter = ref('')
// 关键词用可写 computed 包一层：Vuetify 的 clearable 清除按钮会把模型置为 null，
// 直接 ref('') 收 null 会让各处 .trim() 抛错（1.6.6 真机反馈：清空关键词后列表不刷新），
// 这里在入口统一归一成字符串，模板与脚本就都不用到处防 null。
const hitKeywordRaw = ref('')
const hitKeyword = computed({
  get: () => String(hitKeywordRaw.value ?? ''),
  set: (value) => { hitKeywordRaw.value = value == null ? '' : String(value) },
})
const clearDialog = ref(false)
const clearTarget = ref('filtered')
const clearing = ref(false)

let refreshTimer = null
let keywordTimer = null

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

async function loadHits() {
  try {
    const params = new URLSearchParams()
    params.set('page', String(hitsPage.value))
    params.set('page_size', String(hitsPageSize))
    if (decisionFilter.value) params.set('decision', decisionFilter.value)
    if (hitKeyword.value.trim()) params.set('keyword', hitKeyword.value.trim())
    const data = unwrap(await getPluginApi(
      props.api, props.pluginId, `monitor/hits?${params.toString()}`, { timeoutMs: 15000 },
    ))
    hits.value = data?.items || []
    hitsTotal.value = data?.total || 0
  } catch (err) {
    setMessage(err?.message || '读取命中流水失败', false)
  }
}

// 关键词输入防抖 300ms：边打字边查会把后端打满（流水表可能上万行）
watch(hitKeyword, () => {
  clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => {
    hitsPage.value = 1
    loadHits()
  }, 300)
})

// 当前是否有筛选条件（删除对话框据此说明"删多少"，与后端删除口径严格一致）
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
  if (clearing.value) return
  clearing.value = true
  try {
    // 无论点哪个删除按钮，都只删「当前视图」：带上决策与关键词筛选，
    // 没有筛选才是清空本类全部（后端按 kind 隔离，不会碰到转发流水）。
    // 1.6.6 真机反馈：原来「清空本类流水」忽略筛选直接删整个 kind，对话框却
    // 显示筛选后的条数——用户确认「共 3 条」结果丢了全部流水。
    const payload = { decision: decisionFilter.value || '', keyword: hitKeyword.value.trim() }
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'monitor/hits/clear', payload, { timeoutMs: 30000 },
    ))
    setMessage(data?.message || '已清理流水')
    clearDialog.value = false
    hitsPage.value = 1
    await Promise.all([loadHits(), loadStatus()])
  } catch (err) {
    setMessage(err?.message || '清理流水失败', false)
  } finally {
    clearing.value = false
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

// 监听会话 ID → 反查标题（来自状态卡 watched_detail），命中流水「来源」列展示用
const chatTitleMap = computed(() => {
  const map = {}
  for (const w of (status.value?.pipeline?.watched_detail || [])) {
    if (w.resolved && w.title) map[w.chat_id] = w.title
  }
  return map
})

// 媒体列完整名：片名（年份）+ 电视剧 SxxExx（如「青与碧 (2026) S01E02」；
// 多集区间拼 S01E05-E06）
function mediaName(item) {
  if (!item.title) return ''
  const year = item.year ? ` (${item.year})` : ''
  let name = `${item.title}${year}`
  if (item.season || item.episode) {
    const s = String(item.season ?? 1).padStart(2, '0')
    const e = String(item.episode ?? 0).padStart(2, '0')
    const end = Number(item.episode_end ?? 0)
    if (end > (item.episode ?? 0)) {
      name += ` S${s}E${e}-E${String(end).padStart(2, '0')}`
    } else {
      name += ` S${s}E${e}`
    }
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
  if (keywordTimer) {
    window.clearTimeout(keywordTimer)
    keywordTimer = null
  }
})
</script>

<style scoped>
.mon-pane { display: flex; flex-direction: column; gap: 8px; }
.mon-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.mon-message { font-size: 13px; }
/* 状态卡头部右侧：两个徽章 + 刷新按钮，窄屏自动换行并右对齐 */
.mon-status-chips { display: flex; align-items: center; justify-content: flex-end; gap: 6px; flex-wrap: wrap; }
/* 2×2 统计块：背景/边框/圆角/内边距按效果图固定 */
.mon-stat-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
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
/* 诊断：默认不出现，只在「收不到事件 / 仅缺失判断不可用」时插入 */
.mon-diag { margin-top: 8px; font-size: 11.5px; }
.mon-diag-text { margin-top: 6px; font-size: 11.5px; color: rgb(var(--v-theme-warning)); }
.mon-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 6px; }
.mon-rule { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; margin-top: 8px; }
/* 标题行（折叠态唯一一行）：整行可点，键盘/鼠标都能触发；箭头 + 下拉 + 概览标签 + 开关 + 删除 */
.mon-rule-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; cursor: pointer; }
.mon-rule-head-open { cursor: default; }
.mon-rule-toggle {
  flex: 0 0 14px;
  width: 14px;
  text-align: center;
  font-size: 12px;
  line-height: 1;
  opacity: 0.65;
  user-select: none;
}
/* 下拉框容器：阻止冒泡，选频道/删 chip 时不会误触整行折叠 */
.mon-rule-chatfield { flex: 1 1 240px; min-width: 0; display: flex; flex-direction: column; gap: 2px; cursor: default; }
.mon-rule-chatlabel { font-size: 10.5px; line-height: 1.3; color: rgba(var(--v-theme-on-surface), 0.6); }
.mon-rule-chats { min-width: 0; }
/* 折叠态概览小标签：按规则内容动态出现，无任何过滤时给一句灰色占位 */
.mon-rule-tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.mon-rule-tag-empty { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.45); white-space: nowrap; }
.mon-rule-switch { display: flex; align-items: center; gap: 2px; cursor: default; }
.mon-switch-label { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.7); white-space: nowrap; }
.mon-rules-hint { margin-top: 8px; }
/* 正文网格：等宽自适应列，窄屏自动降为单列 */
.mon-rule-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
  margin-top: 8px;
}
/* 逻辑分组：组内纵向 4px（提示文字与上方控件固定 4px） */
.mon-field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
/* 开关行与同排输入框（compact + outlined，40px）高度对齐 */
.mon-switch-row { display: flex; align-items: center; min-height: 40px; }
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
.mon-hits-tools { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.mon-hits-search { flex: 1 1 220px; max-width: 320px; }
</style>
