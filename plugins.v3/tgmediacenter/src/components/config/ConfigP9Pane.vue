<script setup>
import { computed, onMounted, ref } from 'vue'
import { getPluginApi, unwrap } from '../api'

/**
 * ⑩ P9 重复获取治理面板（1.9.0 引入 / 1.9.1 移除 R0）。
 *
 * 背景：PT 路（MP 订阅 → 下载 → 115）与 TG 路（本插件转存 → 115）写进同一个
 * 115 + STRM + Emby，会重复拿到同一部作品。治理分两向：
 *
 * - **前向闸门 A**：TG 推送前先看「PT 路是不是已经在管」→ **P9-2 才实现**，
 *   本版只在配置里占位，界面上不给控件，免得开关点了却没效果；
 * - **反向 R0 开关**（1.9.0 曾提供）：真机验证**否决**——暂停宿主内置的
 *   「新增订阅搜索」后，新增订阅照旧被搜索（首次搜索是 subscribe.added
 *   事件驱动，那个 5 分钟 job 只是兜底），开关无收益，1.9.1 已移除。
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

    <VProgressLinear v-if="loading" indeterminate color="primary" height="2" class="mb-3" />

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
