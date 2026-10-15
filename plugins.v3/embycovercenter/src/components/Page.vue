<script setup>
import { computed, onMounted, ref } from 'vue'
import CoverDesignPane from './cover/CoverDesignPane.vue'
import EmbyTasksPanel from './emby/EmbyTasksPanel.vue'
import { getPluginApi, getPluginConfig, unwrap } from './api'
import { FRONTEND_VERSION } from './version'

/**
 * 插件详情页 / 侧栏整页内容。
 *
 * 主区分成两个可切换的 Tab：「封面设计」与「Emby 任务中心」；顶部工具条保留
 * 刷新 / 连通测试 / 设置入口，配置弹窗仍复用 Config.vue。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  appPage: { type: Boolean, default: false },
})
const emit = defineEmits(['switch', 'close'])

const tab = ref('cover')
const loading = ref(false)
const status = ref({})
const config = ref(null)
const loadError = ref('')
const actionMessage = ref('')
const actionOk = ref(true)

const backendVersion = computed(() => String(status.value.plugin_version || ''))
const versionMismatched = computed(
  () => !!backendVersion.value && backendVersion.value !== FRONTEND_VERSION,
)
const servers = computed(() => (Array.isArray(status.value.servers) ? status.value.servers : []))
const activeCount = computed(() => servers.value.filter(server => server.active).length)

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
  // 封面设计从已保存配置起步（取不到就用内置默认，不影响使用）。
  try {
    config.value = (await getPluginConfig(props.api, props.pluginId)) || {}
  } catch (error) {
    config.value = {}
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

    <div class="ec-status">
      <div class="ec-chips">
        <VChip :color="status.enabled ? 'success' : 'grey'" variant="tonal" size="small" label>
          {{ status.enabled ? '已启用' : '已停用' }}
        </VChip>
        <VChip color="primary" variant="tonal" size="small" label>v{{ backendVersion || '—' }}</VChip>
        <VChip color="info" variant="tonal" size="small" label>
          服务器 {{ activeCount }}/{{ servers.length }}
        </VChip>
      </div>
      <VAlert v-if="loadError" type="warning" variant="tonal" density="compact" class="ec-full">
        {{ loadError }}
        <VBtn size="x-small" variant="text" class="text-none" @click="load">重试</VBtn>
      </VAlert>
      <VAlert v-if="versionMismatched" type="info" variant="tonal" density="compact" class="ec-full">
        前端组件 v{{ FRONTEND_VERSION }} ≠ 后端 v{{ backendVersion }}：浏览器仍在使用旧联邦组件，
        请按 Ctrl + Shift + R 硬刷新；若仍不一致，说明插件未真正更新。
      </VAlert>
      <div v-if="actionMessage" class="ec-full" :class="actionOk ? 'text-success' : 'text-error'">
        {{ actionMessage }}
      </div>
    </div>

    <VTabs v-model="tab" density="comfortable" color="primary" class="ec-tabs">
      <VTab value="cover" prepend-icon="mdi-image-edit-outline">封面设计</VTab>
      <VTab value="tasks" prepend-icon="mdi-calendar-clock-outline">Emby 任务中心</VTab>
    </VTabs>
    <VDivider />

    <VCardText class="ec-body">
      <VWindow v-model="tab" :touch="false">
        <VWindowItem value="cover" class="ec-pane">
          <!-- 等配置取回后再挂载：封面设计会用已保存配置初始化表单 -->
          <CoverDesignPane
            v-if="config"
            :api="props.api"
            :plugin-id="props.pluginId"
            :initial-config="config"
            :servers="servers"
          />
        </VWindowItem>
        <VWindowItem value="tasks" class="ec-pane">
          <EmbyTasksPanel
            :api="props.api"
            :plugin-id="props.pluginId"
            :servers="servers"
            @notify="onNotify"
          />
        </VWindowItem>
      </VWindow>
    </VCardText>
  </VCard>
</template>

<style scoped>
.ec-page {
  width: 100%;
  border-radius: 16px;
  overflow: hidden;
  /* 两种宿主形态都用「头固定 + 正文内滚」结构：工具条/状态/Tab 不随内容滚走 */
  display: flex;
  flex-direction: column;
}
/* 插件详情弹窗模式：限高视口（上下各留宿主弹窗边距），内容紧凑时自适应、
   超长时正文内部滚动——对齐媒体中心 / 豆瓣中心详情弹窗的高度观感 */
.ec-page:not(.ec-page--app) {
  max-height: calc(100dvh - 160px);
}
.ec-page--app {
  /* 整页锁定视口高度：正文区内部滚动（窄屏同理） */
  height: calc(100dvh - 104px);
  border-radius: 14px;
}
/* flex 子项默认可收缩，正文以外的行都要保持自身高度 */
.ec-page > :not(.ec-body) {
  flex-shrink: 0;
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
.ec-status {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 16px 4px;
}
.ec-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ec-full {
  grid-column: 1 / -1;
}
.ec-tabs {
  padding: 0 8px;
}
.ec-body {
  padding: 10px 14px 16px;
}
/* 正文区占满剩余高度、内部滚动（弹窗与整页两种模式通用） */
.ec-page .ec-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}
.ec-pane {
  padding: 0;
  /* 内容限宽居中（与媒体中心 / 豆瓣中心 AppPage 同为 1800px 上限），
     常规屏幕基本贴边，超宽屏才居中收窄 */
  width: 100%;
  max-width: 1800px;
  margin: 0 auto;
}
@media (max-width: 760px) {
  .ec-label {
    display: none;
  }
  .ec-body {
    padding: 8px 8px 14px;
  }
}
</style>
