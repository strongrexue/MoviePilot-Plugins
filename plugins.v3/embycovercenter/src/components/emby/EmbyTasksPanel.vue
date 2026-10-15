<script setup>
import { computed, onMounted } from 'vue'
import { useEmbyTasks, TRIGGER_TYPE_OPTIONS, WEEK_DAY_OPTIONS } from './useEmbyTasks'

/**
 * Emby 计划任务中心面板。
 *
 * 列表按分类分组、运行中置顶；支持编辑触发器、立即运行、停止。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  servers: { type: Array, default: () => [] },
})
const emit = defineEmits(['notify'])

const tasks = useEmbyTasks({
  api: () => props.api,
  pluginId: () => props.pluginId,
  notify: (message, ok) => emit('notify', message, ok),
})

const { state, dialog } = tasks
const { load, run, stop, openTriggers, addDraft, removeDraft, closeDialog, saveTriggers } = tasks

const serverItems = computed(() =>
  props.servers.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
)

function statusColor(task) {
  if (task.status_type === 'running') return 'primary'
  if (task.status_type === 'success') return 'success'
  if (task.status_type === 'error') return 'error'
  if (task.status_type === 'cancelled') return 'warning'
  return 'grey'
}

onMounted(load)
</script>

<template>
  <VCard variant="tonal" class="ec-tasks">
    <VCardItem class="ec-tasks-head">
      <VCardTitle class="text-subtitle-1">
        Emby 任务中心
        <VChip v-if="state.runningCount" color="primary" variant="tonal" size="small" label class="ms-2">
          {{ state.runningCount }} 运行中
        </VChip>
      </VCardTitle>
      <VCardSubtitle v-if="state.updatedAt" class="text-caption">
        更新于 {{ state.updatedAt }}
      </VCardSubtitle>
      <template #append>
        <div class="ec-actions">
          <VSelect
            v-if="serverItems.length > 1"
            v-model="state.server"
            :items="serverItems"
            density="compact"
            variant="outlined"
            hide-details
            class="ec-server"
            @update:model-value="load"
          />
          <VBtn size="small" variant="text" :loading="state.loading" @click="load">刷新</VBtn>
        </div>
      </template>
    </VCardItem>
    <VProgressLinear v-if="state.loading" indeterminate color="primary" height="2" />
    <VCardText>
      <VAlert v-if="state.error" type="warning" variant="tonal" density="compact" class="mb-2">
        {{ state.error }}
      </VAlert>
      <div v-if="!state.categories.length && !state.error" class="text-caption text-medium-emphasis">
        暂无任务数据。
      </div>

      <div v-for="category in state.categories" :key="category.name" class="ec-group">
        <div class="ec-group-head">
          <VIcon icon="mdi-view-list-outline" size="16" />
          <span class="ec-group-name">{{ category.name }}</span>
          <VChip size="x-small" variant="tonal" color="grey" label>{{ category.count }}</VChip>
        </div>
        <div class="ec-task-list">
          <div v-for="task in category.tasks" :key="task.id" class="ec-task" :class="{ 'ec-task--running': task.is_running }">
            <VChip :color="statusColor(task)" variant="tonal" size="small" label class="ec-task-chip">
              {{ task.status_label }}
            </VChip>
            <div class="ec-task-main">
              <div class="ec-task-title">{{ task.name }}</div>
              <div class="ec-task-meta">
                {{ task.trigger_summary }}
                <span v-if="task.last_run_time"> · 上次 {{ task.last_run_time }}</span>
              </div>
            </div>
            <div class="ec-task-side">
              <span v-if="task.is_running" class="ec-progress">{{ task.progress }}%</span>
              <VBtn
                size="small"
                icon="mdi-play"
                variant="text"
                rounded
                title="立即运行"
                :disabled="!!state.actionId && state.actionId !== task.id"
                :loading="state.actionId === task.id"
                @click="run(task.id)"
              />
              <VBtn
                v-if="task.is_running"
                size="small"
                icon="mdi-stop"
                color="error"
                variant="text"
                rounded
                title="停止"
                :disabled="!!state.actionId && state.actionId !== task.id"
                :loading="state.actionId === task.id"
                @click="stop(task.id)"
              />
              <VBtn
                size="small"
                icon="mdi-clock-edit-outline"
                variant="text"
                rounded
                title="编辑触发器"
                :disabled="!!state.actionId"
                @click="openTriggers(task)"
              />
            </div>
            <VProgressLinear
              v-if="task.is_running"
              :model-value="task.progress"
              height="3"
              color="primary"
              rounded
              class="ec-task-bar"
            />
          </div>
        </div>
      </div>
    </VCardText>

    <VDialog v-model="dialog.visible" max-width="760" :persistent="dialog.saving">
      <VCard>
        <VCardItem>
          <VCardTitle class="text-subtitle-1">触发器 · {{ dialog.taskName }}</VCardTitle>
          <template #append>
            <VBtn size="small" icon variant="text" :disabled="dialog.saving" @click="closeDialog">
              <VIcon icon="mdi-close" size="18" />
            </VBtn>
          </template>
        </VCardItem>
        <VDivider />
        <VCardText class="ec-trigger-body">
          <VProgressLinear v-if="dialog.loading" indeterminate color="primary" height="2" />
          <div v-for="(draft, index) in dialog.triggers" :key="index" class="ec-trigger-row">
            <VSelect
              v-model="draft.type"
              :items="TRIGGER_TYPE_OPTIONS"
              label="类型"
              density="compact"
              variant="outlined"
              hide-details
            />
            <template v-if="draft.type === 'DailyTrigger' || draft.type === 'WeeklyTrigger'">
              <VTextField
                v-model="draft.time"
                label="时间 HH:MM"
                density="compact"
                variant="outlined"
                hide-details
              />
            </template>
            <VSelect
              v-if="draft.type === 'WeeklyTrigger'"
              v-model="draft.day_of_week"
              :items="WEEK_DAY_OPTIONS"
              label="星期"
              density="compact"
              variant="outlined"
              hide-details
            />
            <VTextField
              v-if="draft.type === 'IntervalTrigger'"
              v-model="draft.interval_hours"
              type="number"
              label="间隔（小时）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <VTextField
              v-model="draft.max_runtime_hours"
              type="number"
              label="最长运行（小时，可空）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <VBtn size="small" icon variant="text" :disabled="dialog.saving" @click="removeDraft(index)">
              <VIcon icon="mdi-delete-outline" size="18" />
            </VBtn>
          </div>
          <VBtn size="small" variant="text" prepend-icon="mdi-plus" :disabled="dialog.saving" @click="addDraft">
            添加计划
          </VBtn>
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" :disabled="dialog.saving" @click="closeDialog">取消</VBtn>
          <VBtn color="primary" variant="flat" :loading="dialog.saving" :disabled="dialog.saving" @click="saveTriggers">
            保存触发器
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VCard>
</template>

<style scoped>
.ec-tasks {
  grid-column: 1 / -1;
  min-width: 0;
}
.ec-tasks-head {
  padding-top: 12px;
}
.ec-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.ec-server {
  max-width: 220px;
}
.ec-group {
  margin-bottom: 14px;
}
.ec-group-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 4px 0 8px;
  font-size: 13px;
  font-weight: 600;
  opacity: 0.85;
}
.ec-task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ec-task {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgba(var(--v-theme-on-surface), 0.03);
  overflow: hidden;
  transition: border-color 0.15s, background 0.15s;
}
.ec-task:hover {
  border-color: rgba(var(--v-theme-primary), 0.45);
}
.ec-task--running {
  border-color: rgba(var(--v-theme-primary), 0.55);
  background: rgba(var(--v-theme-primary), 0.06);
}
.ec-task-chip {
  flex: 0 0 auto;
}
.ec-task-main {
  min-width: 0;
  flex: 1;
}
.ec-task-title {
  font-size: 13.5px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ec-task-meta {
  font-size: 12px;
  opacity: 0.7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ec-task-side {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 0 0 auto;
}
.ec-progress {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  margin-right: 6px;
  opacity: 0.8;
}
.ec-task-bar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 0;
}
.ec-trigger-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: min(60vh, 520px);
  overflow-y: auto;
}
.ec-trigger-row {
  display: grid;
  grid-template-columns: 140px 1fr 1fr auto;
  gap: 8px;
  align-items: center;
}
@media (max-width: 760px) {
  .ec-trigger-row {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
