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

    <!-- 运行状态 -->
    <VCard flat class="fwd-card">
      <VCardTitle class="text-subtitle-2">运行状态</VCardTitle>
      <VCardText>
        <div class="fwd-status">
          <VChip size="small" variant="tonal" :color="status?.enabled ? 'success' : 'default'" label>
            转发{{ status?.enabled ? '已启用' : '未启用' }}
          </VChip>
          <VChip size="small" variant="tonal" color="primary" label>
            规则 {{ status?.rules_count ?? 0 }}
          </VChip>
          <VChip size="small" variant="tonal" color="info" label>
            关心会话 {{ status?.watched_chats ?? 0 }}
          </VChip>
          <VChip size="small" variant="tonal" color="default" label>
            转换条目 {{ status?.transform_rules_count ?? 0 }}
          </VChip>
          <VChip v-if="(status?.gate_interval ?? 0) > 0" size="small" variant="tonal" color="default" label>
            全局冷却 {{ status.gate_interval }} 秒
          </VChip>
          <VChip v-if="(status?.flood_remaining ?? 0) > 0" size="small" variant="tonal" color="warning" label>
            FloodWait 退避中（约 {{ status.flood_remaining }} 秒）
          </VChip>
        </div>
        <div class="fwd-status-sub">
          <span>转发只按关键词与扩展名匹配，与订阅无关；识别仅用于展示，识别不出也能转发。</span>
        </div>
        <div class="fwd-actions">
          <VBtn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="refreshAll">
            刷新状态
          </VBtn>
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
      <VCardText>
        <div v-if="!rules.length" class="fwd-empty">
          还没有规则。点「添加规则」创建第一条：选择来源频道与转发目标，保存后立即生效。
        </div>

        <VCard
          v-for="(rule, index) in rules"
          :key="rule.id || index"
          flat
          class="fwd-rule"
        >
          <VCardText>
            <div class="fwd-rule-head">
              <VTextField
                v-model="rule.name"
                label="规则名称"
                density="compact"
                variant="outlined"
                hide-details
                class="fwd-rule-name"
              />
              <VSwitch v-model="rule.enabled" color="success" hide-details inset />
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

            <div class="fwd-rule-grid">
              <div class="fwd-chats">
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
                <div class="fwd-chats-add">
                  <VTextField
                    v-model="manualIds[rule.id || index]"
                    label="手动添加会话 ID"
                    placeholder="-1001234567890"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="fwd-chats-input"
                    @keyup.enter="addManualId(rule, index)"
                  />
                  <VBtn size="small" variant="text" prepend-icon="mdi-plus" @click="addManualId(rule, index)">
                    添加
                  </VBtn>
                </div>
                <div class="fwd-hint">
                  下拉项来自「TG 凭证」页的对话列表缓存；没有缓存时可手动输入 ID（含 -100 前缀）。
                </div>
              </div>

              <div class="fwd-target">
                <VTextField
                  v-model="rule.target_id"
                  label="转发目标会话 ID"
                  placeholder="-1003229693136"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :error="Boolean(rule.target_id) && !isNumericId(rule.target_id)"
                  error-message="需要数字会话 ID"
                />
                <div class="fwd-hint">
                  转发到该会话（个人号，受全局冷却与 FloodWait 退避约束）。
                  目标必须是当前账号能看到的会话，否则转发会失败并重试。
                </div>
              </div>
            </div>

            <!-- 逻辑一：自定义关键词 -->
            <div class="fwd-logic">
              <div class="fwd-logic-title">逻辑一（关键词）</div>
              <div class="fwd-logic-grid fwd-logic-grid-one">
                <div>
                  <VSwitch v-model="rule.match_custom_keywords" color="primary" hide-details inset>
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
                    class="fwd-keywords"
                  />
                  <div v-else class="fwd-hint">启用后只有命中关键词的消息才转发；不启用 = 该级不设限。</div>
                </div>
              </div>
            </div>

            <!-- 逻辑二：扩展名 -->
            <div class="fwd-logic">
              <div class="fwd-logic-title">逻辑二（文件扩展名）</div>
              <div class="fwd-logic-grid">
                <div>
                  <VSwitch v-model="rule.match_file_extensions" color="primary" hide-details inset>
                    <template #label><span class="fwd-switch-label">按扩展名过滤</span></template>
                  </VSwitch>
                  <div class="fwd-hint">消息中出现指定扩展名（如 .mkv / [mp4]）才算命中。</div>
                </div>
                <div>
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
                    class="fwd-keywords"
                  />
                </div>
                <div class="fwd-hint fwd-logic-note">
                  逻辑一与逻辑二之间<strong>恒为 AND</strong>：两者都启用时必须同时满足。
                </div>
              </div>
            </div>

            <!-- 置顶与转换 -->
            <div class="fwd-logic">
              <div class="fwd-logic-title">置顶与内容转换</div>
              <div class="fwd-logic-grid">
                <div>
                  <VSwitch v-model="rule.pin_links_enabled" color="primary" hide-details inset>
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
                    class="fwd-keywords"
                  />
                  <div v-else class="fwd-hint">置顶以链接为对象：没有链接的消息不置顶。</div>
                </div>
                <div>
                  <VSwitch v-model="rule.enable_transform" color="primary" hide-details inset>
                    <template #label><span class="fwd-switch-label">内容转换</span></template>
                  </VSwitch>
                  <div class="fwd-hint">转换后以新内容发送（不改动原消息）。</div>
                </div>
                <div>
                  <VTextarea
                    v-if="rule.enable_transform"
                    v-model="transformText[rule.id || index]"
                    label="转换规则（每行一条：原文 -> 替换文，支持正则）"
                    placeholder="广告词.*-> &#10;@\w+ -> "
                    rows="3"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="fwd-transform"
                    @update:model-value="syncTransform(rule, index)"
                  />
                </div>
              </div>
            </div>
          </VCardText>
        </VCard>

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
      <VCardText>
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
      <VCardText>
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
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPluginApi, postPluginApi, putPluginApi, unwrap } from '../api'

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
const manualIds = ref({})
// 转换规则用多行文本编辑（提交时拆行）；键与规则 id 对应
const transformText = ref({})

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
      source_ids: Array.isArray(rule.source_ids) ? rule.source_ids.map(Number) : [],
      target_id: rule.target_id ? String(rule.target_id) : '',
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: Array.isArray(rule.custom_keywords) ? rule.custom_keywords : [],
      pin_links_enabled: Boolean(rule.pin_links_enabled),
      pin_link_keywords: Array.isArray(rule.pin_link_keywords) ? rule.pin_link_keywords : [],
      match_file_extensions: Boolean(rule.match_file_extensions),
      file_extensions_to_match: Array.isArray(rule.file_extensions_to_match) ? rule.file_extensions_to_match : [],
      enable_transform: Boolean(rule.enable_transform),
      transform_rules: Array.isArray(rule.transform_rules) ? rule.transform_rules : [],
      enabled: rule.enabled !== false,
    }))
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
    const data = unwrap(await getPluginApi(
      props.api, props.pluginId, `forward/hits?${params.toString()}`, { timeoutMs: 15000 },
    ))
    hits.value = data?.items || []
    hitsTotal.value = data?.total || 0
  } catch (err) {
    setMessage(err?.message || '读取转发流水失败', false)
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
  syncRulesToForm()
}

function removeRule(index) {
  const rule = rules.value[index]
  if (rule) delete transformText.value[rule.id]
  rules.value.splice(index, 1)
  syncRulesToForm()
}

function isNumericId(value) {
  return /^-?\d+$/.test(String(value ?? '').trim())
}

function addManualId(rule, index) {
  const raw = String(manualIds.value[rule.id || index] || '')
  const parts = raw.split(/[,，\s]+/).map(part => part.trim()).filter(Boolean)
  const added = []
  for (const part of parts) {
    if (!isNumericId(part)) continue
    const id = Number(part)
    if (id && !rule.source_ids.includes(id)) {
      rule.source_ids.push(id)
      added.push(id)
    }
  }
  manualIds.value[rule.id || index] = ''
  if (!added.length) {
    setMessage('没有可添加的数字 ID（检查格式，如 -1001234567890）', false)
  } else {
    setMessage(`已添加 ${added.length} 个会话 ID`)
  }
}

async function saveRules() {
  if (busy.value) return
  const missing = rules.value.find(rule => !isNumericId(rule.target_id))
  if (missing) {
    setMessage(`规则「${missing.name || '未命名'}」还没填转发目标会话 ID`, false)
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
      pin_links_enabled: Boolean(rule.pin_links_enabled),
      pin_link_keywords: (rule.pin_link_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      match_file_extensions: Boolean(rule.match_file_extensions),
      file_extensions_to_match: (rule.file_extensions_to_match || []).map(ext => String(ext).trim().replace(/^\./, '')).filter(Boolean),
      enable_transform: Boolean(rule.enable_transform),
      transform_rules: (rule.transform_rules || []).map(line => String(line).trim()).filter(Boolean),
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

// 下拉选项 = 对话列表 + 已选中的手动 ID（否则手动添加的 ID 在 chips 里显示不出名称）
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

function decisionLabel(value) {
  const found = decisions.value.find(item => item.value === value)
  return found ? found.title : value
}

function decisionColor(value) {
  if (value === 'hit') return 'success'
  if (value === 'failed') return 'error'
  if (value === 'skipped_unrecognized') return 'warning'
  return 'default'
}

// 来源会话 ID → 标题（来自监控状态卡的会话反查结果，取不到就显示 ID）
const chatTitleMap = computed(() => {
  const map = {}
  for (const w of (watchedDetail.value || [])) {
    if (w.resolved && w.title) map[w.chat_id] = w.title
  }
  return map
})

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
})
</script>

<style scoped>
.fwd-pane { display: flex; flex-direction: column; gap: 12px; }
.fwd-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.fwd-message { font-size: 13px; }
.fwd-status { display: flex; gap: 6px; flex-wrap: wrap; }
.fwd-status-sub { margin-top: 8px; font-size: 12px; opacity: 0.75; line-height: 1.7; }
.fwd-warn { color: rgb(var(--v-theme-warning)); }
.fwd-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
.fwd-rule { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 10px; margin-bottom: 10px; }
.fwd-rule-head { display: flex; gap: 10px; align-items: center; }
.fwd-rule-name { flex: 1 1 auto; }
.fwd-rule-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; margin-top: 10px; }
.fwd-logic { margin-top: 12px; padding-top: 10px; border-top: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity)); }
.fwd-logic-title { font-size: 12.5px; font-weight: 600; opacity: 0.8; margin-bottom: 6px; }
.fwd-logic-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
.fwd-logic-grid-one { grid-template-columns: 1fr; }
.fwd-logic-note { align-self: end; }
@media (max-width: 900px) {
  .fwd-rule-grid { grid-template-columns: 1fr; }
  .fwd-logic-grid { grid-template-columns: 1fr; }
}
.fwd-chats-add { display: flex; gap: 6px; align-items: center; margin-top: 8px; }
.fwd-chats-input { flex: 1 1 auto; }
.fwd-target { display: flex; flex-direction: column; gap: 6px; }
.fwd-switch-label { font-size: 13px; }
.fwd-keywords { margin-top: 6px; }
.fwd-transform { margin-top: 6px; }
.fwd-hint { margin-top: 6px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.6; }
.fwd-empty {
  padding: 18px 12px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.fwd-test-result { margin-top: 12px; }
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
.fwd-hits-empty { text-align: center; padding: 16px; opacity: 0.6; }
.fwd-pager { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.fwd-pager-info { font-size: 12px; opacity: 0.7; }
</style>
