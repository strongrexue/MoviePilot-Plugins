<script setup>
import { onMounted, ref } from 'vue'
import { getPluginApi, unwrap } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
})
const emit = defineEmits(['close', 'switch'])

const loading = ref(false)
const loadError = ref('')
const status = ref(null)

async function loadStatus() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await getPluginApi(props.api, props.pluginId, 'status', { timeoutMs: 8000 })
    status.value = unwrap(response)
  } catch (error) {
    loadError.value = error?.message || '状态加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <VCard flat class="tg-page">
    <VToolbar density="comfortable" class="tg-toolbar">
      <VAvatar color="primary" variant="tonal" rounded="lg" class="ms-3 me-2">
        <VIcon icon="mdi-send-circle-outline" />
      </VAvatar>
      <div class="tg-heading">
        <div class="text-h6">TG媒体中心 · 运行详情</div>
        <div class="text-caption text-medium-emphasis">TG 客户端 → 消息流水线 → 缓存 / 监控 / 转发</div>
      </div>
      <VSpacer />
      <VBtn variant="text" size="small" :loading="loading" prepend-icon="mdi-refresh" @click="loadStatus">
        刷新
      </VBtn>
      <VBtn variant="text" size="small" prepend-icon="mdi-cog-outline" @click="emit('switch')">设置</VBtn>
      <VBtn icon variant="text" size="small" @click="emit('close')">
        <VIcon icon="mdi-close" />
      </VBtn>
    </VToolbar>
    <VDivider />
    <VProgressLinear v-if="loading" indeterminate color="primary" height="2" />
    <VCardText class="pa-3">
      <VAlert v-if="loadError" type="warning" variant="tonal" density="compact">{{ loadError }}</VAlert>
      <VAlert v-else type="info" variant="tonal" density="compact">
        运行状态面板待实现（TG 客户端 / 115 / 缓存统计 / 命中流水）。
      </VAlert>
      <pre v-if="status" class="tg-status-raw">{{ JSON.stringify(status, null, 2) }}</pre>
    </VCardText>
  </VCard>
</template>

<style scoped>
.tg-page {
  background: transparent;
  width: 100%;
  border-radius: 16px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  overflow: hidden;
}
.tg-toolbar { background: transparent; padding-right: 8px; }
.tg-heading { min-width: 0; }
.tg-heading .text-h6,
.tg-heading .text-caption { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tg-status-raw {
  margin-top: 12px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
