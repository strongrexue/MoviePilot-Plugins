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
 * 探针保留：闸门依赖的宿主能力随版本可能漂移，这里随时能看到真实可用性。
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

const probeSummary = computed(() => {
  const data = probe.value
  if (!data) return ''
  const bad = items.value.filter(item => !item.ok).length
  const text = data.ok ? '全部通过' : `${bad} / ${items.value.length} 项未通过`
  return data.checked_at ? `${text}（探测于 ${data.checked_at}）` : text
})

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
    <VCard flat class="p9-card">
      <VCardItem>
        <template #prepend>
          <VAvatar color="primary" variant="tonal" size="40" rounded="lg">
            <VIcon icon="mdi-shield-sync-outline" size="22" />
          </VAvatar>
        </template>
        <VCardTitle class="text-subtitle-2">重复获取治理</VCardTitle>
        <VCardSubtitle class="text-caption">
          PT 路（MP 订阅 → 下载 → 115）与 TG 路（本插件转存 → 115）写进同一个
          115 + STRM + Emby，会重复拿到同一部作品。这里只按「媒体身份」判断谁在管，
          不在目录或命名上做任何约定。
        </VCardSubtitle>
      </VCardItem>
    </VCard>

    <VAlert
      v-if="message"
      :type="messageOk ? 'info' : 'warning'"
      variant="tonal"
      density="comfortable"
      class="p9-message"
    >{{ message }}</VAlert>

    <VProgressLinear v-if="loading" indeterminate color="primary" height="2" />

    <!-- 宿主能力探针 -->
    <VCard flat class="p9-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">宿主能力探针</VCardTitle>
        <VCardSubtitle class="text-caption">
          前向闸门要用宿主的两组能力（下载历史查询、下载器种子列表），而它们本插件此前从未调用过。
          先探测清楚真实导入路径与字段，再动手写判定链——探针只读，不改任何状态。
        </VCardSubtitle>
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
      <VCardText v-if="probe" class="pt-0">
        <div class="p9-probe-summary">
          <VIcon
            :icon="probe.ok ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline'"
            :color="probe.ok ? 'success' : 'warning'"
            size="18"
          />
          <span>{{ probeSummary }}</span>
        </div>
        <div v-for="item in items" :key="item.key" class="p9-probe-row">
          <VIcon
            :icon="item.ok ? 'mdi-check' : 'mdi-close'"
            :color="item.ok ? 'success' : 'error'"
            size="16"
            class="p9-probe-icon"
          />
          <div class="p9-probe-body">
            <div class="p9-probe-label">{{ item.label }}</div>
            <div class="p9-probe-detail">{{ item.detail }}</div>
          </div>
        </div>
      </VCardText>
    </VCard>

    <!-- 前向闸门 A（P9-2 起提供控件） -->
    <VCard flat class="p9-card">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">前向闸门</VCardTitle>
        <VCardSubtitle class="text-caption">
          TG 推送前依次判断「媒体库已有（仅缺失）→ 下载历史近 T 有本集记录 → 下载器有本集活跃种」，
          PT 路在管就拦下：有活跃种记「PT 在途」，PT 还没取到资源则等过成熟期 T 再补；
          有记录但种子已死/被清则立即放行。判定与计时均按「集」粒度（片名+年份+季+集）——
          PT 追更是单集发布、单集抓取，一季可持续数月，按季计时会让季末单集的成熟期早已失效。
          宿主查询失败时一律放行并写 WARNING（闸门绝不静默拦截推送）。
          改动随底部「保存配置」生效。
        </VCardSubtitle>
      </VCardItem>
      <VCardText class="pt-0">
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
.p9-card {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.p9-gate-fields { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.p9-message { margin: 0; }
.p9-probe-summary {
  display: flex; align-items: center; gap: 6px;
  font-size: 0.8125rem; font-weight: 500; margin-bottom: 8px;
}
.p9-probe-row { display: flex; gap: 8px; padding: 4px 0; align-items: flex-start; }
.p9-probe-icon { flex: 0 0 auto; margin-top: 2px; }
.p9-probe-body { min-width: 0; }
.p9-probe-label { font-size: 0.8125rem; }
.p9-probe-detail {
  font-size: 0.75rem; opacity: 0.7; line-height: 1.5;
  word-break: break-all; white-space: normal;
}
</style>
