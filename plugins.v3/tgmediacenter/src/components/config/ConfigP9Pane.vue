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
 * 版面（对齐豆瓣中心「运行总览」）：运行链路 / 状态 / 宿主能力探针 / 前向闸门。
 * 探针结果按效果图只展示 chips（详情走 hover title），不再逐行展开占屏。
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
const probeBadCount = computed(() => items.value.filter(item => !item.ok).length)
const probeTotal = computed(() => items.value.length)
const probeCountText = computed(() => (probe.value ? `${probeOkCount.value}/${probeTotal.value}` : '—'))

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

    <!-- 3) 宿主能力探针：结果只占一行 chips（详情看 hover），与效果图一致 -->
    <VCard flat class="p9-card">
      <VCardItem>
        <VCardTitle class="p9-card-title">宿主能力探针</VCardTitle>
        <VCardSubtitle class="p9-card-sub">只读：确认闸门依赖的宿主接口是否还在</VCardSubtitle>
        <template #append>
          <span v-if="probe" class="p9-badge" :class="probe.ok ? 'p9-badge-ok' : 'p9-badge-warn'">
            {{ probe.ok ? '全部通过' : `${probeBadCount} 项未通过` }}
          </span>
          <VBtn size="small" variant="tonal" prepend-icon="mdi-radar" :loading="loading" @click="load">
            重新探测
          </VBtn>
        </template>
      </VCardItem>
      <VCardText v-if="probe">
        <div class="p9-probe-chips">
          <span
            v-for="item in items"
            :key="item.key"
            class="p9-probe-chip"
            :class="item.ok ? 'p9-probe-chip-ok' : 'p9-probe-chip-bad'"
            :title="item.detail"
          >{{ item.ok ? '✓' : '✗' }} {{ item.label }}</span>
        </div>
        <div class="p9-flow-hint">
          探测于 {{ probe.checked_at || '—' }} · 任一红项会让闸门按 fail-open 放行，不会拦截推送。
        </div>
      </VCardText>
    </VCard>

    <!-- 4) 前向闸门：开关放卡头右侧，正文两列（成熟期 T ｜ 活跃性细化） -->
    <VCard flat class="p9-card">
      <VCardItem>
        <VCardTitle class="p9-card-title">前向闸门</VCardTitle>
        <VCardSubtitle class="p9-card-sub">
          PT 在管就让位：有活跃种记「PT 在途」，没取到则等过成熟期
        </VCardSubtitle>
        <template #append>
          <VSwitch
            v-model="config.form.p9_forward_gate_enabled"
            color="primary"
            inset
            hide-details
            :disabled="!config.form.enabled"
            :label="config.form.p9_forward_gate_enabled ? '启用' : '停用'"
          />
        </template>
      </VCardItem>
      <VCardText>
        <div class="p9-gate-grid">
          <VTextField
            v-model.number="config.form.p9_maturity_hours"
            type="number"
            min="0"
            max="72"
            step="1"
            density="compact"
            variant="outlined"
            hide-details
            label="成熟期 T（小时）"
            :disabled="!config.form.p9_forward_gate_enabled"
          />
          <div class="p9-gate-switch">
            <VSwitch
              v-model="config.form.p9_check_downloader"
              color="primary"
              inset
              hide-details
              label="下载器活跃性细化（用 hash 查活种）"
              :disabled="!config.form.p9_forward_gate_enabled"
            />
          </div>
        </div>
        <div class="p9-flow-hint">
          成熟期 = PT 完全没有本集下载记录时等多久才让 TG 补，从该集第一次发现缺失起算（每集独立计时）；
          0 = 不等待，RSS 间隔 20 分钟左右时 2 小时通常足够。
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
/* 卡片内外边距统一压到 10/12（压过 Vuetify 直系子元素的 16/24）；标题区与正文区相邻处只留一份 */
.p9-card > .v-card-item { padding: 10px 12px; }
.p9-card > .v-card-title { padding: 10px 12px; }
.p9-card > .v-card-text { padding: 10px 12px; }
.p9-card > .v-card-item + .v-card-text,
.p9-card > .v-card-title + .v-card-text { padding-top: 0; }
/* 卡头：12.5px 标题 + 10.5px 灰色副标题 */
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
/* 探针结论徽章（卡头右侧） */
.p9-badge {
  padding: 2px 8px;
  font-size: 10.5px; line-height: 1.6;
  border-radius: 6px;
  white-space: nowrap;
}
.p9-badge-ok { background: rgba(49, 196, 141, 0.15); color: #6ee7b7; }
.p9-badge-warn { background: rgba(240, 164, 74, 0.15); color: #f6c78a; }
/* 探针结果：一行 chips（详情走 hover title），不再逐行展开 */
.p9-probe-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.p9-probe-chip {
  padding: 3px 8px;
  font-size: 11px; line-height: 1.5;
  border-radius: 6px;
  white-space: nowrap;
}
.p9-probe-chip-ok { background: rgba(49, 196, 141, 0.15); color: #6ee7b7; }
.p9-probe-chip-bad { background: rgba(244, 67, 54, 0.15); color: #f19a93; }
/* 前向闸门：两列（成熟期 T ｜ 活跃性细化），窄屏单列 */
.p9-gate-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}
@media (max-width: 700px) {
  .p9-gate-grid { grid-template-columns: 1fr; }
}
.p9-gate-switch { display: flex; align-items: center; }
.p9-message { margin: 0; }
</style>
