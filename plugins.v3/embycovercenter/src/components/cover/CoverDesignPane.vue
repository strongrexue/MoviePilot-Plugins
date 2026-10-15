<script setup>
import { computed, onMounted, ref } from 'vue'
import { useCoverDesigner } from './useCoverDesigner'

/**
 * 封面设计面板：目标对象 / 素材选择 / 详细参数 / 封面上传 / 字体与模板管理。
 *
 * 参数表单由后端布局 schema 驱动（common_fields + layout.fields），
 * 新增布局或字段不需要改本组件。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  initialConfig: { type: Object, default: () => ({}) },
  servers: { type: Array, default: () => [] },
})

const designer = useCoverDesigner({
  api: () => props.api,
  pluginId: () => props.pluginId,
  initialConfig: props.initialConfig,
})
const { form, previewImage, previewInfo, message, messageOk, layoutFields, commonFields } = designer

const serverItems = computed(() =>
  props.servers.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
)

const modeItems = [
  { title: '随机抽取', value: 'random' },
  { title: '最新入库', value: 'latest' },
]

const allFields = computed(() => [...commonFields.value, ...layoutFields.value])

const fontInput = ref(null)
const templateInput = ref(null)
const localImageInput = ref(null)
const templateName = ref('')

function pick(reference) {
  const element = reference.value
  if (element) element.click()
}

function onFontPicked(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (file) designer.uploadFont(file)
}

function onTemplatePicked(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (file) designer.uploadTemplate(file)
}

function onLocalImagePicked(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (file) designer.applyLocalImage(file)
}

onMounted(designer.loadAll)

/** 供父组件保存配置时取当前封面设置（这些字段会持久化到插件配置）。 */
function snapshot() {
  return {
    cover_layout: form.layout,
    cover_config: { ...form.config },
    assets_mode: form.mode,
    poster_count: Number(form.poster_count || 0),
    backdrop_count: Number(form.backdrop_count || 0),
  }
}

defineExpose({ snapshot })
</script>

<template>
  <VCard variant="tonal" class="ec-cover">
    <VCardItem>
      <VCardTitle class="text-subtitle-1">封面设计</VCardTitle>
      <VCardSubtitle class="text-caption">
        生成后可「应用」到媒体库封面；也可直接上传成品图替换。
      </VCardSubtitle>
      <template #append>
        <VBtn size="small" variant="text" :loading="designer.loading.value" @click="designer.loadAll">
          刷新
        </VBtn>
      </template>
    </VCardItem>
    <VDivider />
    <VCardText class="ec-cover-body">
      <div v-if="message" :class="messageOk ? 'text-success' : 'text-error'" class="ec-msg">
        {{ message }}
      </div>

      <VRow dense>
        <VCol cols="12" md="7">
          <VCard variant="text" class="ec-section">
            <VCardText>
              <div class="ec-grid">
                <VSelect
                  v-model="form.server"
                  :items="serverItems"
                  label="媒体服务器"
                  density="compact"
                  variant="outlined"
                  hide-details
                  @update:model-value="designer.onServerChange"
                />
                <VSelect
                  v-model="form.library_id"
                  :items="designer.libraryItems.value"
                  label="媒体库"
                  density="compact"
                  variant="outlined"
                  hide-details
                  @update:model-value="designer.syncTitleFromLibrary"
                />
                <VSelect
                  v-model="form.layout"
                  :items="designer.layoutItems.value"
                  label="布局"
                  density="compact"
                  variant="outlined"
                  hide-details
                  @update:model-value="designer.onLayoutChange"
                />
                <VSelect
                  v-model="form.mode"
                  :items="modeItems"
                  label="素材模式"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <VTextField
                  v-model="form.poster_count"
                  type="number"
                  label="海报数量"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <VTextField
                  v-model="form.backdrop_count"
                  type="number"
                  label="背景数量"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
              </div>

              <div class="ec-subtitle">参数</div>
              <div class="ec-grid">
                <template v-for="field in allFields" :key="field.key">
                  <VSwitch
                    v-if="field.type === 'boolean'"
                    v-model="form.config[field.key]"
                    :label="field.label"
                    color="primary"
                    hide-details
                    inset
                  />
                  <VSelect
                    v-else-if="field.type === 'select'"
                    v-model="form.config[field.key]"
                    :items="field.options || []"
                    :label="field.label"
                    density="compact"
                    variant="outlined"
                    hide-details
                  />
                  <VSelect
                    v-else-if="field.type === 'font'"
                    v-model="form.config[field.key]"
                    :items="designer.fontItems.value"
                    :label="field.label"
                    density="compact"
                    variant="outlined"
                    hide-details
                  />
                  <VTextField
                    v-else
                    v-model="form.config[field.key]"
                    :label="field.label"
                    :type="field.type === 'number' ? 'number' : (field.type === 'color' ? 'color' : 'text')"
                    :step="field.step || undefined"
                    density="compact"
                    variant="outlined"
                    hide-details
                  />
                </template>
              </div>

              <div class="ec-subtitle">封面上传</div>
              <div class="ec-actions">
                <VBtn size="small" variant="tonal" :loading="designer.applying.value" @click="pick(localImageInput)">
                  选择本地封面（直接替换）
                </VBtn>
                <VBtn
                  size="small"
                  variant="tonal"
                  :disabled="!previewImage"
                  :loading="designer.applying.value"
                  @click="designer.applyPreviewImage"
                >
                  应用当前预览图
                </VBtn>
              </div>
            </VCardText>
          </VCard>
        </VCol>

        <VCol cols="12" md="5">
          <VCard variant="text" class="ec-section ec-preview-card">
            <VCardText class="ec-preview-body">
              <VProgressLinear v-if="designer.previewing.value" indeterminate color="primary" height="2" />
              <img v-if="previewImage" :src="previewImage" class="ec-preview" alt="封面预览" />
              <div v-else class="ec-placeholder">
                点击「生成预览」查看封面效果
              </div>
              <div v-if="previewInfo.title" class="text-caption">
                {{ previewInfo.title }}<span v-if="previewInfo.count"> · {{ previewInfo.count }} 部</span>
              </div>
            </VCardText>
          </VCard>
          <div class="ec-actions mt-2">
            <VBtn
              color="primary"
              size="small"
              variant="flat"
              prepend-icon="mdi-image-refresh"
              :loading="designer.previewing.value"
              @click="designer.previewCover"
            >
              生成预览
            </VBtn>
            <VBtn
              size="small"
              variant="tonal"
              prepend-icon="mdi-check"
              :loading="designer.applying.value"
              @click="designer.applyCover"
            >
              渲染并应用
            </VBtn>
          </div>
        </VCol>
      </VRow>

      <VRow dense class="mt-1">
        <VCol cols="12" md="6">
          <div class="ec-subtitle">字体（{{ designer.fonts.value.length }}）</div>
          <div class="ec-chips">
            <VChip
              v-for="name in designer.fonts.value"
              :key="name"
              size="small"
              variant="tonal"
              closable
              @click:close="designer.deleteFont(name)"
            >
              {{ name }}
            </VChip>
            <span v-if="!designer.fonts.value.length" class="text-caption text-medium-emphasis">
              未上传字体（将回退到默认字体）
            </span>
          </div>
          <VBtn size="small" variant="text" prepend-icon="mdi-upload" class="mt-1" @click="pick(fontInput)">
            上传字体（.ttf/.otf）
          </VBtn>
        </VCol>

        <VCol cols="12" md="6">
          <div class="ec-subtitle">模板预设（{{ designer.templates.value.length }}）</div>
          <div class="ec-templates">
            <div v-for="template in designer.templates.value" :key="template.filename" class="ec-template">
              <img
                v-if="template.has_preview"
                :src="designer.templatePreviewUrl(template)"
                class="ec-template-thumb"
                alt="模板预览"
              />
              <div class="ec-template-name">{{ template.name || template.filename }}</div>
              <div class="ec-template-ops">
                <VBtn size="x-small" variant="text" @click="designer.loadTemplate(template)">载入</VBtn>
                <VBtn size="x-small" variant="text" @click="designer.deleteTemplate(template.filename)">删除</VBtn>
              </div>
            </div>
            <span v-if="!designer.templates.value.length" class="text-caption text-medium-emphasis">
              暂无模板
            </span>
          </div>
          <div class="ec-actions mt-1">
            <VTextField
              v-model="templateName"
              label="模板文件名"
              placeholder="如 my-preset.json"
              density="compact"
              variant="outlined"
              hide-details
              class="ec-template-input"
            />
            <VBtn size="small" variant="text" :disabled="!templateName" @click="designer.saveTemplate(templateName)">
              保存当前
            </VBtn>
            <VBtn size="small" variant="text" @click="pick(templateInput)">上传模板</VBtn>
          </div>
        </VCol>
      </VRow>

      <input ref="fontInput" type="file" accept=".ttf,.otf,.ttc" class="ec-hidden" @change="onFontPicked" />
      <input ref="templateInput" type="file" accept=".json" class="ec-hidden" @change="onTemplatePicked" />
      <input ref="localImageInput" type="file" accept="image/*" class="ec-hidden" @change="onLocalImagePicked" />
    </VCardText>
  </VCard>
</template>

<style scoped>
.ec-cover {
  grid-column: 1 / -1;
  min-width: 0;
}
.ec-cover-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ec-msg {
  font-size: 12px;
}
.ec-section {
  height: 100%;
}
.ec-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.ec-subtitle {
  font-size: 13px;
  font-weight: 600;
  margin: 10px 0 6px;
  opacity: 0.8;
}
.ec-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.ec-preview-card {
  min-height: 220px;
}
.ec-preview-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.ec-preview {
  width: 100%;
  max-height: 320px;
  object-fit: contain;
  border-radius: 8px;
}
.ec-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  font-size: 13px;
  opacity: 0.6;
}
.ec-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ec-templates {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ec-template {
  width: 132px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  overflow: hidden;
}
.ec-template-thumb {
  width: 100%;
  height: 74px;
  object-fit: cover;
}
.ec-template-name {
  padding: 4px 6px 0;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ec-template-ops {
  display: flex;
  justify-content: space-between;
  padding: 0 2px 4px;
}
.ec-template-input {
  max-width: 220px;
}
.ec-hidden {
  display: none;
}
@media (max-width: 760px) {
  .ec-grid {
    grid-template-columns: 1fr;
  }
}
</style>
