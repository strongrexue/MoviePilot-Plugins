/**
 * Emby 计划任务中心的前端状态与动作。
 *
 * 数据来自插件 API `/emby_tasks`（已归一化：中文标签、触发器摘要、运行状态），
 * 本模块只负责轮询、操作与触发器草稿管理，不做本地推测。
 */
import { reactive } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from '../api'

export const TRIGGER_TYPE_OPTIONS = [
  { value: 'DailyTrigger', label: '每天' },
  { value: 'WeeklyTrigger', label: '每周' },
  { value: 'IntervalTrigger', label: '按间隔' },
  { value: 'StartupTrigger', label: '服务器启动时' },
]

export const WEEK_DAY_OPTIONS = [
  { value: 'Monday', label: '周一' },
  { value: 'Tuesday', label: '周二' },
  { value: 'Wednesday', label: '周三' },
  { value: 'Thursday', label: '周四' },
  { value: 'Friday', label: '周五' },
  { value: 'Saturday', label: '周六' },
  { value: 'Sunday', label: '周日' },
]

function defaultDraft() {
  return {
    type: 'DailyTrigger',
    time: '00:00',
    day_of_week: 'Monday',
    interval_hours: 24,
    max_runtime_hours: '',
  }
}

function draftFromTrigger(trigger) {
  return {
    type: trigger?.type || 'DailyTrigger',
    time: trigger?.time || '00:00',
    day_of_week: trigger?.day_of_week || 'Monday',
    interval_hours: trigger?.interval_hours || 24,
    max_runtime_hours: trigger?.max_runtime_hours || '',
  }
}

export function useEmbyTasks({ api, pluginId, notify }) {
  const state = reactive({
    loading: false,
    actionId: '',
    server: '',
    categories: [],
    runningCount: 0,
    updatedAt: '',
    error: '',
  })

  const dialog = reactive({
    visible: false,
    loading: false,
    saving: false,
    taskId: '',
    taskName: '',
    triggers: [],
  })

  function report(message, ok = true) {
    if (typeof notify === 'function') notify(message, ok)
  }

  async function load() {
    if (state.loading) return
    state.loading = true
    state.error = ''
    try {
      const target = String(pluginId() || '')
      const query = state.server ? `?server=${encodeURIComponent(state.server)}` : ''
      const data = unwrap(await getPluginApi(api(), target, `emby_tasks${query}`)) || {}
      state.categories = Array.isArray(data.categories) ? data.categories : []
      state.runningCount = Number(data.running_count || 0)
      state.updatedAt = String(data.updated_at || '')
    } catch (error) {
      state.categories = []
      state.error = error?.message || 'Emby 任务读取失败'
    } finally {
      state.loading = false
    }
  }

  async function action(taskId, verb, okMessage) {
    if (state.actionId) return
    state.actionId = taskId
    try {
      const body = { server: state.server }
      await postPluginApi(api(), pluginId(), `emby_tasks/${encodeURIComponent(taskId)}/${verb}`, body)
      report(okMessage)
      await load()
    } catch (error) {
      report(error?.message || '操作失败', false)
    } finally {
      state.actionId = ''
    }
  }

  function run(taskId) {
    return action(taskId, 'run', '任务已启动')
  }

  function stop(taskId) {
    return action(taskId, 'stop', '停止命令已发送')
  }

  async function openTriggers(task) {
    if (dialog.loading) return
    dialog.loading = true
    dialog.taskId = task.id
    dialog.taskName = task.name
    dialog.triggers = []
    dialog.visible = true
    try {
      const query = state.server ? `?server=${encodeURIComponent(state.server)}` : ''
      const data = unwrap(
        await getPluginApi(api(), pluginId(), `emby_tasks/${encodeURIComponent(task.id)}${query}`),
      ) || {}
      const triggers = Array.isArray(data.triggers) ? data.triggers : []
      dialog.triggers = triggers.map(draftFromTrigger)
      if (!dialog.triggers.length) dialog.triggers = [defaultDraft()]
    } catch (error) {
      dialog.triggers = [defaultDraft()]
      report(error?.message || '触发器读取失败', false)
    } finally {
      dialog.loading = false
    }
  }

  function addDraft() {
    dialog.triggers.push(defaultDraft())
  }

  function removeDraft(index) {
    dialog.triggers.splice(index, 1)
    if (!dialog.triggers.length) dialog.triggers.push(defaultDraft())
  }

  function closeDialog() {
    dialog.visible = false
    dialog.triggers = []
  }

  async function saveTriggers() {
    if (dialog.saving) return
    dialog.saving = true
    try {
      const body = {
        server: state.server,
        triggers: dialog.triggers.map(item => ({
          type: item.type,
          time: item.time,
          day_of_week: item.day_of_week,
          interval_hours: Number(item.interval_hours || 0),
          max_runtime_hours: Number(item.max_runtime_hours || 0),
        })),
      }
      await postPluginApi(
        api(),
        pluginId(),
        `emby_tasks/${encodeURIComponent(dialog.taskId)}/triggers`,
        body,
      )
      report('触发器已保存')
      closeDialog()
      await load()
    } catch (error) {
      report(error?.message || '触发器保存失败', false)
    } finally {
      dialog.saving = false
    }
  }

  return { state, dialog, load, run, stop, openTriggers, addDraft, removeDraft, closeDialog, saveTriggers }
}
