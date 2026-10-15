<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getPluginApi, unwrap } from './api'

/**
 * 插件配置面板。
 *
 * 纪律：字段与后端 model/config.py 的 default_config() 保持一致；配置由宿主
 * `plugin/<id>` 的 GET/PUT 承载，本组件只负责渲染与回填，不做本地持久化。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  initialConfig: { type: Object, default: () => ({}) },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['save', 'close'])

const form = reactive({
  enabled: props.initialConfig.enabled === true,
  discovery_page_enabled: props.initialConfig.discovery_page_enabled === true,
  selected_servers: Array.isArray(props.initialConfig.selected_servers)
    ? [...props.initialConfig.selected_servers]
    : [],
  auto_refresh_on_webhook: props.initialConfig.auto_refresh_on_webhook !== false,
  cover_cron: props.initialConfig.cover_cron || '0 4 * * *',
  notify_on_task_finish: props.initialConfig.notify_on_task_finish !== false,
})

const servers = ref([])
const loadingServers = ref(false)
const serverError = ref('')

const cronPresets = [
  { title: '每天 04:00', value: '0 4 * * *' },
  { title: '每 6 小时', value: '0 */6 * * *' },
  { title: '每周一 04:00', value: '0 4 * * 1' },
]

const serverItems = computed(() =>
  servers.value.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
)

async function loadServers() {
  if (loadingServers.value) return
  loadingServers.value = true
  serverError.value = ''
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'status')) || {}
    servers.value = Array.isArray(data.servers) ? data.servers : []
  } catch (error) {
    servers.value = []
    serverError.value = error?.message || '媒体服务器读取失败'
  } finally {
    loadingServers.value = false
  }
}

function submit() {
  if (props.busy) return
  emit('save', {
    enabled: form.enabled,
    discovery_page_enabled: form.discovery_page_enabled,
    selected_servers: [...form.selected_servers],
    auto_refresh_on_webhook: form.auto_refresh_on_webhook,
    cover_cron: form.cover_cron,
    notify_on_task_finish: form.notify_on_task_finish,
  })
}

onMounted(loadServers)
</script>

<template>
  <VCard flat class="ec-config">
    <VCardItem class="ec-header">
      <template #prepend>
        <VAvatar color="primary" variant="tonal" size="44" rounded="lg">
          <VIcon icon="mdi-image-multiple-outline" size="24" />
        </VAvatar>
      </template>
      <VCardTitle class="text-h6">胖虎封面中心</VCardTitle>
      <VCardSubtitle class="text-caption">Emby 媒体库封面生成与任务中心</VCardSubtitle>
      <template #append>
        <VSwitch
          v-model="form.enabled"
          color="success"
          hide-details
          inset
          :label="form.enabled ? '已启用' : '已停用'"
        />
      </template>
    </VCardItem>
    <VDivider />
    <VCardText class="ec-body">
      <VRow dense>
        <VCol cols="12" md="6">
          <VCard variant="tonal" class="ec-pane">
            <VCardItem>
              <VCardTitle class="text-subtitle-1">基础</VCardTitle>
            </VCardItem>
            <VCardText>
              <VSwitch
                v-model="form.discovery_page_enabled"
                color="primary"
                hide-details
                inset
                class="mb-3"
                label="在「发现」分区显示整页入口"
              />
              <VSwitch
                v-model="form.auto_refresh_on_webhook"
                color="primary"
                hide-details
                inset
                class="mb-3"
                label="Emby 入库后自动刷新对应媒体库封面"
              />
              <VSwitch
                v-model="form.notify_on_task_finish"
                color="primary"
                hide-details
                inset
                label="任务完成后发送通知（走 MP 通知渠道）"
              />
            </VCardText>
          </VCard>
        </VCol>
        <VCol cols="12" md="6">
          <VCard variant="tonal" class="ec-pane">
            <VCardItem>
              <VCardTitle class="text-subtitle-1">媒体服务器</VCardTitle>
              <template #append>
                <VBtn
                  size="small"
                  variant="text"
                  :loading="loadingServers"
                  @click="loadServers"
                >
                  刷新
                </VBtn>
              </template>
            </VCardItem>
            <VCardText>
              <VAlert
                v-if="serverError"
                type="warning"
                variant="tonal"
                density="compact"
                class="mb-2"
              >
                {{ serverError }}
              </VAlert>
              <VSelect
                v-model="form.selected_servers"
                :items="serverItems"
                label="参与封面的服务器"
                chips
                multiple
                clearable
                :disabled="!servers.length"
              />
              <div class="text-caption text-medium-emphasis">
                留空表示使用全部已启用的媒体服务器。
              </div>
            </VCardText>
          </VCard>
        </VCol>
        <VCol cols="12">
          <VCard variant="tonal" class="ec-pane">
            <VCardItem>
              <VCardTitle class="text-subtitle-1">定时封面任务</VCardTitle>
            </VCardItem>
            <VCardText>
              <VCombobox
                v-model="form.cover_cron"
                :items="cronPresets"
                label="Cron 表达式"
                hint="自动生成媒体库封面的执行时间"
                persistent-hint
              />
            </VCardText>
          </VCard>
        </VCol>
      </VRow>
    </VCardText>
    <VDivider />
    <VCardActions>
      <VSpacer />
      <VBtn variant="text" :disabled="props.busy" @click="emit('close')">取消</VBtn>
      <VBtn
        color="primary"
        variant="flat"
        prepend-icon="mdi-content-save-outline"
        :loading="props.busy"
        :disabled="props.busy"
        @click="submit"
      >
        保存配置
      </VBtn>
    </VCardActions>
  </VCard>
</template>

<style scoped>
.ec-config {
  width: min(1120px, calc(100vw - 48px));
  max-width: 100%;
  border-radius: 14px;
  overflow: hidden;
}
.ec-header {
  padding: 14px 18px;
}
.ec-body {
  max-height: min(70vh, 720px);
  overflow-y: auto;
}
.ec-pane {
  height: 100%;
}
@media (max-width: 760px) {
  .ec-config {
    width: min(100%, calc(100vw - 16px));
  }
}
</style>
