<script setup>
import { computed, onMounted, ref } from 'vue'
import EmbyTasksPanel from './emby/EmbyTasksPanel.vue'
import { getPluginApi, unwrap } from './api'
import { FRONTEND_VERSION } from './version'

/**
 * 插件详情页 / 侧栏整页内容。
 *
 * 展示插件与媒体服务器状态，并提供连通性测试与设置入口。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  appPage: { type: Boolean, default: false },
})
const emit = defineEmits(['switch', 'close'])

const loading = ref(false)
const status = ref({})
const loadError = ref('')
const actionMessage = ref('')
const actionOk = ref(true)

const backendVersion = computed(() => String(status.value.plugin_version || ''))
const versionMismatched = computed(
  () => !!backendVersion.value && backendVersion.value !== FRONTEND_VERSION,
)
const servers = computed(() => (Array.isArray(status.value.servers) ? status.value.servers : []))

async function load() {
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status')) || {}
  } catch (error) {
    loadError.value = error?.message || '状态读取失败'
  } finally {
    loading.value = false
  }
}

async function ping() {
  actionMessage.value = ''
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'ping')) || {}
    actionOk.value = true
    actionMessage.value = `连通正常 · 后端 v${data.plugin_version || backendVersion.value || '?'}`
  } catch (error) {
    actionOk.value = false
    actionMessage.value = error?.message || '连通性测试失败'
  }
}

function onNotify(message, ok = true) {
  actionOk.value = ok !== false
  actionMessage.value = message || ''
}

onMounted(load)
</script>

<template>
  <VCard flat class="ec-page" :class="{ 'ec-page--app': props.appPage }">
    <VToolbar density="comfortable" class="ec-toolbar">
      <VAvatar color="primary" variant="tonal" rounded="lg" size="32" class="ms-3 me-2">
        <VIcon icon="mdi-image-multiple-outline" />
      </VAvatar>
      <div class="ec-heading">
        <div class="text-h6">胖虎封面中心</div>
        <div class="text-caption text-medium-emphasis">Emby 媒体库封面生成与任务中心</div>
      </div>
      <VSpacer />
      <VBtn size="small" variant="text" :loading="loading" @click="load">
        <VIcon icon="mdi-refresh" size="18" /><span class="ec-label">刷新</span>
      </VBtn>
      <VBtn size="small" variant="text" @click="ping">
        <VIcon icon="mdi-lan-connect" size="18" /><span class="ec-label">连通测试</span>
      </VBtn>
      <VBtn size="small" variant="text" @click="emit('switch')">
        <VIcon icon="mdi-cog-outline" size="18" /><span class="ec-label">设置</span>
      </VBtn>
      <VBtn v-if="!props.appPage" size="small" icon variant="text" @click="emit('close')">
        <VIcon icon="mdi-close" size="18" />
      </VBtn>
    </VToolbar>
    <VDivider />
    <VProgressLinear v-if="loading" indeterminate color="primary" height="2" />
    <VCardText class="ec-flow">
      <VAlert v-if="loadError" type="warning" variant="tonal" density="compact" class="ec-span">
        {{ loadError }}
        <VBtn size="x-small" variant="text" class="text-none" @click="load">重试</VBtn>
      </VAlert>
      <VAlert
        v-if="versionMismatched"
        type="info"
        variant="tonal"
        density="compact"
        class="ec-span"
      >
        前端组件 v{{ FRONTEND_VERSION }} ≠ 后端 v{{ backendVersion }}：浏览器仍在使用旧联邦组件，
        请按 Ctrl + Shift + R 硬刷新；若仍不一致，说明插件未真正更新。
      </VAlert>
      <div v-if="actionMessage" class="ec-span" :class="actionOk ? 'text-success' : 'text-error'">
        {{ actionMessage }}
      </div>

      <VCard variant="tonal" class="ec-card">
        <VCardItem>
          <VCardTitle class="text-subtitle-1">运行状态</VCardTitle>
        </VCardItem>
        <VCardText class="ec-kv">
          <div class="ec-row"><span>插件版本</span><b>v{{ backendVersion || '—' }}</b></div>
          <div class="ec-row"><span>启用状态</span><b>{{ status.enabled ? '已启用' : '已停用' }}</b></div>
          <div class="ec-row"><span>媒体服务器</span><b>{{ servers.length }}</b></div>
        </VCardText>
      </VCard>

      <VCard variant="tonal" class="ec-card">
        <VCardItem>
          <VCardTitle class="text-subtitle-1">媒体服务器</VCardTitle>
        </VCardItem>
        <VCardText>
          <div v-if="!servers.length" class="text-caption text-medium-emphasis">
            未发现已启用的媒体服务器，请在 MoviePilot「设置 · 媒体服务器」中配置 Emby / Jellyfin。
          </div>
          <div v-for="server in servers" :key="server.name" class="ec-row">
            <span>{{ server.name }}</span>
            <b :class="server.active ? 'text-success' : 'text-warning'">
              {{ server.type || '—' }} · {{ server.active ? '已连接' : '未连接' }}
            </b>
          </div>
        </VCardText>
      </VCard>

      <EmbyTasksPanel
        :api="props.api"
        :plugin-id="props.pluginId"
        :servers="servers"
        @notify="onNotify"
      />
    </VCardText>
  </VCard>
</template>

<style scoped>
.ec-page {
  width: 100%;
  border-radius: 16px;
  overflow: hidden;
}
.ec-page--app {
  min-height: calc(100dvh - 104px);
  border-radius: 14px;
}
.ec-toolbar {
  background: transparent;
  padding-right: 8px;
}
.ec-heading {
  min-width: 0;
}
.ec-label {
  white-space: nowrap;
}
.ec-flow {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.ec-span {
  grid-column: 1 / -1;
}
.ec-card {
  min-width: 0;
}
.ec-kv {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ec-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}
@media (max-width: 760px) {
  .ec-flow {
    grid-template-columns: 1fr;
  }
  .ec-label {
    display: none;
  }
}
</style>
