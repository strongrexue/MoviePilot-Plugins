<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import CoverField from './CoverField.vue'
import { useCoverDesigner } from './useCoverDesigner'

/**
 * 封面设计面板（单列 / 对齐 ChillPoster）。
 *
 * 自上而下全部占满宽度：
 * - 顶部工具条：刷新 / 生成预览 / 渲染并应用；
 * - 预览横版：合成结果占满整行，关键参数摘要压成图下一行小字；
 * - 模板预设横版：点卡片即载入；
 * - 可折叠分组（点击展开/收起，头部右侧带一行关键值摘要）：
 *   目标对象 → 布局分组 → 文字内容 → 其余布局分组 → 引擎通用 → 封面上传 → 字体。
 *
 * 主/副标题属于「文字内容」（跟随媒体库 / 用户输入），载入模板只套用风格参数。
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
const { form, previewImage, previewInfo, message, messageOk, styleGroups, engineGroup } = designer

/** 删除确认弹窗：模板 / 字体的删除入口太容易误点，统一先确认再执行。 */
const confirm = reactive({ show: false, title: '', text: '', action: null })
function askDelete(title, text, action) {
  confirm.title = title
  confirm.text = text
  confirm.action = action
  confirm.show = true
}
const askDeleteTemplate = template =>
  askDelete(
    '删除模板预设',
    `确定删除「${template.name || template.filename}」吗？内置模板重启插件后会自动补回，自行上传的不会。`,
    () => designer.deleteTemplate(template.filename),
  )
const askDeleteFont = name =>
  askDelete(
    '删除字体',
    `确定删除字体「${name}」吗？正在使用该字体的封面会回退为内置字体。`,
    () => designer.deleteFont(name),
  )
function confirmOk() {
  const action = confirm.action
  confirm.show = false
  confirm.action = null
  if (action) action()
}

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

const templateName = ref('')

/** 默认只展开 1-2 组：目标对象 + 第一个布局分组（无布局分组时只展开目标对象）。 */
const openSections = ref(['target', 'style-0'])

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

const currentLayoutLabel = computed(() => {
  const hit = designer.layoutItems.value.find(item => item.value === form.layout)
  return hit ? hit.title : form.layout
})

const currentLibraryName = computed(() => {
  const hit = designer.libraries.value.find(item => item.id === form.library_id)
  return hit ? (hit.name || hit.id) : '未选媒体库'
})

const canvasLabel = computed(() => {
  const width = Number(form.config.canvas_width || 0)
  const height = Number(form.config.canvas_height || 0)
  return width && height ? `${width} × ${height}` : '—'
})

/** 头部摘要：取前两个有值的可读参数，收起时也能一眼看到关键设置。 */
function summarize(items) {
  const readable = ['range', 'number', 'select', 'font', 'color']
  const parts = []
  for (const item of items || []) {
    if (parts.length >= 2) break
    if (!item || !readable.includes(item.type)) continue
    const value = form.config[item.key]
    if (value === undefined || value === null || value === '') continue
    let text = String(value)
    if (item.type === 'select' && Array.isArray(item.options)) {
      const hit = item.options.find(option => String(option.value) === text)
      if (hit) text = String(hit.label || text)
    }
    parts.push(`${item.label} ${text}`)
  }
  return parts.join(' · ') || '—'
}

/** 折叠分组清单：目标对象 → 布局分组 → 文字内容 → 其余布局分组 → 引擎通用 → 封面上传 → 字体。 */
const blocks = computed(() => {
  const list = []
  list.push({
    id: 'target',
    kind: 'target',
    icon: 'mdi-crosshairs-gps',
    title: '目标对象',
    summary: `${form.server || '未选服务器'} · ${currentLibraryName.value} · ${currentLayoutLabel.value}`,
  })
  const styles = styleGroups.value.filter(group => group.items.length)
  if (styles.length) {
    list.push({
      id: 'style-0',
      kind: 'style',
      icon: 'mdi-image-multiple-outline',
      title: styles[0].group,
      summary: summarize(styles[0].items),
      items: styles[0].items,
    })
  }
  list.push({
    id: 'content',
    kind: 'content',
    icon: 'mdi-format-text',
    title: '文字内容',
    summary: `${form.config.title || '—'} / ${form.config.subtitle || '—'}`,
  })
  styles.slice(1).forEach((group, index) => {
    list.push({
      id: `style-${index + 1}`,
      kind: 'style',
      icon: 'mdi-tune-variant',
      title: group.group,
      summary: summarize(group.items),
      items: group.items,
    })
  })
  if (engineGroup.value) {
    list.push({
      id: 'engine',
      kind: 'engine',
      icon: 'mdi-cog-outline',
      title: engineGroup.value.group,
      summary: summarize(engineGroup.value.items),
      items: engineGroup.value.items,
    })
  }
  list.push({ id: 'upload', kind: 'upload', icon: 'mdi-image-plus', title: '封面上传', summary: '成品图替换 / 应用当前预览' })
  list.push({
    id: 'fonts',
    kind: 'fonts',
    icon: 'mdi-format-font',
    title: `字体（${designer.fonts.value.length}）`,
    summary: '点击已装字体右侧 × 可删除',
  })
  return list
})

onMounted(designer.loadAll)
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

    <VAlert v-if="message" :type="messageOk ? 'success' : 'error'" variant="tonal" density="compact">
      {{ message }}
    </VAlert>

    <!-- 预览：横版占满 -->
    <VCard variant="tonal" class="ec-band">
      <VCardItem class="py-2">
        <VCardTitle class="text-subtitle-1">预览</VCardTitle>
        <VCardSubtitle class="text-caption">横版占满 · 生成后可一键应用为当前媒体库封面</VCardSubtitle>
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
      <VCardText>
        <VProgressLinear v-if="designer.previewing.value" indeterminate color="primary" height="2" class="mb-2" />
        <div class="ec-preview-stage">
          <img v-if="previewImage" :src="previewImage" class="ec-preview" alt="封面预览" />
          <div v-else class="ec-placeholder">点击「生成」查看封面效果</div>
        </div>
        <div class="ec-meta">
          <span>布局 {{ currentLayoutLabel }}</span>
          <span>媒体库 {{ currentLibraryName }}</span>
          <span>条目 {{ previewInfo.count || 0 }}</span>
          <span>画布 {{ canvasLabel }}</span>
        </div>
      </VCardText>
    </VCard>

    <!-- 模板预设：横版占满 -->
    <VCard variant="tonal" class="ec-band">
      <VCardItem class="py-2">
        <VCardTitle class="text-subtitle-1">模板预设（{{ designer.templates.value.length }}）</VCardTitle>
        <VCardSubtitle class="text-caption">横版占满 · 点击卡片即载入（仅套用风格参数，不改标题/副标题）</VCardSubtitle>
        <template #append>
          <VBtn tag="label" for="ec-upload-template" size="small" variant="text" prepend-icon="mdi-upload">
            上传
          </VBtn>
        </template>
      </VCardItem>
      <VCardText>
        <div class="ec-templates">
          <div
            v-for="template in designer.templates.value"
            :key="template.filename"
            class="ec-template"
            :class="{ 'ec-template--active': template.layout === form.layout }"
            role="button"
            :title="`点击载入：${template.name || template.filename}`"
            @click="designer.loadTemplate(template)"
          >
            <img
              v-if="template.has_preview"
              :src="designer.templatePreviewUrl(template)"
              class="ec-template-thumb"
              alt=""
            />
            <div v-else class="ec-template-noimg">{{ template.layout }}</div>
            <VBtn
              class="ec-template-del"
              size="x-small"
              icon
              variant="text"
              title="删除模板"
              @click.stop="askDeleteTemplate(template)"
            >
              <VIcon icon="mdi-close" size="14" />
            </VBtn>
            <div class="ec-template-name">{{ template.name || template.filename }}</div>
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

    <!-- 可折叠分组 -->
    <VExpansionPanels v-model="openSections" variant="accordion" flat multiple class="ec-acc">
      <VExpansionPanel v-for="block in blocks" :key="block.id" :value="block.id">
        <template #title>
          <VIcon :icon="block.icon" size="18" class="ec-acc-icon me-2" />
          <span class="ec-acc-title">{{ block.title }}</span>
          <span class="ec-acc-sum ms-auto">{{ block.summary }}</span>
        </template>
        <template #text>
          <div v-if="block.kind === 'target'" class="ec-fields">
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
              @update:model-value="designer.syncFromLibrary"
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
          </div>

          <div v-else-if="block.kind === 'content'" class="ec-fields">
            <VTextField
              v-model="form.config.title"
              label="主标题内容"
              density="compact"
              variant="outlined"
              hide-details
            />
            <VTextField
              v-model="form.config.subtitle"
              label="副标题内容（英文名）"
              density="compact"
              variant="outlined"
              hide-details
              @update:model-value="designer.onSubtitleEdited"
            />
            <div class="text-caption text-medium-emphasis ec-span">
              主标题跟随所选媒体库，副标题自动取英文名（手填即记住该库），载入模板不会改它们。
            </div>
          </div>

          <div v-else-if="block.kind === 'style' || block.kind === 'engine'" class="ec-fields">
            <CoverField
              v-for="item in block.items"
              :key="item.key"
              :item="item"
              :config="form.config"
              :fonts="designer.fontItems.value"
            />
          </div>

          <div v-else-if="block.kind === 'upload'" class="ec-row-wrap">
            <VBtn
              tag="label"
              for="ec-upload-local-image"
              size="small"
              variant="tonal"
              prepend-icon="mdi-image"
              :loading="designer.applying.value"
            >
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
          </div>

          <div v-else-if="block.kind === 'fonts'" class="ec-chips">
            <VChip
              v-for="name in designer.fonts.value"
              :key="name"
              size="small"
              variant="tonal"
              closable
              @click:close="askDeleteFont(name)"
            >
              {{ name }}
            </VChip>
            <span v-if="!designer.fonts.value.length" class="text-caption text-medium-emphasis">
              未上传字体（中文会回退为方块），请先上传 .ttf/.otf
            </span>
            <VBtn tag="label" for="ec-upload-font" size="small" variant="text" prepend-icon="mdi-upload">
              上传字体
            </VBtn>
          </div>
        </template>
      </VExpansionPanel>
    </VExpansionPanels>

    <input id="ec-upload-font" type="file" accept=".ttf,.otf,.ttc" class="ec-file-input" @change="onFontPicked" />
    <input id="ec-upload-template" type="file" accept=".json" class="ec-file-input" @change="onTemplatePicked" />
    <input id="ec-upload-local-image" type="file" accept="image/*" class="ec-file-input" @change="onLocalImagePicked" />

    <VDialog v-model="confirm.show" max-width="400">
      <VCard>
        <VCardItem class="py-3">
          <VCardTitle class="text-subtitle-1">{{ confirm.title }}</VCardTitle>
        </VCardItem>
        <VCardText class="text-body-2">{{ confirm.text }}</VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="confirm.show = false">取消</VBtn>
          <VBtn color="error" variant="flat" @click="confirmOk">删除</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.ec-cover {
  display: flex;
  flex-direction: column;
  gap: 10px;
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
.ec-band {
  border-radius: 10px;
}
.ec-preview-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  overflow: hidden;
}
.ec-preview {
  width: 100%;
  max-height: 46vh;
  object-fit: contain;
  border-radius: 8px;
}
.ec-placeholder {
  padding: 24px;
  font-size: 13px;
  opacity: 0.6;
  text-align: center;
}
.ec-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.ec-meta span {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(var(--v-theme-on-surface), 0.05);
  opacity: 0.75;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.ec-acc {
  background: transparent;
}
.ec-acc-title {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ec-acc-sum {
  max-width: 46%;
  font-size: 12px;
  opacity: 0.6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 分组面板的卡片化样式见文件末尾的非 scoped 样式块：
   裸 :deep() 规则会被构建静默丢弃（v1.4.2~v1.4.5 分组样式未出厂的根因），
   故移出 :deep 并以 .ec-acc 命名空间隔离 */
.ec-acc-icon {
  color: rgb(var(--v-theme-primary));
}
.ec-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
}
.ec-span {
  grid-column: 1 / -1;
}
.ec-row-wrap {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.ec-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.ec-templates {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(116px, 1fr));
  gap: 8px;
}
.ec-template {
  position: relative;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}
.ec-template:hover {
  border-color: rgba(var(--v-theme-primary), 0.6);
  transform: translateY(-1px);
}
.ec-template--active {
  border-color: rgb(var(--v-theme-primary));
  box-shadow: 0 0 0 1px rgba(var(--v-theme-primary), 0.35);
}
.ec-template-del {
  position: absolute;
  top: 2px;
  right: 2px;
  opacity: 0.55;
}
.ec-template-del:hover {
  opacity: 1;
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
  padding: 4px 6px 6px;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ec-template-input {
  max-width: 220px;
}
/* 文件选择框：视觉隐藏但**不可用 display:none**——宿主环境下对 display:none
   的 input 程序化 click() 不弹窗（三处上传按钮失灵的根因），现改由
   <VBtn tag="label" for=...> 原生激活，输入框只需视觉隐藏（clip 技法）。 */
.ec-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  pointer-events: none;
}
@media (max-width: 760px) {
  .ec-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>

<style>
/* 非 scoped：分组面板卡片化样式（数值与 v1.4.5 定稿一致）。
   裸 :deep() 会被构建丢弃，改用 .ec-acc 命名空间隔离，仅作用于封面设计分组；
   底色与「预览 / 模板预设」tonal 卡片同配方（on-surface @ 12%，展开 15%），
   组间距对齐 .ec-cover 的 10px gap，标题行 44px 不加高 */
/* 分组宽屏左右两列（align-items:start 让每个面板保持自身高度），
   组间距由 grid gap 接管；窄屏回单列 */
.ec-acc {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
  align-items: start;
}
.ec-acc .v-expansion-panel {
  border-radius: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgba(var(--v-theme-on-surface), 0.12);
  overflow: hidden;
  isolation: isolate;
  transition: background 0.15s, border-color 0.15s;
}
.ec-acc .v-expansion-panel:not(.v-expansion-panel--active):hover {
  border-color: rgba(var(--v-theme-primary), 0.45);
}
.ec-acc .v-expansion-panel--active {
  background: rgba(var(--v-theme-on-surface), 0.15);
  border-color: rgba(var(--v-theme-primary), 0.35);
}
.ec-acc .v-expansion-panel-title {
  min-height: 44px;
}
.ec-acc .v-expansion-panel-title--active {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
@media (max-width: 1000px) {
  .ec-acc {
    grid-template-columns: 1fr;
  }
}
</style>
