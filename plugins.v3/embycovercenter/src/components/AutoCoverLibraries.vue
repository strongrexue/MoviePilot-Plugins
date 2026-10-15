<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { getPluginApi, unwrap } from './api'

/**
 * 自动封面目标媒体库选择（ChillPoster 风格）：
 * 按服务器分节可折叠，节头「全选」复选框 + 选中数徽标，媒体库为复选 chips
 * （选中 tonal 填充 + 品牌色描边）。v-model 为 { 服务器名: [库ID, ...] }；
 * 与「参与封面的服务器」的交集由后端执行时再取，本组件只管选择。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  modelValue: { type: Object, default: () => ({}) },
  servers: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const sections = ref([])
const loading = ref(false)
const open = reactive({})

const selectedTotal = computed(() =>
  Object.values(props.modelValue || {}).reduce(
    (sum, list) => sum + (Array.isArray(list) ? list.length : 0),
    0,
  ),
)

function isSelected(server, libraryId) {
  const list = props.modelValue?.[server]
  return Array.isArray(list) && list.includes(libraryId)
}

function countSelected(section) {
  const list = props.modelValue?.[section.name]
  return Array.isArray(list) ? list.length : 0
}

function allSelected(section) {
  return section.libraries.length > 0 && countSelected(section) >= section.libraries.length
}

function emitValue(next) {
  emit('update:modelValue', { ...next })
}

function toggle(server, libraryId) {
  if (props.disabled) return
  const current = props.modelValue?.[server]
  const list = Array.isArray(current) ? [...current] : []
  const index = list.indexOf(libraryId)
  if (index >= 0) list.splice(index, 1)
  else list.push(libraryId)
  const next = { ...(props.modelValue || {}) }
  if (list.length) next[server] = list
  else delete next[server]
  emitValue(next)
}

function toggleSection(section) {
  if (props.disabled) return
  const next = { ...(props.modelValue || {}) }
  if (allSelected(section)) delete next[section.name]
  else next[section.name] = section.libraries.map(library => library.id)
  emitValue(next)
}

function toggleOpen(name) {
  open[name] = !open[name]
}

async function loadAll() {
  if (loading.value) return
  if (!props.servers.length) {
    sections.value = []
    return
  }
  loading.value = true
  const results = await Promise.all(
    props.servers.map(async server => {
      try {
        const query = server.name ? `?server=${encodeURIComponent(server.name)}` : ''
        const data = unwrap(await getPluginApi(props.api, props.pluginId, `libraries${query}`)) || {}
        return {
          name: server.name,
          libraries: Array.isArray(data.libraries) ? data.libraries : [],
          error: '',
        }
      } catch (error) {
        return {
          name: server.name,
          libraries: [],
          error: error?.message || '媒体库读取失败',
        }
      }
    }),
  )
  sections.value = results
  for (const section of results) open[section.name] = true
  loading.value = false
}

// servers 由父组件异步加载，就绪后（或变化时）重拉媒体库
watch(
  () => props.servers,
  () => loadAll(),
)
onMounted(loadAll)
</script>

<template>
  <div class="ec-acl">
    <div class="ec-acl-head">
      <div class="ec-acl-title">
        目标媒体库
        <VChip size="x-small" variant="tonal" color="primary" class="ms-2">已选 {{ selectedTotal }}</VChip>
      </div>
      <VBtn size="small" variant="text" :loading="loading" @click="loadAll">刷新</VBtn>
    </div>

    <div v-if="!sections.length && !loading" class="text-caption text-medium-emphasis">
      未获取到媒体服务器：请先在「参与封面的服务器」里确认宿主已启用 Emby。
    </div>

    <div v-for="section in sections" :key="section.name" class="ec-acl-section">
      <div class="ec-acl-row" role="button" @click="toggleOpen(section.name)">
        <VIcon
          icon="mdi-chevron-down"
          size="18"
          class="ec-acl-caret"
          :class="{ 'ec-acl-caret--closed': !open[section.name] }"
        />
        <span class="ec-acl-name">{{ section.name }}</span>
        <span class="ec-acl-count">{{ countSelected(section) }}/{{ section.libraries.length }}</span>
        <VCheckboxBtn
          :model-value="allSelected(section)"
          :indeterminate="countSelected(section) > 0 && !allSelected(section)"
          :disabled="props.disabled || !section.libraries.length"
          color="primary"
          hide-details
          density="compact"
          @click.stop
          @update:model-value="toggleSection(section)"
        />
      </div>
      <div v-show="open[section.name]" class="ec-acl-grid">
        <button
          v-for="library in section.libraries"
          :key="library.id"
          type="button"
          class="ec-acl-chip"
          :class="{ 'ec-acl-chip--on': isSelected(section.name, library.id) }"
          :disabled="props.disabled"
          @click="toggle(section.name, library.id)"
        >
          <VIcon
            :icon="isSelected(section.name, library.id) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'"
            size="14"
          />
          <span class="ec-acl-chip-text">{{ library.name || library.id }}</span>
        </button>
        <div v-if="section.error" class="text-caption text-error ec-acl-error">{{ section.error }}</div>
        <div v-else-if="!section.libraries.length" class="text-caption text-medium-emphasis ec-acl-error">
          该服务器暂无媒体库
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* 非 scoped（.ec-acl 命名空间隔离）：自动封面目标媒体库选择。
   裸 :deep() 会被构建丢弃（v1.4.6 教训），一律走 .ec-acl 前缀；底色与
   「预览 / 模板预设」tonal 卡片同配方，选中 chips 用品牌色 tonal 填充。 */
.ec-acl {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ec-acl-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.ec-acl-title {
  display: flex;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
}
.ec-acl-section {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.05);
  overflow: hidden;
}
.ec-acl-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  min-height: 44px;
  cursor: pointer;
}
.ec-acl-caret {
  transition: transform 0.15s;
}
.ec-acl-caret--closed {
  transform: rotate(-90deg);
}
.ec-acl-name {
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ec-acl-count {
  margin-left: auto;
  margin-right: 8px;
  font-size: 12px;
  opacity: 0.65;
}
.ec-acl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 6px;
  padding: 4px 10px 10px;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.ec-acl-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 5px 10px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  color: rgb(var(--v-theme-on-surface));
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.ec-acl-chip:hover {
  border-color: rgba(var(--v-theme-primary), 0.55);
}
.ec-acl-chip--on {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.16);
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
}
.ec-acl-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ec-acl-chip-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ec-acl-error {
  grid-column: 1 / -1;
}
@media (max-width: 760px) {
  .ec-acl-grid {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  }
}
</style>
