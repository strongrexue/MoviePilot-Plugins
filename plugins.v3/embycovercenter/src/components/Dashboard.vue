<script setup>
import { computed, onMounted, ref } from 'vue'
import { getPluginApi, unwrap } from './api'
import { FRONTEND_VERSION } from './version'

/**
 * 仪表盘卡片：一眼概览插件与媒体服务器状态。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
})

const status = ref({})
const loadError = ref('')

const backendVersion = computed(() => String(status.value.plugin_version || ''))
const versionMismatched = computed(
  () => !!backendVersion.value && backendVersion.value !== FRONTEND_VERSION,
)
const servers = computed(() => (Array.isArray(status.value.servers) ? status.value.servers : []))
const activeCount = computed(() => servers.value.filter(server => server.active).length)

async function load() {
  loadError.value = ''
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status')) || {}
  } catch (error) {
    loadError.value = error?.message || '状态读取失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="ec-dash">
    <div class="ec-chips">
      <VChip
        :color="status.enabled ? 'success' : 'grey'"
        variant="tonal"
        size="small"
        label
      >
        {{ status.enabled ? '已启用' : '已停用' }}
      </VChip>
      <VChip color="primary" variant="tonal" size="small" label>v{{ backendVersion || '—' }}</VChip>
      <VChip color="info" variant="tonal" size="small" label>
        服务器 {{ activeCount }}/{{ servers.length }}
      </VChip>
    </div>

    <VAlert v-if="loadError" type="warning" variant="tonal" density="compact" class="mt-2">
      {{ loadError }}
    </VAlert>
    <VAlert v-if="versionMismatched" type="info" variant="tonal" density="compact" class="mt-2">
      前端组件 v{{ FRONTEND_VERSION }} ≠ 后端 v{{ backendVersion }}，请 Ctrl + Shift + R 硬刷新。
    </VAlert>

    <div class="ec-list">
      <div v-for="server in servers" :key="server.name" class="ec-row">
        <span>{{ server.name }}</span>
        <b :class="server.active ? 'text-success' : 'text-warning'">
          {{ server.active ? '已连接' : '未连接' }}
        </b>
      </div>
      <div v-if="!servers.length" class="text-caption text-medium-emphasis">
        未发现已启用的媒体服务器。
      </div>
    </div>
  </div>
</template>

<style scoped>
.ec-dash {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.ec-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ec-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 180px;
  overflow-y: auto;
}
.ec-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}
</style>
