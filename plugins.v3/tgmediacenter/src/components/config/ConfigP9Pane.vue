<script setup>
import { computed, onMounted, ref } from 'vue'
import { getPluginApi, unwrap } from '../api'

/**
 * ⑩ P9 重复获取治理面板（1.9.0 引入 / 1.9.1 移除 R0 / 1.10.0 闸门 A 上线）。
 *
 * 背景：PT 路（MP 订阅 → 下载 → 115）与 TG 路（本插件转存 → 115）写进同一个
 * 115 + STRM + Emby，会重复拿到同一部作品。治理分两向：
 *
 * - **前向闸门 A**（1.10.0 起提供）：TG 推送前先看「PT 路是不是已经在管」，
 *   默认关；判定细节见 services/forward_gate.py；
 * - **反向 R0 开关**（1.9.0 曾提供）：真机验证**否决**——暂停宿主内置的
 *   「新增订阅搜索」后，新增订阅照旧被搜索（首次搜索是 subscribe.added
 *   事件驱动，那个 5 分钟 job 只是兜底），开关无收益，1.9.1 已移除。
 * - **反向闸门 R1**（1.13.8 提供）：开关已迁到「消息缓存 → 缓存频道与范围」，
 *   本分区只保留探针与前向闸门。
 *
 * 版面（对齐豆瓣中心「运行总览」）：四张分区卡——运行链路 / 状态 / 宿主能力探针 /
 * 前向闸门；说明一律压到一行小字，探针详情按行展开，默认不占屏。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
})

const guard = ref(null)
const loading = ref(false)
const message = ref('')
const messageOk = ref(true)

const probe = computed(() => guard.value?.probe || null)
const items = computed(() => probe.value?.items || [])

/** 运行链路：前向闸门的判定顺序（纯展示，不参与逻辑） */
const flowSteps = ['媒体库已有？', '下载历史近 T', '活跃种？', 'PT 在途 / 等成熟期 / 放行']

/** 探针通过数 / 总数（只读现有 probe.items） */
const probeOkCount = computed(() => items.value.filter(item => item.ok).length)
const probeTotal = computed(() => items.value.length)
const probeCountText = computed(() => (probe.value ? `${probeOkCount.value}/${probeTotal.value}` : '—'))

/** 顶部汇总一行：全部通过 / N 项未通过 + 探测时间 */
const probeSummary = computed(() => {
  const data = probe.value
  if (!data) return ''
  const bad = items.value.filter(item => !item.ok).length
  const text = data.ok ? '全部通过' : `${bad} 项未通过`
  return data.checked_at ? `${text} · 探测于 ${data.checked_at}` : text
})

/** 探针详情按行展开，默认全部收起（避免大段 app.sdk... 文字占屏） */
const expanded = ref({})
function toggleDetail(key) {
  expanded.value = { ...expanded.value, [key]: !expanded.value[key] }
}

function setMessage(text, ok = true) {
  message.value = text || ''
  messageOk.value = ok
}

async function load() {
  loading.value = true
  try {
    guard.value = unwrap(await getPluginApi(props.api, props.pluginId, 'p9/guard', { timeoutMs: 30000 }))
  } catch (err) {
    setMessage(err?.message || '读取 P9 状态失败', false)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p9-pane">
    <VAlert
      v-if="message"
      :type="messageOk ? 'info' : 'warning'"
      variant="tonal"
      density="comfortable"
      class="p9-message"
    >{{ message }}</VAlert>

    <VProgressLinear v-if="loading" indeterminate color="primary" height="2" />

    <!-- 1) 运行链路：一行 chips 展示前向闸门的判定顺序 -->
    <VCard flat class="p9-card">
      <VCardItem>
        <VCardTitle class="p9-card-title">运行链路</VCardTitle>
        <VCardSubtitle class="p9-card-sub">
          只按「媒体身份」判断 PT 路与 TG 路谁在管，不在目录或命名上做任何约定。
        </VCardSubtitle>
      </VCardItem>
      <VCardText>
        <div class="p9-flow">
          <template v-for="(step, index) in flowSteps" :key="step">
            <span v-if="index" class="p9-flow-arrow">→</span>
            <span class="p9-flow-chip">{{ step }}</span>
          </template>
        </div>
        <div class="p9-flow-hint">命中以上任一环节就按对应结论处理，不命中则照常推送 115。</div>
      </VCardText>
    </VCard>

    <!-- 2) 状态：一行 4 个统计块（窄屏 2×2），样式与缓存/监控面板一致 -->
    <VCard flat class="p9-card">
      <VCardItem>
        <VCardTitle class="p9-card-title">状态</VCardTitle>
        <VCardSubtitle class="p9-card-sub">探针结论与闸门当前生效值</VCardSubtitle>
      </VCardItem>
      <VCardText>
        <div class="p9-stat-grid">
          <div class="p9-stat">
            <div class="p9-stat-label">探针通过</div>
            <div class="p9-stat-value">{{ probeCountText }}</div>
          </div>
          <div class="p9-stat">
            <div class="p9-stat-label">前向闸门</div>
            <div class="p9-stat-value">{{ config.form.p9_forward_gate_enabled ? '已开启' : '已关闭' }}</div>
          </div>
          <div class="p9-stat">
            <div class="p9-stat-label">成熟期 T</div>
            <div class="p9-stat-value">{{ config.form.p9_maturity_hours ?? 0 }} 小时</div>
          </div>
          <div class="p9-stat">
            <div class="p9-stat-label">活跃性细化</div>
            <div class="p9-stat-value">{{ config.form.p9_check_downloader ? '开启' : '关闭' }}</div>
          </div>
        </div>
      </VCardText>
    </VCard>

    <!-- 3) 宿主能力探针：6 项压成紧凑列表，详情按行展开 -->
    <VCard flat class="p9-card">
      <VCardItem>
        <VCardTitle class="p9-card-title">宿主能力探针</VCardTitle>
        <VCardSubtitle class="p9-card-sub">闸门依赖的宿主能力，只读探测，不改任何状态。</VCardSubtitle>
        <template #append>
          <VBtn
            size="small"
            variant="text"
            prepend-icon="mdi-radar"
            :loading="loading"
            @click="load"
          >重新探测</VBtn>
        </template>
      </VCardItem>
      <VCardText v-if="probe">
        <div class="p9-probe-summary">
          <VIcon
            :icon="probe.ok ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline'"
            :color="probe.ok ? 'success' : 'warning'"
            size="14"
          />
          <span>{{ probeSummary }}</span>
        </div>
        <div v-for="item in items" :key="item.key" class="p9-probe-row">
          <div class="p9-probe-line">
            <VIcon
              :icon="item.ok ? 'mdi-check' : 'mdi-close'"
              :color="item.ok ? 'success' : 'error'"
              size="14"
              class="p9-probe-icon"
            />
            <span class="p9-probe-label">{{ item.label }}</span>
            <button
              type="button"
              class="p9-probe-toggle"
              :aria-expanded="Boolean(expanded[item.key])"
              @click="toggleDetail(item.key)"
            >{{ expanded[item.key] ? '收起' : '详情' }}</button>
          </div>
          <div v-if="expanded[item.key]" class="p9-probe-detail">{{ item.detail }}</div>
        </div>
      </VCardText>
    </VCard>

    <!-- 4) 前向闸门：控件不变，说明压成一行小字 -->
    <VCard flat class="p9-card">
      <VCardItem>
        <VCardTitle class="p9-card-title">前向闸门</VCardTitle>
        <VCardSubtitle class="p9-card-sub">
          TG 推送前先看 PT 路是否在管：有活跃种记「PT 在途」，没取到则等过成熟期 T，记录已死立即放行。
        </VCardSubtitle>
      </VCardItem>
      <VCardText>
        <VSwitch
          v-model="config.form.p9_forward_gate_enabled"
          color="primary"
          inset
          :disabled="!config.form.enabled"
          hide-details
          label="启用前向闸门（默认关，开启后 TG 路让位给 PT 路）"
        />
        <div class="p9-gate-fields">
          <VTextField
            v-model.number="config.form.p9_maturity_hours"
            type="number"
            min="0"
            max="72"
            step="1"
            density="comfortable"
            label="成熟期 T（小时）"
            hint="PT 完全没有本集下载记录时等多久才让 TG 补，从该集第一次发现缺失起算（每集独立计时）。0 = 不等待；RSS 间隔 20 分钟左右时 2 小时通常足够。"
            persistent-hint
            :disabled="!config.form.p9_forward_gate_enabled"
          />
          <VSwitch
            v-model="config.form.p9_check_downloader"
            color="primary"
            inset
            hide-details
            label="下载器活跃性细化（用 hash 查活种，区分「在途」与「死种」）"
            :disabled="!config.form.p9_forward_gate_enabled"
          />
        </div>
      </VCardText>
    </VCard>
  </div>
</template>

<style scoped>
.p9-pane { display: flex; flex-direction: column; gap: 8px; }
/* 分区卡外观：有底色 + 1px 描边的 10px 圆角块，块与块之间 8px（对齐效果图的分区语言）。
   Vuetify 的 flat 卡片会把背景重置成与对话框同色的 surface，故用 !important 压过它；
   描边用 on-surface 的显式 alpha，避免主题变量缺失时整条 border 声明失效（计算值 0px） */
.p9-card {
  background: rgba(var(--v-theme-on-surface), 0.04) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10) !important;
  border-radius: 10px;
}
/* 卡片内外边距统一压到 10/12（压过 Vuetify 直系子元素的 16/24）；标题区与正文区相邻处只留一份，
   模板里不再用 pt-0 之类的工具类叠加 */
.p9-card > .v-card-item { padding: 10px 12px; }
.p9-card > .v-card-title { padding: 10px 12px; }
.p9-card > .v-card-text { padding: 10px 12px; }
.p9-card > .v-card-item + .v-card-text,
.p9-card > .v-card-title + .v-card-text { padding-top: 0; }
/* 卡头：12.5px 标题 + 10.5px 灰色副标题（压过 Vuetify 的 1.25rem 标题与 0.75rem 副标题） */
.p9-card-title { font-size: 12.5px; font-weight: 600; line-height: 1.4; }
.p9-card-sub {
  font-size: 10.5px; line-height: 1.5; opacity: 1;
  color: rgba(var(--v-theme-on-surface), 0.6);
  white-space: normal;
  word-break: break-word;
}
/* 运行链路：一行流程 chips，用箭头连接，窄屏自动换行 */
.p9-flow { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.p9-flow-chip {
  padding: 3px 8px;
  font-size: 11px; line-height: 1.5;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 6px;
  background: transparent;
  white-space: nowrap;
}
.p9-flow-arrow { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.45); }
.p9-flow-hint {
  margin-top: 6px;
  font-size: 10.5px; line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
/* 状态条：一行 4 个（与缓存/监控面板一致），窄屏回落 2×2 */
.p9-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
@media (max-width: 760px) {
  .p9-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.p9-stat {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  padding: 7px 9px;
  min-width: 0;
}
.p9-stat-label { font-size: 10.5px; line-height: 1.3; color: rgba(var(--v-theme-on-surface), 0.6); }
.p9-stat-value { font-size: 14px; font-weight: 700; line-height: 1.4; margin-top: 2px; }
/* 探针：顶部一行小字汇总 + 紧凑行；行与行之间一条极淡分隔线 */
.p9-probe-summary {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 6px;
  font-size: 10.5px; line-height: 1.4;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.p9-probe-row { padding: 3px 0; }
.p9-probe-row + .p9-probe-row {
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}
.p9-probe-line { display: flex; align-items: center; gap: 6px; min-width: 0; }
.p9-probe-icon { flex: 0 0 auto; }
.p9-probe-label {
  flex: 1 1 auto; min-width: 0;
  font-size: 12px; line-height: 1.4;
  overflow-wrap: anywhere;
}
/* 「详情」按钮：10.5px 灰色纯文字，点开才出现该行的导入路径/字段说明 */
.p9-probe-toggle {
  flex: 0 0 auto;
  padding: 2px 5px;
  background: transparent;
  border: 0;
  border-radius: 4px;
  font-size: 10.5px; line-height: 1.4;
  color: rgba(var(--v-theme-on-surface), 0.55);
  cursor: pointer;
}
.p9-probe-toggle:hover { color: rgba(var(--v-theme-on-surface), 0.85); background: rgba(var(--v-theme-on-surface), 0.06); }
.p9-probe-detail {
  padding: 2px 0 2px 20px;
  font-size: 10.5px; line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.55);
  word-break: break-all; white-space: normal;
}
.p9-gate-fields { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.p9-message { margin: 0; }
</style>
