<script setup>
import { computed, onMounted, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from '../api'

/**
 * ⑩ P9 重复获取治理面板（1.9.0 / 阶段 P9-1）。
 *
 * 背景：PT 路（MP 订阅 → 下载 → 115）与 TG 路（本插件转存 → 115）写进同一个
 * 115 + STRM + Emby，会重复获取同一部作品。治理分两向：
 *
 * - **前向闸门 A**：TG 推送前先看「PT 路是不是已经在管」→ **P9-2 才实现**，
 *   本版只在配置里占位，界面上不给控件，免得开关点了却没效果；
 * - **反向 R0 开关**：暂停宿主内置的「新增订阅搜索」→ **本版可用**。
 *
 * 探针的意义：闸门 A 要用 `list_download_history` 与 `DownloaderHelper`，而这两组
 * 宿主能力本插件此前一处都没用过。先探清"到底能不能导入、真实落在哪个模块、
 * 有哪些字段"，再动手写判定链，避免靠猜。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
})

const guard = ref(null)
const loading = ref(false)
const busy = ref('')
const message = ref('')
const messageOk = ref(true)

const form = computed(() => props.config.form)
const r0 = computed(() => guard.value?.r0 || null)
const probe = computed(() => guard.value?.probe || null)
const items = computed(() => probe.value?.items || [])

/** 开关的期望值（表单里刚改、还没保存的值）。 */
const wantPause = computed(() => Boolean(form.value.p9_pause_new_subscribe_search))

const r0Line = computed(() => {
  const info = r0.value
  if (!info) return '未知（尚未探测）'
  if (!info.available) return '旧调度接口不可用，开关不生效'
  if (!info.exists) return '宿主未注册「新增订阅搜索」任务'
  return info.paused
    ? '已暂停：内置的 5 分钟兜底搜索不会跑'
    : `运行中${info.next_run ? `，下次 ${info.next_run}` : ''}`
})

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

/** 按当前**已保存**的配置重贴开关（宿主热重载会重建任务，pause 会被冲掉）。 */
async function reapply() {
  if (busy.value) return
  busy.value = 'apply'
  setMessage('正在按当前配置重贴开关…')
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'p9/r0/apply', {}, { timeoutMs: 30000 }))
    if (guard.value) guard.value.r0 = data
    setMessage(data?.message || '已重贴')
  } catch (err) {
    setMessage(err?.message || '重贴失败', false)
    await load()
  } finally {
    busy.value = ''
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

    <VProgressLinear v-if="loading" indeterminate color="primary" height="2" class="mb-3" />

    <!-- 反向 R0：暂停宿主内置的「新增订阅搜索」 -->
    <VCard flat class="p9-card">
      <VCardItem>
        <template #prepend>
          <VSwitch
            v-model="form.p9_pause_new_subscribe_search"
            color="primary"
            hide-details
            inset
            :disabled="!form.enabled"
          />
        </template>
        <VCardTitle class="text-subtitle-2">暂停宿主的「新增订阅搜索」</VCardTitle>
        <VCardSubtitle class="text-caption">
          开启后，宿主那个每 5 分钟跑一次的「新增订阅搜索」会被暂停。
          它的作用是：TG 已经先把内容送进媒体库时，别让 MP 再用 PT 下一次。
          改动随底部「保存配置」生效；插件停用或本开关关闭时一律放行。
        </VCardSubtitle>
      </VCardItem>
      <VCardText class="pt-0">
        <div class="p9-state">
          <span>当前状态：{{ r0Line }}</span>
          <VChip
            v-if="r0"
            size="x-small"
            :color="r0.available && r0.exists ? (r0.paused ? 'warning' : 'success') : 'default'"
            variant="tonal"
            class="ms-2"
          >{{ r0.available ? (r0.exists ? (r0.paused ? '已暂停' : '运行中') : '任务不存在') : '接口不可用' }}</VChip>
        </div>
        <div class="p9-hint">
          表单里显示的是<b>期望值</b>，上面是宿主侧的<b>真实状态</b>——两者不一致时先保存配置。
          宿主配置热重载会重建这个任务、把暂停状态冲掉，此时点右侧按钮重贴一次即可。
        </div>
        <VBtn
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-refresh"
          class="mt-2"
          :loading="busy === 'apply'"
          :disabled="!r0?.available"
          @click="reapply"
        >按当前配置重贴</VBtn>
        <VAlert
          v-if="r0 && !r0.available"
          type="warning"
          variant="tonal"
          density="compact"
          class="mt-3"
        >
          宿主没有保留旧调度接口（或已移除内置任务），本开关不生效；不影响插件的其余能力。
          <span v-if="r0.message" class="p9-detail">{{ r0.message }}</span>
        </VAlert>
      </VCardText>
    </VCard>

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

    <!-- 前向闸门 A（P9-2） -->
    <VCard flat class="p9-card p9-card-muted">
      <VCardItem>
        <VCardTitle class="text-subtitle-2">前向闸门（未启用）</VCardTitle>
        <VCardSubtitle class="text-caption">
          计划：TG 推送前依次判断「媒体库已有 → 下载历史有记录且在途 → 等过成熟期（默认 2 小时）」，
          全都没拦住才补。这一步需要先由上面的探针确认宿主能力可用，因此放在下一阶段落地，
          本版界面不提供开关（配置里的三个字段已占位，默认关闭）。
        </VCardSubtitle>
      </VCardItem>
    </VCard>
  </div>
</template>

<style scoped>
.p9-pane { display: flex; flex-direction: column; gap: 12px; }
.p9-card {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.p9-card-muted { opacity: 0.75; }
.p9-message { margin: 0; }
.p9-state { display: flex; align-items: center; flex-wrap: wrap; font-size: 0.875rem; }
.p9-hint { margin-top: 6px; font-size: 0.75rem; opacity: 0.7; line-height: 1.5; }
.p9-detail { display: block; margin-top: 4px; font-size: 0.75rem; opacity: 0.85; word-break: break-all; }
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
