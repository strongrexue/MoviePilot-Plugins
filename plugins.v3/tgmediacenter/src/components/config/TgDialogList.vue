<script setup>
import { computed, ref } from 'vue'
import { copyText } from '../clipboard'

/**
 * 对话（群组 / 频道 / 机器人 / 用户）列表。
 *
 * 参照 MA 的「群组/联系人列表」：可搜索、按类型筛选、显示 ID 并可一键复制，
 * 便于配置资源监控与转发规则时挑选频道。
 */
const props = defineProps({
  dialogs: { type: Array, default: () => [] },
  updatedAt: { type: String, default: '' },
  // 每屏最多渲染条数，避免上千条一次全渲染
  pageSize: { type: Number, default: 60 },
})

const keyword = ref('')
const typeFilter = ref('全部')
const limit = ref(props.pageSize)
const toast = ref('')

const TYPE_ORDER = ['频道', '群组', '机器人', '用户', '其他']

const TYPE_COLOR = {
  频道: 'primary',
  群组: 'success',
  机器人: 'info',
  用户: 'warning',
  其他: 'default',
}

const typeOptions = computed(() => {
  const present = new Set((props.dialogs || []).map(item => item?.type).filter(Boolean))
  const ordered = TYPE_ORDER.filter(type => present.has(type))
  // 出现未知类型时也列出来，避免"看不见就是没有"
  for (const type of present) {
    if (!ordered.includes(type)) ordered.push(type)
  }
  return ['全部', ...ordered]
})

const counts = computed(() => {
  const result = {}
  for (const item of props.dialogs || []) {
    const type = item?.type || '其他'
    result[type] = (result[type] || 0) + 1
  }
  return result
})

const filtered = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  return (props.dialogs || []).filter(item => {
    if (typeFilter.value !== '全部' && (item?.type || '') !== typeFilter.value) return false
    if (!key) return true
    return (
      String(item?.name || '').toLowerCase().includes(key)
      || String(item?.username || '').toLowerCase().includes(key)
      || String(item?.id ?? '').includes(key)
    )
  })
})

const visible = computed(() => filtered.value.slice(0, limit.value))
const hasMore = computed(() => filtered.value.length > visible.value.length)

function typeColor(type) {
  return TYPE_COLOR[type] || 'default'
}

async function revealId(item) {
  const text = String(item?.id ?? '')
  const ok = await copyText(text)
  toast.value = ok ? `已复制 ID：${text}` : `复制失败，请手动选择：${text}`
  window.setTimeout(() => {
    if (toast.value.startsWith('已复制')) toast.value = ''
  }, 2000)
}

function resetLimit() {
  limit.value = props.pageSize
}

function more() {
  limit.value += props.pageSize
}

function onFilterChange() {
  resetLimit()
}

function clearFilters() {
  keyword.value = ''
  typeFilter.value = '全部'
  resetLimit()
}
</script>

<template>
  <VCard flat class="tg-card">
    <VCardTitle class="tg-list-title">
      <span class="text-subtitle-2">群组 / 联系人列表</span>
      <VChip v-if="dialogs.length" size="x-small" variant="tonal" color="primary" label>
        共 {{ dialogs.length }} 个
      </VChip>
    </VCardTitle>
    <VCardText>
      <div class="tg-filters">
        <VTextField
          v-model="keyword"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          prepend-inner-icon="mdi-magnify"
          placeholder="按名称 / 用户名 / ID 搜索"
          class="tg-filter-key"
          @update:model-value="onFilterChange"
        />
        <VSelect
          v-model="typeFilter"
          :items="typeOptions"
          density="compact"
          variant="outlined"
          hide-details
          class="tg-filter-type"
          @update:model-value="onFilterChange"
        />
      </div>

      <div v-if="dialogs.length" class="tg-type-summary">
        <VChip
          v-for="(count, type) in counts"
          :key="type"
          size="x-small"
          variant="tonal"
          :color="typeColor(type)"
          label
        >{{ type }} {{ count }}</VChip>
        <span v-if="updatedAt" class="tg-updated">更新于 {{ updatedAt }}</span>
      </div>

      <VAlert
        v-if="toast"
        :type="toast.startsWith('已复制') ? 'success' : 'warning'"
        variant="tonal"
        density="compact"
        class="mt-3"
      >{{ toast }}</VAlert>

      <div v-if="!dialogs.length" class="tg-empty">
        暂无缓存。登录成功后点「刷新对话列表」拉取（首次可能较慢）。
      </div>

      <div v-else-if="!filtered.length" class="tg-empty">
        没有匹配的对话，试试其它关键词。
      </div>

      <VList v-else density="compact" class="tg-dialog-list">
        <VListItem
          v-for="item in visible"
          :key="`${item.type}-${item.id}`"
          class="tg-dialog-item"
          @click="revealId(item)"
        >
          <template #prepend>
            <VChip size="x-small" variant="tonal" :color="typeColor(item.type)" label class="tg-type-chip">
              {{ item.type }}
            </VChip>
          </template>
          <VListItemTitle class="tg-dialog-name">{{ item.name }}</VListItemTitle>
          <VListItemSubtitle class="tg-dialog-sub">
            <span v-if="item.username">@{{ item.username }} · </span>{{ item.id }}
          </VListItemSubtitle>
          <template #append>
            <VIcon icon="mdi-content-copy" size="16" class="tg-copy" title="复制 ID" />
          </template>
        </VListItem>
      </VList>

      <div v-if="hasMore" class="tg-more">
        <VBtn size="small" variant="text" @click="more">
          显示更多（还有 {{ filtered.length - visible.length }} 个）
        </VBtn>
      </div>
      <div v-else-if="filtered.length > pageSize" class="tg-more">
        <VBtn size="small" variant="text" @click="clearFilters">重置筛选</VBtn>
      </div>

      <div class="tg-hint">点击任意条目可复制其 ID（配置监控/转发规则时会用到）。</div>
    </VCardText>
  </VCard>
</template>

<style scoped>
.tg-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.tg-list-title { display: flex; align-items: center; gap: 8px; padding-bottom: 0; }
.tg-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.tg-filter-key { flex: 1 1 240px; min-width: 180px; }
.tg-filter-type { flex: 0 0 140px; max-width: 160px; }
.tg-type-summary { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.tg-updated { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); margin-left: auto; }
.tg-dialog-list {
  margin-top: 6px;
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.tg-dialog-item { cursor: pointer; }
.tg-type-chip { min-width: 44px; justify-content: center; }
.tg-dialog-name { font-size: 14px; }
.tg-dialog-sub { font-size: 12px; opacity: 0.7; }
.tg-copy { opacity: 0.4; }
.tg-dialog-item:hover .tg-copy { opacity: 1; }
.tg-empty {
  margin-top: 10px;
  padding: 18px 12px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.tg-more { margin-top: 6px; text-align: center; }
.tg-hint { margin-top: 10px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.6; }
</style>
