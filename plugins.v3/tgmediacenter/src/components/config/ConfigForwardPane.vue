<template>
  <div class="fwd-pane">
    <!-- 启用开关 -->
    <VCard flat class="fwd-card">
      <VCardItem>
        <template #prepend>
          <VSwitch v-model="form.forward_enabled" color="primary" hide-details inset />
        </template>
        <VCardTitle class="text-subtitle-2">启用 TG 通用转发</VCardTitle>
        <VCardSubtitle class="text-caption">
          监听来源频道的消息，按两级匹配命中后转发到目标会话——可选内容转换与置顶
          （开关随「保存配置」生效）。
        </VCardSubtitle>
      </VCardItem>
    </VCard>

    <VAlert
      v-if="message"
      :type="messageOk ? 'info' : 'warning'"
      variant="tonal"
      density="comfortable"
      class="fwd-message"
    >{{ message }}</VAlert>

    <!-- 运行状态：头部右侧留状态徽章 + 刷新，正文是 2×2 统计块 -->
    <VCard flat class="fwd-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">运行状态</VCardTitle>
        <VCardSubtitle class="text-caption">与监控共用流水线与全局冷却</VCardSubtitle>
        <template #append>
          <div class="fwd-status-head">
            <VChip size="small" variant="tonal" :color="status?.enabled ? 'success' : 'default'" label>
              转发{{ status?.enabled ? '已启用' : '未启用' }}
            </VChip>
            <VChip v-if="(status?.gate_interval ?? 0) > 0" size="small" variant="tonal" color="default" label>
              全局冷却 {{ status.gate_interval }} 秒
            </VChip>
            <VChip v-if="(status?.flood_remaining ?? 0) > 0" size="small" variant="tonal" color="warning" label>
              FloodWait 退避中（约 {{ status.flood_remaining }} 秒）
            </VChip>
            <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="refreshAll">
              刷新
            </VBtn>
          </div>
        </template>
      </VCardItem>
      <VCardText class="pt-0">
        <!-- 统计块：小灰标签 + 粗体数值，两列等宽 -->
        <div class="fwd-stats">
          <div class="fwd-stat">
            <span class="fwd-stat-label">转发规则</span>
            <span class="fwd-stat-value">{{ status?.rules_count ?? 0 }}</span>
          </div>
          <div class="fwd-stat">
            <span class="fwd-stat-label">关心会话</span>
            <span class="fwd-stat-value">{{ status?.watched_chats ?? 0 }}</span>
          </div>
          <div class="fwd-stat">
            <span class="fwd-stat-label">转换条目</span>
            <span class="fwd-stat-value">{{ status?.transform_rules_count ?? 0 }}</span>
          </div>
          <div class="fwd-stat">
            <span class="fwd-stat-label">冷却间隔</span>
            <span class="fwd-stat-value">{{ gateIntervalText }}</span>
          </div>
        </div>
        <div class="fwd-status-sub">
          <span>转发只按关键词与扩展名匹配，与订阅无关；识别仅用于展示，识别不出也能转发。</span>
        </div>
      </VCardText>
    </VCard>

    <!-- 规则编辑器 -->
    <VCard flat class="fwd-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">转发规则</VCardTitle>
        <template #append>
          <VBtn size="small" variant="tonal" prepend-icon="mdi-plus" @click="addRule">添加规则</VBtn>
        </template>
      </VCardItem>
      <VCardText class="pt-0">
        <div v-if="!rules.length" class="fwd-empty">
          还没有规则。点「添加规则」创建第一条：选择来源频道与转发目标，保存后立即生效。
        </div>

        <VCard
          v-for="(rule, index) in rules"
          :key="rule.id || index"
          flat
          class="fwd-rule"
        >
          <!-- 规则卡片：顶部留 8px，避免 outlined 控件贴住卡片描边 -->
          <VCardText class="pt-2 pb-2 px-3">
            <!-- 卡片头（折叠态一行）：折叠箭头 + 来源下拉 + 概览标签 + 启用/删除；点整行切换折叠 -->
            <div
              class="fwd-rule-head"
              :title="isRuleExpanded(rule) ? '点这里折叠规则详情' : '点这里展开规则详情'"
              @click="toggleRule(rule)"
            >
              <span class="fwd-rule-caret">{{ isRuleExpanded(rule) ? '▾' : '▸' }}</span>
              <!-- 来源下拉保持可操作：点它不触发折叠 -->
              <div class="fwd-rule-source" @click.stop>
                <VSelect
                  v-model="rule.source_ids"
                  :items="selectItems"
                  item-title="title"
                  item-value="value"
                  label="来源频道 / 群组"
                  multiple
                  chips
                  closable-chips
                  density="compact"
                  variant="outlined"
                  hide-details
                />
              </div>
              <!-- 概览标签：按规则实际内容动态生成，折叠态也能一眼看出规则在做什么 -->
              <div class="fwd-rule-tags">
                <span v-for="(tag, tagIndex) in ruleSummary(rule)" :key="tagIndex" class="fwd-rule-tag">{{ tag }}</span>
              </div>
              <div class="fwd-rule-tools" @click.stop>
                <div
                  class="fwd-rule-switch"
                  title="规则总开关：关闭后这条转发规则不生效（不转发、也不会有通知）；改动随底部「保存配置」生效。"
                >
                  <VSwitch v-model="rule.enabled" color="success" hide-details inset density="compact" />
                  <span class="fwd-switch-label">启用</span>
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
            </div>

            <!-- 正文网格：展开后显示，用 v-show 而非 v-if，折叠时控件仍挂载、表单绑定不断 -->
            <div v-show="isRuleExpanded(rule)" class="fwd-rule-grid">
              <!-- 组一：转发（规则名 + 目标 + 置顶） -->
              <div class="fwd-group">
                <div class="fwd-group-title">转发</div>
                <VTextField
                  v-model="rule.name"
                  label="规则名称"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <VSelect
                  v-model="rule.target_id"
                  :items="targetItems"
                  item-title="title"
                  item-value="value"
                  label="转发目标频道 / 群组"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <VSwitch v-model="rule.pin_links_enabled" color="primary" hide-details inset density="compact">
                  <template #label><span class="fwd-switch-label">转发后置顶</span></template>
                </VSwitch>
                <VCombobox
                  v-if="rule.pin_links_enabled"
                  v-model="rule.pin_link_keywords"
                  multiple
                  chips
                  closable-chips
                  label="仅命中这些关键词时置顶（留空=有链接就置顶）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div v-else class="fwd-hint">置顶以链接为对象：没有链接的消息不置顶。</div>
              </div>

              <!-- 组二：关键词（自定义关键词 + 排除词） -->
              <div class="fwd-group">
                <div class="fwd-group-title">关键词</div>
                <VSwitch v-model="rule.match_custom_keywords" color="primary" hide-details inset density="compact">
                  <template #label><span class="fwd-switch-label">自定义关键词</span></template>
                </VSwitch>
                <VCombobox
                  v-if="rule.match_custom_keywords"
                  v-model="rule.custom_keywords"
                  multiple
                  chips
                  closable-chips
                  label="关键词"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div v-else class="fwd-hint">启用后只有命中关键词的消息才转发；不启用 = 该级不设限。</div>
                <VCombobox
                  v-model="rule.exclude_keywords"
                  multiple
                  chips
                  closable-chips
                  label="排除关键词（任一命中即不转发，优先于上面两级）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div class="fwd-hint">对整条消息做子串匹配，如「加更」「花絮」「预告」；即使命中关键词，含排除词也不转发。</div>
              </div>

              <!-- 组三：扩展名 -->
              <div class="fwd-group">
                <div class="fwd-group-title">文件扩展名</div>
                <VSwitch v-model="rule.match_file_extensions" color="primary" hide-details inset density="compact">
                  <template #label><span class="fwd-switch-label">按扩展名过滤</span></template>
                </VSwitch>
                <VCombobox
                  v-if="rule.match_file_extensions"
                  v-model="rule.file_extensions_to_match"
                  multiple
                  chips
                  closable-chips
                  label="扩展名"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div class="fwd-hint">消息中出现指定扩展名（如 .mkv / [mp4]）才算命中。</div>
                <div class="fwd-hint">
                  逻辑一（关键词）与逻辑二（扩展名）<strong>恒为 AND</strong>：两者都启用时必须同时满足。
                </div>
              </div>

              <!-- 组四：内容转换 -->
              <div class="fwd-group">
                <div class="fwd-group-title">内容转换</div>
                <VSwitch v-model="rule.enable_transform" color="primary" hide-details inset density="compact">
                  <template #label><span class="fwd-switch-label">内容转换</span></template>
                </VSwitch>
                <VTextarea
                  v-if="rule.enable_transform"
                  v-model="transformText[rule.id || index]"
                  label="转换规则（每行一条：原文 -> 替换文，支持正则）"
                  placeholder="广告词.*-> &#10;@\w+ -> "
                  rows="3"
                  density="compact"
                  variant="outlined"
                  hide-details
                  @update:model-value="syncTransform(rule, index)"
                />
                <div class="fwd-hint">转换后以新内容发送（不改动原消息）。</div>
              </div>
            </div>
          </VCardText>
        </VCard>

        <!-- 折叠说明：规则默认折叠，避免多条规则把面板拉得很长 -->
        <div v-if="rules.length" class="fwd-hint fwd-rules-hint">
          默认折叠：点标题行展开；折叠态用右侧小标签概览。
        </div>

        <div v-if="rules.length" class="fwd-actions">
          <VBtn
            color="primary"
            variant="flat"
            prepend-icon="mdi-content-save-outline"
            :loading="busy === 'save'"
            @click="saveRules"
          >
            保存规则（即时生效）
          </VBtn>
          <span class="fwd-hint">规则保存在插件配置里；开关与其它模块设置随底部「保存配置」持久化。</span>
        </div>
      </VCardText>
    </VCard>

    <!-- 规则测试 -->
    <VCard flat class="fwd-card">
      <VCardTitle class="text-subtitle-2">规则测试</VCardTitle>
      <VCardText class="pt-0">
        <VTextarea
          v-model="testText"
          label="粘贴一条来源频道消息原文"
          placeholder="剧名.S01E02.2160p.WEB-DL.mkv&#10;https://115.com/s/xxxxx?password=abcd"
          rows="3"
          density="compact"
          variant="outlined"
          hide-details
        />
        <div class="fwd-actions">
          <VBtn variant="tonal" prepend-icon="mdi-test-tube" :loading="busy === 'test'" @click="runTest">
            测试（不转发、不入队）
          </VBtn>
        </div>

        <div v-if="testResult" class="fwd-test-result">
          <div class="fwd-test-line">
            <strong>识别结果：</strong>
            <span v-if="testResult.recognized">
              《{{ testResult.recognized.title }}》
              <span v-if="testResult.recognized.year">（{{ testResult.recognized.year }}）</span>
              <span v-if="testResult.recognized.season"> S{{ String(testResult.recognized.season).padStart(2, '0') }}</span>
              <span v-if="testResult.recognized.episode">E{{ String(testResult.recognized.episode).padStart(2, '0') }}</span>
            </span>
            <span v-else class="fwd-test-none">无法识别（不影响转发：转发只按关键词与扩展名匹配）</span>
          </div>
          <div v-if="testResult.links?.length" class="fwd-test-line">
            <strong>解析到 {{ testResult.links.length }} 个链接</strong>
          </div>
          <VList density="compact" class="fwd-test-list">
            <VListItem v-for="(trace, index) in testResult.rules" :key="index">
              <template #prepend>
                <VIcon
                  :icon="trace.matched ? 'mdi-share-outline' : 'mdi-minus-circle-outline'"
                  size="18"
                  :color="trace.matched ? 'success' : 'warning'"
                />
              </template>
              <VListItemTitle class="fwd-test-name">
                {{ trace.rule_name }}
                <VChip v-if="!trace.enabled" size="x-small" variant="tonal" color="default" label class="fwd-test-off">已停用</VChip>
                <VChip v-if="trace.pin" size="x-small" variant="tonal" color="info" label class="fwd-test-off">置顶</VChip>
              </VListItemTitle>
              <VListItemSubtitle class="fwd-test-msg">
                {{ decisionLabel(trace.decision) }} · {{ trace.reason }}
                <template v-if="trace.matched && trace.send_text"> ▸ 将发送：{{ trace.send_text }}</template>
              </VListItemSubtitle>
            </VListItem>
          </VList>
        </div>
      </VCardText>
    </VCard>

    <!-- 转发流水 -->
    <VCard flat class="fwd-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">转发流水</VCardTitle>
        <template #append>
          <VSelect
            v-model="decisionFilter"
            :items="[{ value: '', title: '全部决策' }, ...decisions]"
            item-title="title"
            item-value="value"
            density="compact"
            variant="outlined"
            hide-details
            class="fwd-filter"
            @update:model-value="onDecisionFilter"
          />
        </template>
      </VCardItem>
      <VCardText class="pt-0">
        <div class="fwd-hits-tools">
          <VTextField
            v-model="hitKeyword"
            placeholder="按片名 / 规则 / 说明搜索"
            prepend-inner-icon="mdi-magnify"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            class="fwd-hits-search"
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
        <VTable density="compact" class="fwd-hits">
          <thead>
            <tr>
              <th class="fwd-nowrap">时间</th>
              <th class="fwd-nowrap">规则</th>
              <th class="fwd-nowrap">来源</th>
              <th>媒体</th>
              <th class="fwd-nowrap">决策</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in hits" :key="item.id">
              <td class="fwd-hits-time">{{ fmtTime(item.created_at) }}</td>
              <td class="fwd-nowrap">{{ item.rule_name }}</td>
              <td class="fwd-hits-source">{{ chatTitleMap[item.chat_id] || item.chat_id }}</td>
              <td>
                <span v-if="item.title">{{ mediaName(item) }}</span>
                <span v-else class="fwd-hits-none">—</span>
              </td>
              <td class="fwd-nowrap">
                <VChip size="x-small" variant="tonal" :color="decisionColor(item.decision)" label>
                  {{ decisionLabel(item.decision) }}
                </VChip>
              </td>
              <td class="fwd-hits-detail">{{ item.detail }}</td>
            </tr>
            <tr v-if="!hits.length">
              <td colspan="6" class="fwd-hits-empty">暂无记录</td>
            </tr>
          </tbody>
        </VTable>
        <div class="fwd-pager">
          <VBtn size="small" variant="text" :disabled="hitsPage <= 1" prepend-icon="mdi-chevron-left" @click="prevHits">
            上一页
          </VBtn>
          <span class="fwd-pager-info">第 {{ hitsPage }} 页 · 共 {{ hitsTotal }} 条</span>
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

    <div class="fwd-hint">
      风控提示：TG 个人号转发有严格频率限制，插件按「聚合窗口 + 全局冷却 + FloodWait 退避」克制发送；
      转发目标建议用小号或私密频道，避免主号因高频转发被限制。
    </div>

    <!-- 清理流水确认（删除不可恢复，必须二次确认） -->
    <VDialog v-model="clearDialog" max-width="460">
      <VCard>
        <VCardTitle class="text-subtitle-1">
          {{ clearTarget === 'all' ? '清空转发流水' : '删除筛选结果' }}
        </VCardTitle>
        <VCardText class="text-body-2">
          <template v-if="hasFilter">
            当前有筛选条件，将只删除筛选出的 <strong>{{ hitsTotal }}</strong> 条流水
            <template v-if="filterText">（筛选：{{ filterText }}）</template>
            ，删除后不可恢复；未筛选部分不受影响。如需清空全部，请先清除筛选条件。
          </template>
          <template v-else>
            将删除本面板的<strong>全部转发流水</strong>（共 {{ hitsTotal }} 条），删除后不可恢复；
            资源监控的流水不受影响。
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
import { decisionLabel, decisionColor } from '../decision'

/**
 * ⑥ TG 通用转发面板。
 *
 * 规则存放在插件配置 `forward_rules`（随主表单保存），读写走 `/forward/rules`
 * 专用接口——保存即校验（缺目标会话直接 400）+ 归一（补 f 前缀规则 ID）+ 即时生效。
 * 转发流水与运行态只读。
 *
 * 纪律（沿用全项目约定）：
 * - 模板/脚本用到的变量全部在 script setup 声明 ref；
 * - 重入保护只留在按钮处理器，内部 fetch 函数无保护；
 * - 新增配置项必须同步进 useConfigForm.js 的 configDefaults（保存是整份覆盖）。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
})

const form = computed(() => props.config.form)

const status = ref(null)
// 会话 ID → 标题的映射来自监控状态（转发与监控共用同一条流水线的会话反查结果）
const watchedDetail = ref([])
const loading = ref(false)
const busy = ref('')
const message = ref('')
const messageOk = ref(true)

const decisions = ref([
  { value: 'hit', title: '已转发' },
  { value: 'skipped_keyword', title: '关键词未命中' },
  { value: 'skipped_extension', title: '扩展名未命中' },
])

const rules = ref([])
const dialogs = ref([])
// 转换规则用多行文本编辑（提交时拆行）；键与规则 id 对应
const transformText = ref({})
// 每条规则的本地折叠状态：{ [规则 id]: true } 即展开。
// 已保存的规则默认折叠（表里没有即 false），新加的规则由 addRule 显式置 true。
const expandedRules = ref({})

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
  return 'f' + Math.random().toString(16).slice(2, 10)
}

function blankRule() {
  return {
    id: newRuleId(),
    name: '',
    source_ids: [],
    target_id: '',
    match_custom_keywords: false,
    custom_keywords: [],
    exclude_keywords: [],
    pin_links_enabled: false,
    pin_link_keywords: [],
    match_file_extensions: false,
    file_extensions_to_match: [],
    enable_transform: false,
    transform_rules: [],
    enabled: true,
  }
}

// ------------------------------------------------------------------ 数据加载（无重入保护）

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'forward/status', { timeoutMs: 15000 }))
  } catch (err) {
    setMessage(err?.message || '读取转发状态失败', false)
  }
  // 会话标题映射：转发与监控共用同一条流水线的会话反查结果，取不到就显示 ID
  try {
    const monitor = unwrap(await getPluginApi(props.api, props.pluginId, 'monitor/status', { timeoutMs: 15000 }))
    watchedDetail.value = monitor?.pipeline?.watched_detail || []
  } catch {
    watchedDetail.value = []
  }
}

async function loadRules() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'forward/rules', { timeoutMs: 15000 }))
    if (data?.decisions?.length) decisions.value = data.decisions
    const list = Array.isArray(data?.rules) ? data.rules : []
    rules.value = list.map(rule => ({
      id: rule.id || newRuleId(),
      name: rule.name || '',
      source_ids: Array.isArray(rule.source_ids) ? rule.source_ids.map(toChatId).filter(id => id !== '') : [],
      target_id: toChatId(rule.target_id),
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: Array.isArray(rule.custom_keywords) ? rule.custom_keywords : [],
      exclude_keywords: Array.isArray(rule.exclude_keywords) ? rule.exclude_keywords : [],
      pin_links_enabled: Boolean(rule.pin_links_enabled),
      pin_link_keywords: Array.isArray(rule.pin_link_keywords) ? rule.pin_link_keywords : [],
      match_file_extensions: Boolean(rule.match_file_extensions),
      file_extensions_to_match: Array.isArray(rule.file_extensions_to_match) ? rule.file_extensions_to_match : [],
      enable_transform: Boolean(rule.enable_transform),
      transform_rules: Array.isArray(rule.transform_rules) ? rule.transform_rules : [],
      enabled: rule.enabled !== false,
    }))
    // 已保存规则默认折叠（表里没有即 false）；只保留仍在列表里的 id，防止残留 key
    const nextExpanded = {}
    for (const rule of rules.value) {
      if (expandedRules.value[rule.id]) nextExpanded[rule.id] = true
    }
    expandedRules.value = nextExpanded
    syncTransformFromRules()
    syncRulesToForm()
  } catch (err) {
    setMessage(err?.message || '读取转发规则失败', false)
  }
}

async function loadDialogs() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'telegram/dialogs', { timeoutMs: 15000 }))
    dialogs.value = data?.dialogs || []
  } catch {
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
      props.api, props.pluginId, `forward/hits?${params.toString()}`, { timeoutMs: 15000 },
    ))
    hits.value = data?.items || []
    hitsTotal.value = data?.total || 0
  } catch (err) {
    setMessage(err?.message || '读取转发流水失败', false)
  }
}

// 关键词输入防抖 300ms：边打字边查会把后端打满
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
    // 没有筛选才是清空本类全部（后端按 kind 隔离，不会碰到监控流水）。
    // 1.6.6 真机反馈：原来「清空本类流水」忽略筛选直接删整个 kind，对话框却
    // 显示筛选后的条数——用户确认「共 3 条」结果丢了全部流水。
    const payload = { decision: decisionFilter.value || '', keyword: hitKeyword.value.trim() }
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'forward/hits/clear', payload, { timeoutMs: 30000 },
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
  form.value.forward_rules = rules.value
}

function syncTransformFromRules() {
  const next = {}
  for (const rule of rules.value) {
    next[rule.id] = (rule.transform_rules || []).join('\n')
  }
  transformText.value = next
}

function syncTransform(rule, index) {
  const key = rule.id || index
  const lines = String(transformText.value[key] || '')
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
  rule.transform_rules = lines
  syncRulesToForm()
}

function addRule() {
  const rule = blankRule()
  rules.value.push(rule)
  transformText.value[rule.id] = ''
  // 新规则自动展开：空白规则折叠起来没法填
  expandedRules.value[rule.id] = true
  syncRulesToForm()
}

function removeRule(index) {
  const rule = rules.value[index]
  if (rule) {
    delete transformText.value[rule.id]
    delete expandedRules.value[rule.id]
  }
  rules.value.splice(index, 1)
  syncRulesToForm()
}

// 规则折叠状态：按规则 id 存在本地表里，已保存规则默认折叠
function isRuleExpanded(rule) {
  return Boolean(expandedRules.value[rule.id])
}

function toggleRule(rule) {
  expandedRules.value[rule.id] = !expandedRules.value[rule.id]
}

function isNumericId(value) {
  return /^-?\d+$/.test(String(value ?? '').trim())
}

async function saveRules() {
  if (busy.value) return
  const missing = rules.value.find(rule => !isNumericId(rule.target_id))
  if (missing) {
    setMessage(`规则「${missing.name || '未命名'}」还没选择转发目标`, false)
    return
  }
  busy.value = 'save'
  setMessage('正在保存规则…')
  try {
    const payload = rules.value.map(rule => ({
      id: rule.id,
      name: String(rule.name || '').trim() || '未命名规则',
      source_ids: rule.source_ids,
      target_id: Number(rule.target_id),
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: (rule.custom_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      exclude_keywords: (rule.exclude_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      pin_links_enabled: Boolean(rule.pin_links_enabled),
      pin_link_keywords: (rule.pin_link_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      match_file_extensions: Boolean(rule.match_file_extensions),
      file_extensions_to_match: (rule.file_extensions_to_match || []).map(ext => String(ext).trim().replace(/^\./, '')).filter(Boolean),
      enable_transform: Boolean(rule.enable_transform),
      transform_rules: (rule.transform_rules || []).map(line => String(line).trim()).filter(Boolean),
      // 转存 / 转发等既有规则行保留启用开关：关掉即暂停该规则（不生效、无通知）
      enabled: rule.enabled !== false,
    }))
    const data = unwrap(await putPluginApi(props.api, props.pluginId, 'forward/rules', { rules: payload }, { timeoutMs: 30000 }))
    if (Array.isArray(data?.rules)) {
      rules.value = data.rules.map(rule => ({
        ...rule,
        id: rule.id || newRuleId(),
        source_ids: Array.isArray(rule.source_ids) ? rule.source_ids.map(Number) : [],
        target_id: rule.target_id ? String(rule.target_id) : '',
        custom_keywords: rule.custom_keywords || [],
        exclude_keywords: rule.exclude_keywords || [],
        pin_link_keywords: rule.pin_link_keywords || [],
        file_extensions_to_match: rule.file_extensions_to_match || [],
        transform_rules: rule.transform_rules || [],
      }))
      syncTransformFromRules()
      syncRulesToForm()
    }
    setMessage(`已保存 ${payload.length} 条转发规则，转发已进入运行态`)
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
      props.api, props.pluginId, 'forward/test', { text: testText.value }, { timeoutMs: 30000 },
    ))
    testResult.value = data
    setMessage('测试完成（未转发、未入队）')
  } catch (err) {
    setMessage(err?.message || '测试失败', false)
  } finally {
    busy.value = ''
  }
}

// ------------------------------------------------------------------ 流水分页

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

// 下拉项的 value 一律是 Number，v-model 也必须归一成 Number——Vuetify 的下拉
// 按严格比较找选项，字符串 v-model 匹配不到数字 value 时会**原样显示模型值**，
// 于是转发目标就显示成裸 ID（-1003229693136）。1.8.0 修正为与来源同口径。
function toChatId(value) {
  if (value === '' || value === null || value === undefined) return ''
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : ''
}

// 不在对话缓存里的会话（老规则 / 缓存过期 / 目标已不可见）：给个可识别的
// 占位名，别让用户对着一串裸 ID 猜。
function unknownChatTitle(id) {
  return `未知会话（${id}）`
}

// 下拉选项 = 对话列表 + 已保存但不在缓存里的 ID（老规则/缓存过期时保证 chips 仍能显示）
const selectItems = computed(() => {
  const items = dialogOptions.value.slice()
  const known = new Set(items.map(item => item.value))
  for (const rule of rules.value) {
    for (const raw of rule.source_ids || []) {
      const id = toChatId(raw)
      if (id !== '' && !known.has(id)) {
        items.push({ title: unknownChatTitle(id), value: id })
        known.add(id)
      }
    }
  }
  return items
})

// 转发目标下拉：同一份对话缓存 + 已保存的目标值兜底
const targetItems = computed(() => {
  const items = dialogOptions.value.slice()
  const known = new Set(items.map(item => item.value))
  for (const rule of rules.value) {
    const id = toChatId(rule.target_id)
    if (id !== '' && !known.has(id)) {
      items.push({ title: unknownChatTitle(id), value: id })
      known.add(id)
    }
  }
  return items
})

// 来源会话 ID → 标题（来自监控状态卡的会话反查结果，取不到就显示 ID）
const chatTitleMap = computed(() => {
  const map = {}
  for (const w of (watchedDetail.value || [])) {
    if (w.resolved && w.title) map[w.chat_id] = w.title
  }
  return map
})

// 冷却间隔展示：0 表示未设限，其余按「N 秒」
const gateIntervalText = computed(() => {
  const seconds = Number(status.value?.gate_interval ?? 0)
  return seconds > 0 ? `${seconds} 秒` : '未设限'
})

// 会话 ID → 对话名（优先用对话缓存里的原始 name，避免下拉标题里的「（类型）」后缀）
function chatNameById(id) {
  const numeric = Number(id)
  const found = (dialogs.value || []).find(item => Number(item.id) === numeric)
  return found ? found.name : unknownChatTitle(id)
}

// 折叠态概览标签：按规则真实内容动态生成（目标 / 置顶 / 扩展名 / 关键词 / 排除 / 转换）
function ruleSummary(rule) {
  const tags = []
  const targetId = toChatId(rule.target_id)
  tags.push(targetId === '' ? '→ 未选目标' : `→ ${chatNameById(targetId)}`)
  if (rule.pin_links_enabled) tags.push('置顶')
  if (rule.match_file_extensions) {
    const extensions = (rule.file_extensions_to_match || [])
      .map(ext => String(ext).trim().replace(/^\./, ''))
      .filter(Boolean)
    if (extensions.length) tags.push(extensions.join(' '))
  }
  if (rule.match_custom_keywords) tags.push(`关键词 ${(rule.custom_keywords || []).length}`)
  if ((rule.exclude_keywords || []).length) tags.push(`排除 ${rule.exclude_keywords.length}`)
  if (rule.enable_transform) {
    const count = (rule.transform_rules || []).length
    tags.push(count ? `转换 ${count}` : '内容转换')
  }
  return tags
}

// 媒体列完整名：片名（年份）+ 电视剧 SxxExx
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

function fmtTime(value) {
  return String(value || '').replace('T', ' ')
}

onMounted(async () => {
  await refreshAll()
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
.fwd-pane { display: flex; flex-direction: column; gap: 8px; }
.fwd-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.fwd-message { font-size: 13px; }
.fwd-status-head { display: flex; align-items: center; justify-content: flex-end; gap: 6px; flex-wrap: wrap; }
/* 运行状态正文：2×2 统计块，小灰标签 + 粗体数值 */
.fwd-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.fwd-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 7px 9px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}
.fwd-stat-label { font-size: 10.5px; line-height: 1.4; color: rgba(var(--v-theme-on-surface), 0.6); }
/* 数值 14px 粗体（600 与缓存面板统计块同口径），过长的会话名不撑破两列 */
.fwd-stat-value { font-size: 14px; font-weight: 600; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fwd-status-sub { margin-top: 6px; font-size: 12px; opacity: 0.75; line-height: 1.5; }
.fwd-warn { color: rgb(var(--v-theme-warning)); }
.fwd-actions { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-top: 6px; }
.fwd-rule { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; margin-bottom: 8px; }
.fwd-rule:last-child { margin-bottom: 0; }
/* 卡片头：折叠箭头 + 来源下拉占满剩余宽度 + 概览标签，开关与删除靠右；点整行切换折叠 */
.fwd-rule-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; cursor: pointer; }
.fwd-rule-caret { flex: 0 0 auto; width: 12px; font-size: 12px; line-height: 1; text-align: center; opacity: 0.65; user-select: none; }
.fwd-rule-head:hover .fwd-rule-caret { opacity: 1; }
/* 下拉自身要能正常点击，所以这一格不继承整行的 pointer */
.fwd-rule-source { flex: 1 1 260px; min-width: 200px; cursor: default; }
.fwd-rule-tags { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.fwd-rule-tag {
  display: inline-flex;
  align-items: center;
  max-width: 180px;
  padding: 2px 8px;
  overflow: hidden;
  font-size: 11.5px;
  line-height: 1.5;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: rgba(var(--v-theme-on-surface), 0.75);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
}
.fwd-rule-tools { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.fwd-rule-switch { display: flex; align-items: center; gap: 4px; }
.fwd-switch-label { font-size: 13px; color: rgba(var(--v-theme-on-surface), 0.7); white-space: nowrap; }
/* 正文网格：每格 220px 起自适应换行，同一行由 grid 自动等高对齐 */
.fwd-rule-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; margin-top: 8px; }
.fwd-group { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.fwd-group-title { font-size: 12.5px; font-weight: 600; opacity: 0.8; }
.fwd-hint { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.5; }
/* 折叠说明：跟规则卡片留 8px 呼吸，往下接保存按钮 */
.fwd-rules-hint { margin: 8px 2px 0; }
/* 组内纵向 gap 为 6px，提示文字再上提 2px，与上方控件净间距正好 4px */
.fwd-group > .fwd-hint { margin-top: -2px; }
.fwd-empty {
  padding: 12px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.fwd-test-result { margin-top: 6px; }
.fwd-test-line { font-size: 13px; margin-bottom: 4px; }
.fwd-test-none { opacity: 0.7; }
.fwd-test-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.fwd-test-name { font-size: 13px; }
.fwd-test-off { margin-left: 6px; }
.fwd-test-msg { font-size: 12px; opacity: 0.75; white-space: normal; word-break: break-all; }
.fwd-filter { flex: 0 0 160px; max-width: 200px; }
.fwd-hits { font-size: 12.5px; }
.fwd-hits .fwd-nowrap { white-space: nowrap; }
.fwd-hits-time { white-space: nowrap; opacity: 0.75; }
.fwd-hits-source { white-space: nowrap; opacity: 0.8; }
.fwd-hits-none { opacity: 0.4; }
.fwd-hits-detail { opacity: 0.75; }
.fwd-hits-empty { text-align: center; padding: 12px; opacity: 0.6; }
.fwd-pager { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
.fwd-pager-info { font-size: 12px; opacity: 0.7; }
.fwd-hits-tools { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
.fwd-hits-search { flex: 1 1 220px; max-width: 320px; }
</style>
