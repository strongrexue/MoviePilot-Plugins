<script setup>
import { computed, onMounted, ref } from 'vue'
import { useCoverDesigner } from './useCoverDesigner'

/**
 * 封面设计面板：目标对象 / 布局参数（schema 驱动，支持滑块）/ 封面上传 / 字体与模板。
 *
 * 参数表单完全由后端布局 schema 生成：分组 → 逐项按 type 渲染控件
 * （range 滑块、select、color、font、boolean、text、number）。
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
const { form, previewImage, previewInfo, message, messageOk } = designer

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

const fontInput = ref(null)
const templateInput = ref(null)
const localImageInput = ref(null)
const templateName = ref('')

/** select 的 options 统一成 {title, value}，避免 Vuetify 渲染成 [object Object]。 */
function toSelectItems(item) {
  return (item.options || []).map(option => ({
    title: option.label !== undefined ? option.label : option.title,
    value: option.value,
  }))
}

function fieldValue(item) {
  return form.config[item.key]
}

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
  <div class="ec-cover">
    <div class="ec-toolbar">
      <div class="ec-toolbar-head">
        <div class="ec-h">封面设计</div>
        <div class="ec-sub">选媒体库 → 调风格 → 生成预览 → 应用到媒体库封面</div>
      </div>
      <div class="ec-toolbar-actions">
        <VBtn size="small" variant="text" :loading="designer.loading.value" @click="designer.loadAll">刷新</VBtn>
        <VBtn
          size="small"
          variant="tonal"
          prepend-icon="mdi-image-refresh"
          :loading="designer.previewing.value"
          @click="designer.previewCover"
        >
          生成预览
        </VBtn>
        <VBtn
          color="primary"
          size="small"
          variant="flat"
          prepend-icon="mdi-check"
          :loading="designer.applying.value"
          @click="designer.applyCover"
        >
          渲染并应用
        </VBtn>
      </div>
    </div>

    <VAlert v-if="message" :type="messageOk ? 'success' : 'error'" variant="tonal" density="compact" class="mb-2">
      {{ message }}
    </VAlert>

    <div class="ec-cols">
      <!-- 左：控件区 -->
      <div class="ec-controls">
        <VCard variant="tonal" class="ec-block">
          <VCardItem class="py-2">
            <VCardTitle class="text-subtitle-1">目标对象</VCardTitle>
          </VCardItem>
          <VCardText class="ec-grid">
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
              label="风格（布局）"
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
          </VCardText>
        </VCard>

        <VCard v-for="(group, groupIndex) in designer.allGroups.value" :key="groupIndex" variant="tonal" class="ec-block">
          <VCardItem class="py-2">
            <VCardTitle class="text-subtitle-1">{{ group.group }}</VCardTitle>
          </VCardItem>
          <VCardText class="ec-fields">
            <template v-for="item in group.items" :key="item.key">
              <!-- 滑块 -->
              <div v-if="item.type === 'range'" class="ec-slider">
                <div class="ec-slider-head">
                  <span>{{ item.label }}</span>
                  <b>{{ fieldValue(item) }}</b>
                </div>
                <VSlider
                  v-model="form.config[item.key]"
                  :min="item.min !== undefined && item.min !== null ? item.min : 0"
                  :max="item.max !== undefined && item.max !== null ? item.max : 100"
                  :step="item.step || 1"
                  density="compact"
                  hide-details
                  color="primary"
                  thumb-label
                />
              </div>
              <!-- 下拉 -->
              <VSelect
                v-else-if="item.type === 'select'"
                v-model="form.config[item.key]"
                :items="toSelectItems(item)"
                :label="item.label"
                density="compact"
                variant="outlined"
                hide-details
              />
              <!-- 字体 -->
              <VSelect
                v-else-if="item.type === 'font'"
                v-model="form.config[item.key]"
                :items="designer.fontItems.value"
                :label="item.label"
                density="compact"
                variant="outlined"
                hide-details
              />
              <!-- 开关 -->
              <VSwitch
                v-else-if="item.type === 'boolean'"
                v-model="form.config[item.key]"
                :label="item.label"
                color="primary"
                hide-details
                inset
                density="compact"
              />
              <!-- 颜色：色块 + 文本框 -->
              <div v-else-if="item.type === 'color'" class="ec-color">
                <label class="ec-color-swatch" :style="{ background: fieldValue(item) || '#000000' }">
                  <input
                    type="color"
                    class="ec-color-input"
                    :value="fieldValue(item) || '#000000'"
                    @input="form.config[item.key] = $event.target.value"
                  />
                </label>
                <VTextField
                  v-model="form.config[item.key]"
                  :label="item.label"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
              </div>
              <!-- 数字 / 文本 -->
              <VTextField
                v-else
                v-model="form.config[item.key]"
                :label="item.label"
                :type="item.type === 'number' ? 'number' : 'text'"
                density="compact"
                variant="outlined"
                hide-details
              />
            </template>
          </VCardText>
        </VCard>

        <VCard variant="tonal" class="ec-block">
          <VCardItem class="py-2">
            <VCardTitle class="text-subtitle-1">封面上传</VCardTitle>
          </VCardItem>
          <VCardText class="ec-row-wrap">
            <VBtn size="small" variant="tonal" prepend-icon="mdi-image" :loading="designer.applying.value" @click="pick(localImageInput)">
              选择本地封面（直接替换）
            </VBtn>
            <VBtn
              size="small"
              variant="tonal"
              prepend-icon="mdi-content-save-check"
              :disabled="!previewImage"
              :loading="designer.applying.value"
              @click="designer.applyPreviewImage"
            >
              应用当前预览图
            </VBtn>
          </VCardText>
        </VCard>

        <VCard variant="tonal" class="ec-block">
          <VCardItem class="py-2">
            <VCardTitle class="text-subtitle-1">字体（{{ designer.fonts.value.length }}）</VCardTitle>
            <template #append>
              <VBtn size="small" variant="text" prepend-icon="mdi-upload" @click="pick(fontInput)">上传</VBtn>
            </template>
          </VCardItem>
          <VCardText>
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
                未上传字体（中文会回退为方块），请先上传 .ttf/.otf
              </span>
            </div>
          </VCardText>
        </VCard>

      </div>

      <!-- 右：预览 + 模板预设（都偏视觉，放右侧填满空间） -->
      <div class="ec-preview-side">
        <VCard variant="tonal" class="ec-preview-card">
          <VCardItem class="py-2">
            <VCardTitle class="text-subtitle-1">预览</VCardTitle>
            <template #append>
              <VBtn
                size="small"
                variant="text"
                prepend-icon="mdi-image-refresh"
                :loading="designer.previewing.value"
                @click="designer.previewCover"
              >
                生成
              </VBtn>
            </template>
          </VCardItem>
          <VCardText class="ec-preview-body">
            <VProgressLinear v-if="designer.previewing.value" indeterminate color="primary" height="2" />
            <img v-if="previewImage" :src="previewImage" class="ec-preview" alt="封面预览" />
            <div v-else class="ec-placeholder">点击「生成」查看封面效果</div>
            <div v-if="previewInfo.title" class="text-caption">
              {{ previewInfo.title }}<span v-if="previewInfo.count"> · {{ previewInfo.count }} 部</span>
            </div>
          </VCardText>
        </VCard>

        <VCard variant="tonal" class="ec-block mt-2">
          <VCardItem class="py-2">
            <VCardTitle class="text-subtitle-1">模板预设（{{ designer.templates.value.length }}）</VCardTitle>
            <template #append>
              <VBtn size="small" variant="text" prepend-icon="mdi-upload" @click="pick(templateInput)">上传</VBtn>
            </template>
          </VCardItem>
          <VCardText>
            <div class="ec-templates">
              <div
                v-for="template in designer.templates.value"
                :key="template.filename"
                class="ec-template"
                :class="{ 'ec-template--active': template.layout === form.layout }"
              >
                <img
                  v-if="template.has_preview"
                  :src="designer.templatePreviewUrl(template)"
                  class="ec-template-thumb"
                  alt=""
                />
                <div v-else class="ec-template-noimg">{{ template.layout }}</div>
                <div class="ec-template-name">{{ template.name || template.filename }}</div>
                <div class="ec-template-ops">
                  <VBtn size="x-small" variant="text" @click="designer.loadTemplate(template)">载入</VBtn>
                  <VBtn size="x-small" variant="text" @click="designer.deleteTemplate(template.filename)">删除</VBtn>
                </div>
              </div>
            </div>
            <div class="ec-row-wrap mt-2">
              <VTextField
                v-model="templateName"
                label="模板文件名"
                placeholder="如 我的封面.json"
                density="compact"
                variant="outlined"
                hide-details
                class="ec-template-input"
              />
              <VBtn size="small" variant="tonal" :disabled="!templateName" @click="designer.saveTemplate(templateName)">
                保存当前
              </VBtn>
            </div>
          </VCardText>
        </VCard>
      </div>
    </div>

    <input ref="fontInput" type="file" accept=".ttf,.otf,.ttc" class="ec-hidden" @change="onFontPicked" />
    <input ref="templateInput" type="file" accept=".json" class="ec-hidden" @change="onTemplatePicked" />
    <input ref="localImageInput" type="file" accept="image/*" class="ec-hidden" @change="onLocalImagePicked" />
  </div>
</template>

<style scoped>
.ec-cover {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.ec-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.ec-h {
  font-size: 15px;
  font-weight: 600;
}
.ec-sub {
  font-size: 12px;
  opacity: 0.65;
}
.ec-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ec-cols {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
  gap: 12px;
  align-items: start;
}
.ec-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.ec-block {
  border-radius: 10px;
}
.ec-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.ec-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
}
.ec-slider {
  grid-column: 1 / -1;
}
.ec-slider-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 2px;
  opacity: 0.85;
}
.ec-color {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}
.ec-color-swatch {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  overflow: hidden;
  cursor: pointer;
  display: block;
}
.ec-color-input {
  width: 100%;
  height: 100%;
  border: none;
  padding: 0;
  background: transparent;
  cursor: pointer;
}
.ec-row-wrap {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.ec-preview-side {
  position: sticky;
  top: 8px;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.ec-preview-card {
  min-height: 220px;
  border-radius: 10px;
}
.ec-preview-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.ec-preview {
  width: 100%;
  max-height: 42vh;
  object-fit: contain;
  border-radius: 8px;
}
.ec-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  font-size: 13px;
  opacity: 0.6;
}
.ec-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ec-templates {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(116px, 1fr));
  gap: 8px;
}
.ec-template {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  overflow: hidden;
}
.ec-template--active {
  border-color: rgb(var(--v-theme-primary));
}
.ec-template-thumb {
  width: 100%;
  height: 78px;
  object-fit: cover;
  display: block;
}
.ec-template-noimg {
  height: 78px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  opacity: 0.55;
  background: rgba(var(--v-theme-on-surface), 0.04);
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
@media (max-width: 1100px) {
  .ec-cols {
    grid-template-columns: 1fr;
  }
  .ec-preview-side {
    position: static;
  }
}
@media (max-width: 760px) {
  .ec-grid,
  .ec-fields {
    grid-template-columns: 1fr;
  }
}
</style>
