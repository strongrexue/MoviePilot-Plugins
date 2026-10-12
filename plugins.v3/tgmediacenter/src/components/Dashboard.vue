<script setup>
import { onMounted, ref } from 'vue'
import { getPluginApi, unwrap } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, default: () => ({}) },
})

const loading = ref(false)
const loadError = ref('')
const cache = ref([])

const dashboardPluginId = () => String(props.pluginId || '').trim() || 'TgMediaCenter'

async function loadData() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await getPluginApi(props.api, dashboardPluginId(), 'cache/status', { timeoutMs: 8000 })
    cache.value = unwrap(response) || []
  } catch (error) {
    loadError.value = error?.message || '缓存统计加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <VCard flat class="tg-dashboard">
    <VCardItem class="tg-dashboard-header">
      <template #prepend>
        <VAvatar color="primary" variant="tonal" rounded="lg" size="40">
          <VIcon icon="mdi-chart-box-outline" />
        </VAvatar>
      </template>
      <VCardTitle class="text-subtitle-1">TG媒体中心</VCardTitle>
      <VCardSubtitle class="text-caption">缓存统计与近期命中</VCardSubtitle>
      <template #append>
        <VBtn icon variant="text" size="small" :loading="loading" @click="loadData">
          <VIcon icon="mdi-refresh" />
        </VBtn>
      </template>
    </VCardItem>
    <VDivider />
    <VProgressLinear v-if="loading" indeterminate color="primary" height="2" />
    <VCardText class="pa-3">
      <VAlert v-if="loadError" type="warning" variant="tonal" density="compact">{{ loadError }}</VAlert>
      <VAlert v-else-if="!cache.length" type="info" variant="tonal" density="compact">
        暂无缓存数据（仪表盘待实现）。
      </VAlert>
      <VList v-else density="compact">
        <VListItem v-for="item in cache" :key="item.chat_id" :title="String(item.chat_id)">
          <template #append>
            <span class="text-caption">{{ item.message_count }} 条</span>
          </template>
        </VListItem>
      </VList>
    </VCardText>
  </VCard>
</template>

<style scoped>
.tg-dashboard {
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.tg-dashboard-header { padding: 12px 16px; }
</style>
