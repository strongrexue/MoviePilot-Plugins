<script setup>
/**
 * 洗版规则（1.13.34）：独立板块。
 *
 * 数据源直接是表单里的 ``cache_wash_rules``（保存配置时整份下发）：
 * - 七维字典序：行序＝优先级（质量锁第 1），chip 左右＝维度内优劣，✓/✕ 只决定是否保留；
 * - 未列出值默认排除（可按维切垫底/置顶纳入）；
 * - 体积维：由大到小 + 小于 N MB / 大于 N GB 硬闸；
 * - 收口：同集每轮最多推几条（TopN）、体积容差、比对来源三源。
 */
import { computed, onMounted, ref } from 'vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
})

const form = computed(() => props.config.form)

const WASH_ORDER = ['quality', 'resolution', 'effect', 'audio', 'codec', 'ext', 'size']
const WASH_DEFAULTS = {
  quality: [['remux', 1], ['bluray', 1], ['webdl', 1], ['webrip', 1], ['hdtv', 0], ['cam', 0], ['ts', 0]],
  resolution: [['2160p', 1], ['1080p', 1], ['720p', 1]],
  effect: [['dv_hdr', 1], ['dv', 1], ['hdr10p', 1], ['hdr10', 1], ['hdr', 1], ['sdr', 1]],
  audio: [['atmos', 1], ['truehd', 1], ['dtshd', 1], ['dtsx', 1], ['dts', 1], ['eac3', 1], ['ac3', 1], ['flac', 1], ['aac', 1]],
  codec: [['av1', 1], ['hevc', 1], ['h264', 1], ['vp9', 1], ['other', 1]],
  ext: [['mkv', 1], ['mp4', 1], ['ts', 1], ['iso', 1], ['rmvb', 1], ['avi', 1], ['mov', 0], ['mpeg', 0], ['mpg', 0], ['wmv', 0], ['other', 0]],
}
const dimLabels = {
  quality: '质量', resolution: '分辨率', effect: '色彩模式',
  audio: '音频规格', codec: '视频编码', ext: '扩展名', size: '文件体积',
}
const valueLabels = {
  remux: 'REMUX', bluray: 'BluRay', webdl: 'WEB-DL', webrip: 'WEBRip', hdtv: 'HDTV', cam: 'CAM', ts: 'TS',
  '2160p': '4K / 2160p', '1080p': '1080p', '720p': '720p 及以下',
  dv_hdr: 'DV & HDR', dv: 'DV', hdr10p: 'HDR10+', hdr10: 'HDR10', hdr: 'HDR', sdr: 'SDR',
  atmos: 'Atmos', truehd: 'TrueHD', dtshd: 'DTS-HD MA', dtsx: 'DTS-X', dts: 'DTS',
  eac3: 'EAC3', ac3: 'AC3', flac: 'FLAC', aac: 'AAC',
  av1: 'AV1', hevc: 'HEVC (H.265)', h264: 'H.264', vp9: 'VP9',
  mkv: 'MKV', mp4: 'MP4', iso: 'ISO', rmvb: 'RMVB', avi: 'AVI', mov: 'MOV',
  mpeg: 'MPEG', mpg: 'MPG', wmv: 'WMV', other: '其他',
}
const unlistedOptions = [
  { value: 'deny', title: '默认排除' },
  { value: 'bottom', title: '垫底纳入' },
  { value: 'top', title: '置顶纳入' },
]
const sourceOptions = [
  { value: 'pushed', title: '已推送基线' },
  { value: 'library', title: '媒体库已存在' },
  { value: 'history', title: '下载历史（PT）' },
]

function normalizeWashRules(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  const values = {}
  Object.keys(WASH_DEFAULTS).forEach((dim) => {
    values[dim] = WASH_DEFAULTS[dim].map(([v, on]) => ({ v, on: Boolean(on) }))
  })
  const incoming = source.values && typeof source.values === 'object' ? source.values : {}
  Object.keys(incoming).forEach((dim) => {
    if (!values[dim] || !Array.isArray(incoming[dim]) || !incoming[dim].length) return
    const merged = []
    const seen = new Set()
    incoming[dim].forEach((item) => {
      const value = typeof item === 'string' ? item : (item && item.v)
      if (!value || seen.has(value)) return
      seen.add(value)
      merged.push({ v: value, on: typeof item === 'object' && item ? item.on !== false : true })
    })
    values[dim].forEach((item) => { if (!seen.has(item.v)) merged.push(item) })
    values[dim] = merged
  })
  const rawOrder = Array.isArray(source.order) ? source.order : []
  const order = ['quality']
  rawOrder.forEach((dim) => {
    if (WASH_ORDER.includes(dim) && dim !== 'quality' && !order.includes(dim)) order.push(dim)
  })
  WASH_ORDER.forEach((dim) => { if (!order.includes(dim)) order.push(dim) })
  const unlisted = {}
  const rawUnlisted = source.unlisted && typeof source.unlisted === 'object' ? source.unlisted : {}
  WASH_ORDER.forEach((dim) => {
    if (dim === 'size') return
    const policy = rawUnlisted[dim]
    unlisted[dim] = ['deny', 'bottom', 'top'].includes(policy) ? policy : 'deny'
  })
  const rawSize = source.size && typeof source.size === 'object' ? source.size : {}
  return {
    enabled: source.enabled === true,
    order,
    values,
    unlisted,
    size: {
      min_mb: Number(rawSize.min_mb) || 0,
      max_gb: Number(rawSize.max_gb) || 0,
      prefer: rawSize.prefer === 'asc' ? 'asc' : 'desc',
    },
    top_n: source.top_n === undefined ? 1 : Math.max(0, Math.min(50, Number(source.top_n) || 0)),
    size_tolerance_pct: source.size_tolerance_pct === undefined
      ? 5 : Math.max(0, Math.min(50, Number(source.size_tolerance_pct) || 0)),
    compare_sources: Array.isArray(source.compare_sources) && source.compare_sources.length
      ? source.compare_sources.filter((item) => ['pushed', 'library', 'history'].includes(item))
      : ['pushed', 'library', 'history'],
  }
}

onMounted(() => {
  form.value.cache_wash_rules = normalizeWashRules(form.value.cache_wash_rules)
})

const rules = computed(() => form.value.cache_wash_rules || normalizeWashRules({}))

const dragRow = ref(-1)
const dragChip = ref(null)

function valueLabel(value) {
  return valueLabels[value] || value
}

function onRowDragStart(index) {
  if (rules.value.order[index] === 'quality') return
  dragRow.value = index
}

function onRowDrop(index) {
  const from = dragRow.value
  dragRow.value = -1
  if (from < 0 || from === index) return
  const list = rules.value.order.slice()
  if (list[from] === 'quality' || list[index] === 'quality') return
  const [moved] = list.splice(from, 1)
  list.splice(index, 0, moved)
  rules.value.order = list
}

function onChipDragStart(dim, index) {
  if (dim === 'size') return
  dragChip.value = { dim, index }
}

function onChipDrop(dim, index) {
  const from = dragChip.value
  dragChip.value = null
  if (!from || from.dim !== dim || from.index === index) return
  const list = rules.value.values[dim]
  if (!list) return
  const [moved] = list.splice(from.index, 1)
  list.splice(index, 0, moved)
}

function toggleChip(dim, item) {
  item.on = !item.on
}

function toggleSizePrefer() {
  const size = rules.value.size
  size.prefer = size.prefer === 'desc' ? 'asc' : 'desc'
}

function toggleSource(value, on) {
  const list = (rules.value.compare_sources || []).slice()
  const index = list.indexOf(value)
  if (on && index < 0) list.push(value)
  if (!on && index >= 0) list.splice(index, 1)
  if (!list.length) list.push('pushed')
  rules.value.compare_sources = list
}

const unlistedPolicy = computed({
  get() {
    const map = rules.value.unlisted || {}
    const keys = Object.keys(map)
    if (!keys.length) return 'deny'
    const first = map[keys[0]]
    return keys.every((key) => map[key] === first) ? first : 'deny'
  },
  set(value) {
    const map = {}
    rules.value.order.forEach((dim) => {
      if (dim !== 'size') map[dim] = value
    })
    rules.value.unlisted = map
  },
})

const examples = [
  { a: '1080p REMUX', b: '4K WEB-DL', keep: '推 A', why: '质量 REMUX > WEB-DL' },
  { a: '4K REMUX', b: '1080p REMUX', keep: '推 A', why: '质量相同 → 分辨率 4K 胜' },
  { a: '4K WEB-DL', b: '1080p WEB-DL', keep: '推 A', why: '质量相同 → 分辨率 4K 胜' },
  { a: '1080p REMUX', b: '720p REMUX', keep: '推 A', why: '质量相同 → 分辨率 1080p 胜' },
  { a: '4K WEB-DL 12G', b: '4K WEB-DL 12.3G', keep: '持平', why: '同质量同体积（±5% 容差）' },
]
</script>

<template>
  <div class="wash-pane">
    <VCard flat class="wash-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">启用洗版规则</VCardTitle>
        <VCardSubtitle class="text-caption">
          单一总开关（含质量门禁语义）。关闭 = 推送完全不洗版，按原逻辑只判缺失。
        </VCardSubtitle>
      </VCardItem>
      <VCardText class="wash-body">
        <div class="wash-switch">
          <VSwitch
            v-model="rules.enabled"
            color="primary"
            density="compact"
            hide-details
            label="启用洗版（开启后：准入过滤 + 逐维比较 + TopN 全部生效）"
          />
        </div>
      </VCardText>
    </VCard>

    <VCard flat class="wash-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">资源权重</VCardTitle>
        <VCardSubtitle class="text-caption">
          每一行就是一个维度，行序即优先级；质量锁定第 1 不可拖。行内 chip 左右＝维度内优劣。
        </VCardSubtitle>
      </VCardItem>
      <VCardText class="wash-body">
        <div class="wash-rules">
          <div class="wash-head">
            <span class="wash-hint">
              行序拖 ⋮⋮ 调整，chip 位置＝维度内优劣，「✓/✕」只决定该值是否保留；
              只有<strong>逐维更优</strong>才推，同质量同分辨率同体积（±容差）视为持平不推。
            </span>
          </div>
          <div
            v-for="(dim, index) in rules.order"
            :key="dim"
            class="wash-row"
            :class="{ 'wash-row-locked': dim === 'quality' }"
            :draggable="dim !== 'quality'"
            @dragstart="onRowDragStart(index)"
            @dragover.prevent
            @drop="onRowDrop(index)"
            @dragend="dragRow = -1"
          >
            <span class="wash-grip" :class="{ 'wash-grip-off': dim === 'quality' }">⋮⋮</span>
            <span class="wash-index">{{ index + 1 }}</span>
            <span class="wash-dim">{{ dimLabels[dim] }}</span>
            <span v-if="dim === 'quality'" class="wash-lock">锁定</span>
            <div v-if="dim === 'size'" class="wash-chips">
              <VChip
                size="small"
                :color="rules.size.prefer === 'desc' ? 'primary' : undefined"
                :variant="rules.size.prefer === 'desc' ? 'flat' : 'outlined'"
                class="wash-chip"
                @click="toggleSizePrefer"
              >
                由大到小
              </VChip>
              <VChip size="small" variant="outlined" class="wash-chip wash-chip-input">
                小于
                <input v-model.number="rules.size.min_mb" type="number" min="0" class="wash-input" />
                MB
              </VChip>
              <VChip size="small" variant="outlined" class="wash-chip wash-chip-input">
                大于
                <input v-model.number="rules.size.max_gb" type="number" min="0" class="wash-input" />
                GB
              </VChip>
            </div>
            <div v-else class="wash-chips">
              <VChip
                v-for="(item, chipIndex) in rules.values[dim]"
                :key="item.v"
                size="small"
                :color="item.on ? 'primary' : undefined"
                :variant="item.on ? 'flat' : 'outlined'"
                class="wash-chip"
                :class="{ 'wash-chip-off': !item.on }"
                draggable="true"
                @dragstart.stop="onChipDragStart(dim, chipIndex)"
                @dragover.prevent.stop
                @drop.stop="onChipDrop(dim, chipIndex)"
                @click="toggleChip(dim, item)"
              >
                {{ valueLabel(item.v) }}
              </VChip>
            </div>
          </div>
          <div class="wash-foot-note">
            未在 chip 里的值：默认排除（可切「垫底纳入 / 置顶纳入」）；画质/体积解析不出的候选不参与比较，由 TopN 兜底。
          </div>
        </div>
      </VCardText>
    </VCard>

    <VCard flat class="wash-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">判定与收口</VCardTitle>
        <VCardSubtitle class="text-caption">「逐维更优」才推；同质量同体积不重推。</VCardSubtitle>
      </VCardItem>
      <VCardText class="wash-body">
        <div class="wash-foot">
          <div class="wash-field">
            <span class="wash-hint">未在排列里的值</span>
            <VSelect
              v-model="unlistedPolicy"
              :items="unlistedOptions"
              item-title="title"
              item-value="value"
              density="compact"
              variant="outlined"
              hide-details
            />
          </div>
          <div class="wash-field">
            <span class="wash-hint">同集每轮最多推几条（0=不限）</span>
            <VTextField
              v-model.number="rules.top_n"
              type="number"
              min="0"
              max="50"
              density="compact"
              variant="outlined"
              hide-details
            />
          </div>
          <div class="wash-field">
            <span class="wash-hint">体积容差 ±%</span>
            <VTextField
              v-model.number="rules.size_tolerance_pct"
              type="number"
              min="0"
              max="50"
              density="compact"
              variant="outlined"
              hide-details
            />
          </div>
        </div>
        <div class="wash-sources">
          <span class="wash-hint">比对来源</span>
          <VCheckbox
            v-for="item in sourceOptions"
            :key="item.value"
            :model-value="(rules.compare_sources || []).includes(item.value)"
            density="compact"
            hide-details
            :label="item.title"
            class="wash-source"
            @update:model-value="toggleSource(item.value, $event)"
          />
        </div>
        <div class="wash-foot-note">
          任一处已有「同质量 + 同分辨率 + 同体积（±容差）」判为持平、不推；只有逐维比较后严格更优才升级。
        </div>
      </VCardText>
    </VCard>

    <VCard flat class="wash-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">判定示例（按默认顺序）</VCardTitle>
        <VCardSubtitle class="text-caption">质量内置第一，所以片源档位先决胜。</VCardSubtitle>
      </VCardItem>
      <VCardText class="wash-body">
        <table class="wash-table">
          <thead>
            <tr>
              <th>候选 A</th>
              <th>候选 B</th>
              <th>结果</th>
              <th>依据</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in examples" :key="index">
              <td>{{ row.a }}</td>
              <td>{{ row.b }}</td>
              <td class="wash-keep">{{ row.keep }}</td>
              <td class="wash-why">{{ row.why }}</td>
            </tr>
          </tbody>
        </table>
      </VCardText>
    </VCard>
  </div>
</template>

<style scoped>
.wash-pane { display: flex; flex-direction: column; gap: 8px; }
.wash-card {
  background: rgba(var(--v-theme-on-surface), 0.04) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10);
  border-radius: 10px;
}
.wash-card :deep(.v-card-item) { padding: 10px 12px; }
.wash-card :deep(.v-card-title) { padding: 0; }
.wash-card :deep(.v-card-subtitle) { padding: 2px 0 0; }
.wash-card :deep(.v-card-text) { padding: 8px 12px 10px; }
.wash-body { display: flex; flex-direction: column; gap: 8px; }

.wash-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 0 2px 6px;
  border-bottom: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
}

.wash-rules {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10);
  border-radius: 10px;
}

.wash-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.wash-hint { font-size: 11.5px; color: rgba(var(--v-theme-on-surface), 0.66); }

.wash-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-bottom: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
  cursor: grab;
}
.wash-row:last-of-type { border-bottom: none; }
.wash-row-locked { cursor: default; }
.wash-grip { font-size: 11px; line-height: 1; letter-spacing: -1px; color: rgba(var(--v-theme-on-surface), 0.45); }
.wash-grip-off { opacity: 0.25; }
.wash-index { min-width: 14px; font-size: 11px; text-align: center; color: rgba(var(--v-theme-on-surface), 0.55); }
.wash-dim { min-width: 62px; font-size: 12px; font-weight: 600; }
.wash-lock {
  font-size: 10px;
  padding: 0 5px;
  border-radius: 999px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.14);
}
.wash-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.wash-chip { font-size: 12px; height: 24px; }
.wash-chip-off { opacity: 0.55; text-decoration: line-through; }
.wash-chip-input { display: inline-flex; align-items: center; gap: 3px; }
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
.wash-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }

.wash-foot {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 8px;
  padding-top: 6px;
  border-top: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
}
.wash-field { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.wash-sources { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.wash-source { font-size: 11px; }
.wash-foot-note {
  font-size: 11px;
  line-height: 1.6;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding-top: 6px;
  border-top: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
}

.wash-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.wash-table th {
  text-align: left;
  font-weight: 600;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding: 4px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.10);
}
.wash-table td {
  padding: 6px 8px;
  border-bottom: 1px dashed rgba(var(--v-theme-on-surface), 0.08);
}
.wash-table tr:last-child td { border-bottom: none; }
.wash-keep { color: rgb(var(--v-theme-success)); font-weight: 600; }
.wash-why { color: rgba(var(--v-theme-on-surface), 0.66); }
</style>
