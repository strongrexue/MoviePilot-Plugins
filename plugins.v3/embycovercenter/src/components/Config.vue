<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import AutoCoverLibraries from './AutoCoverLibraries.vue'
import CoverBackups from './CoverBackups.vue'
import CoverDesignPane from './cover/CoverDesignPane.vue'
import { getPluginApi, postPluginApi, unwrap } from './api'

/**
 * 插件配置面板：顶部总开关 + 两个分区（基础设置 / 封面设计）。
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

const tab = ref('base')

const form = reactive({
  enabled: props.initialConfig.enabled === true,
  discovery_page_enabled: props.initialConfig.discovery_page_enabled === true,
  selected_servers: Array.isArray(props.initialConfig.selected_servers)
    ? [...props.initialConfig.selected_servers]
    : [],
  auto_cover_enabled: props.initialConfig.auto_cover_enabled === true,
  auto_cover_template: props.initialConfig.auto_cover_template || '',
  auto_cover_libraries:
    props.initialConfig.auto_cover_libraries && typeof props.initialConfig.auto_cover_libraries === 'object'
      ? { ...props.initialConfig.auto_cover_libraries }
      : {},
  auto_refresh_on_webhook: props.initialConfig.auto_refresh_on_webhook !== false,
  auto_backup_enabled: props.initialConfig.auto_backup_enabled !== false,
  cover_cron: props.initialConfig.cover_cron || '0 4 * * *',
  notify_on_task_finish: props.initialConfig.notify_on_task_finish !== false,
})

const servers = ref([])
const loadingServers = ref(false)
const serverError = ref('')
const templates = ref([])
const coverRef = ref(null)
const runningCover = ref(false)
const runMessage = ref('')
const runOk = ref(true)
const showBackups = ref(false)

/** 执行频率：预设 + 自定义。单独维护下拉选择值——选中「自定义」时若直接绑
 * form.cover_cron，computed getter 会立刻弹回旧预设（表现为点了没反应）。 */
const scheduleOptions = [
  { title: '每天 04:00', value: '0 4 * * *' },
  { title: '每 6 小时', value: '0 */6 * * *' },
  { title: '每周一 04:00', value: '0 4 * * 1' },
  { title: '每小时', value: '0 * * * *' },
  { title: '每 30 分钟', value: '*/30 * * * *' },
  { title: '自定义 Cron', value: '__custom__' },
]
const scheduleChoice = ref(
  scheduleOptions.some(item => item.value === form.cover_cron) ? form.cover_cron : '__custom__',
)
function onScheduleChange(value) {
  scheduleChoice.value = value
  if (value && value !== '__custom__') form.cover_cron = value
}

const serverItems = computed(() =>
  servers.value.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
)

const templateItems = computed(() => [
  { title: '跟随封面设计', value: '' },
  ...templates.value.map(template => ({
    title: template.name || template.filename,
    value: template.filename,
  })),
])

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

async function loadTemplates() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'templates')) || {}
    templates.value = Array.isArray(data.templates) ? data.templates : []
  } catch (error) {
    templates.value = []
  }
}

async function runAutoCover() {
  if (runningCover.value) return
  runningCover.value = true
  runMessage.value = ''
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'auto_cover/run', {})) || {}
    runMessage.value = data.message || '自动封面任务已在后台启动'
    runOk.value = true
  } catch (error) {
    runMessage.value = error?.message || '启动失败'
    runOk.value = false
  } finally {
    runningCover.value = false
  }
}

function submit() {
  if (props.busy) return
  const cover = coverRef.value?.snapshot ? coverRef.value.snapshot() : {}
  emit('save', {
    enabled: form.enabled,
    discovery_page_enabled: form.discovery_page_enabled,
    selected_servers: [...form.selected_servers],
    auto_cover_enabled: form.auto_cover_enabled,
    auto_cover_template: form.auto_cover_template,
    auto_cover_libraries: { ...form.auto_cover_libraries },
    auto_backup_enabled: form.auto_backup_enabled,
    auto_refresh_on_webhook: form.auto_refresh_on_webhook,
    cover_cron: form.cover_cron,
    notify_on_task_finish: form.notify_on_task_finish,
    ...cover,
  })
}

onMounted(() => {
  loadServers()
  loadTemplates()
})
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

    <VTabs v-model="tab" density="comfortable" color="primary" class="ec-tabs">
      <VTab value="base" prepend-icon="mdi-cog-outline">基础设置</VTab>
      <VTab value="cover" prepend-icon="mdi-image-edit-outline">封面设计</VTab>
    </VTabs>
    <VDivider />

    <div class="ec-body">
      <VWindow v-model="tab" :touch="false">
        <VWindowItem value="base" class="ec-pane">
          <VRow dense>
            <VCol cols="12" md="6">
              <VCard variant="tonal" class="ec-block">
                <VCardItem class="py-2">
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
              <VCard variant="tonal" class="ec-block">
                <VCardItem class="py-2">
                  <VCardTitle class="text-subtitle-1">媒体服务器</VCardTitle>
                  <template #append>
                    <VBtn size="small" variant="text" :loading="loadingServers" @click="loadServers">刷新</VBtn>
                  </template>
                </VCardItem>
                <VCardText>
                  <VAlert v-if="serverError" type="warning" variant="tonal" density="compact" class="mb-2">
                    {{ serverError }}
                  </VAlert>
                  <VSelect
                    v-model="form.selected_servers"
                    :items="serverItems"
                    label="参与封面的服务器"
                    chips
                    multiple
                    clearable
                    density="compact"
                    variant="outlined"
                    :disabled="!servers.length"
                  />
                  <div class="text-caption text-medium-emphasis mt-1">
                    留空表示使用全部已启用的媒体服务器。
                  </div>
                </VCardText>
              </VCard>
            </VCol>
            <VCol cols="12">
              <VCard variant="tonal" class="ec-block">
                <VCardItem class="py-2">
                  <VCardTitle class="text-subtitle-1">自动封面任务</VCardTitle>
                  <VCardSubtitle class="text-caption">
                    定时 / Emby 入库时，为选中媒体库自动生成并应用封面
                  </VCardSubtitle>
                  <template #append>
                    <VBtn size="small" variant="text" prepend-icon="mdi-backup-restore" @click="showBackups = true">
                      备份管理
                    </VBtn>
                    <VBtn
                      size="small"
                      variant="tonal"
                      prepend-icon="mdi-play"
                      :loading="runningCover"
                      :disabled="!form.enabled"
                      @click="runAutoCover"
                    >
                      立即运行
                    </VBtn>
                  </template>
                </VCardItem>
                <VCardText>
                  <VAlert v-if="runMessage" :type="runOk ? 'success' : 'error'" variant="tonal" density="compact" class="mb-2">
                    {{ runMessage }}
                  </VAlert>
                  <VRow dense>
                    <VCol cols="12" md="4">
                      <VSwitch
                        v-model="form.auto_cover_enabled"
                        color="primary"
                        hide-details
                        inset
                        class="mt-2"
                        label="启用定时自动封面"
                      />
                    </VCol>
                    <VCol cols="12" md="4">
                      <VSelect
                        v-model="form.auto_cover_template"
                        :items="templateItems"
                        label="封面方案"
                        density="compact"
                        variant="outlined"
                        hide-details
                      />
                    </VCol>
                    <VCol cols="12" md="4">
                      <VSelect
                        :model-value="scheduleChoice"
                        :items="scheduleOptions"
                        label="执行频率"
                        density="compact"
                        variant="outlined"
                        hide-details
                        @update:model-value="onScheduleChange"
                      />
                    </VCol>
                    <VCol cols="12">
                      <VSwitch
                        v-model="form.auto_backup_enabled"
                        color="primary"
                        hide-details
                        inset
                        label="覆盖前自动备份原版封面（每库保留最近 3 版，可在「备份管理」恢复）"
                      />
                    </VCol>
                    <VCol v-if="scheduleChoice === '__custom__'" cols="12" md="6">
                      <VTextField
                        v-model="form.cover_cron"
                        label="Cron 表达式"
                        placeholder="分 时 日 月 周，如 30 5 * * *"
                        density="compact"
                        variant="outlined"
                        hide-details
                      />
                    </VCol>
                    <VCol cols="12">
                      <AutoCoverLibraries
                        v-model="form.auto_cover_libraries"
                        :api="props.api"
                        :plugin-id="props.pluginId"
                        :servers="servers"
                        :disabled="!servers.length"
                      />
                    </VCol>
                    <VCol cols="12">
                      <div class="text-caption text-medium-emphasis">
                        「跟随封面设计」使用封面设计 Tab 当前保存的布局与参数；执行时只处理所选媒体库与
                        「参与封面的服务器」的交集。Emby 入库自动刷新由上方开关控制，同样只刷新这里勾选的媒体库。
                      </div>
                    </VCol>
                  </VRow>
                </VCardText>
              </VCard>
            </VCol>
          </VRow>
        </VWindowItem>

        <VWindowItem value="cover" class="ec-pane">
          <CoverDesignPane
            ref="coverRef"
            :api="props.api"
            :plugin-id="props.pluginId"
            :initial-config="props.initialConfig"
            :servers="servers"
          />
        </VWindowItem>
      </VWindow>
    </div>

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

    <CoverBackups v-model="showBackups" :api="props.api" :plugin-id="props.pluginId" />
  </VCard>
</template>

<style scoped>
.ec-config {
  width: min(1360px, calc(100vw - 48px));
  max-width: 100%;
  border-radius: 14px;
  overflow: hidden;
}
.ec-header {
  padding: 14px 18px;
}
.ec-tabs {
  padding: 0 8px;
}
.ec-body {
  max-height: min(74vh, 820px);
  overflow-y: auto;
  padding: 14px 16px 4px;
}
.ec-pane {
  padding: 0;
}
.ec-block {
  border-radius: 10px;
}
@media (max-width: 760px) {
  .ec-config {
    width: min(100%, calc(100vw - 16px));
  }
  .ec-body {
    padding: 10px 10px 4px;
  }
}
</style>
