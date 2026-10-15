import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { p as postPluginApi, u as unwrap, a as getPluginApi, _ as _export_sfc } from './_plugin-vue_export-helper-C6TXstWj.js';
import { F as FRONTEND_VERSION } from './version-uhC7d-gd.js';

/**
 * Emby 计划任务中心的前端状态与动作。
 *
 * 数据来自插件 API `/emby_tasks`（已归一化：中文标签、触发器摘要、运行状态），
 * 本模块只负责轮询、操作与触发器草稿管理，不做本地推测。
 */
const {reactive} = await importShared('vue');

const TRIGGER_TYPE_OPTIONS = [
  { value: 'DailyTrigger', label: '每天' },
  { value: 'WeeklyTrigger', label: '每周' },
  { value: 'IntervalTrigger', label: '按间隔' },
  { value: 'StartupTrigger', label: '服务器启动时' },
];

const WEEK_DAY_OPTIONS = [
  { value: 'Monday', label: '周一' },
  { value: 'Tuesday', label: '周二' },
  { value: 'Wednesday', label: '周三' },
  { value: 'Thursday', label: '周四' },
  { value: 'Friday', label: '周五' },
  { value: 'Saturday', label: '周六' },
  { value: 'Sunday', label: '周日' },
];

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

function useEmbyTasks({ api, pluginId, notify }) {
  const state = reactive({
    loading: false,
    actionId: '',
    server: '',
    categories: [],
    runningCount: 0,
    updatedAt: '',
    error: '',
  });

  const dialog = reactive({
    visible: false,
    loading: false,
    saving: false,
    taskId: '',
    taskName: '',
    triggers: [],
  });

  function report(message, ok = true) {
    if (typeof notify === 'function') notify(message, ok);
  }

  async function load() {
    if (state.loading) return
    state.loading = true;
    state.error = '';
    try {
      const target = String(pluginId() || '');
      const query = state.server ? `?server=${encodeURIComponent(state.server)}` : '';
      const data = unwrap(await getPluginApi(api(), target, `emby_tasks${query}`)) || {};
      state.categories = Array.isArray(data.categories) ? data.categories : [];
      state.runningCount = Number(data.running_count || 0);
      state.updatedAt = String(data.updated_at || '');
    } catch (error) {
      state.categories = [];
      state.error = error?.message || 'Emby 任务读取失败';
    } finally {
      state.loading = false;
    }
  }

  async function action(taskId, verb, okMessage) {
    if (state.actionId) return
    state.actionId = taskId;
    try {
      const body = { server: state.server };
      await postPluginApi(api(), pluginId(), `emby_tasks/${encodeURIComponent(taskId)}/${verb}`, body);
      report(okMessage);
      await load();
    } catch (error) {
      report(error?.message || '操作失败', false);
    } finally {
      state.actionId = '';
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
    dialog.loading = true;
    dialog.taskId = task.id;
    dialog.taskName = task.name;
    dialog.triggers = [];
    dialog.visible = true;
    try {
      const query = state.server ? `?server=${encodeURIComponent(state.server)}` : '';
      const data = unwrap(
        await getPluginApi(api(), pluginId(), `emby_tasks/${encodeURIComponent(task.id)}${query}`),
      ) || {};
      const triggers = Array.isArray(data.triggers) ? data.triggers : [];
      dialog.triggers = triggers.map(draftFromTrigger);
      if (!dialog.triggers.length) dialog.triggers = [defaultDraft()];
    } catch (error) {
      dialog.triggers = [defaultDraft()];
      report(error?.message || '触发器读取失败', false);
    } finally {
      dialog.loading = false;
    }
  }

  function addDraft() {
    dialog.triggers.push(defaultDraft());
  }

  function removeDraft(index) {
    dialog.triggers.splice(index, 1);
    if (!dialog.triggers.length) dialog.triggers.push(defaultDraft());
  }

  function closeDialog() {
    dialog.visible = false;
    dialog.triggers = [];
  }

  async function saveTriggers() {
    if (dialog.saving) return
    dialog.saving = true;
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
      };
      await postPluginApi(
        api(),
        pluginId(),
        `emby_tasks/${encodeURIComponent(dialog.taskId)}/triggers`,
        body,
      );
      report('触发器已保存');
      closeDialog();
      await load();
    } catch (error) {
      report(error?.message || '触发器保存失败', false);
    } finally {
      dialog.saving = false;
    }
  }

  return { state, dialog, load, run, stop, openTriggers, addDraft, removeDraft, closeDialog, saveTriggers }
}

const {unref:_unref$1,toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,createVNode:_createVNode$1,createElementVNode:_createElementVNode$1,createElementBlock:_createElementBlock$1,renderList:_renderList$1,Fragment:_Fragment$1} = await importShared('vue');


const _hoisted_1$1 = { class: "ec-actions" };
const _hoisted_2$1 = {
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_3$1 = { class: "ec-group-title" };
const _hoisted_4$1 = { class: "ec-task-main" };
const _hoisted_5 = { class: "ec-task-title" };
const _hoisted_6 = { class: "ec-task-meta" };
const _hoisted_7 = { key: 0 };
const _hoisted_8 = { class: "ec-task-side" };
const _hoisted_9 = {
  key: 0,
  class: "ec-progress"
};

const {computed: computed$1,onMounted: onMounted$1} = await importShared('vue');

/**
 * Emby 计划任务中心面板。
 *
 * 列表按分类分组、运行中置顶；支持编辑触发器、立即运行、停止。
 */

const _sfc_main$1 = {
  __name: 'EmbyTasksPanel',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  servers: { type: Array, default: () => [] },
},
  emits: ['notify'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const tasks = useEmbyTasks({
  api: () => props.api,
  pluginId: () => props.pluginId,
  notify: (message, ok) => emit('notify', message, ok),
});

const { state, dialog } = tasks;
const { load, run, stop, openTriggers, addDraft, removeDraft, closeDialog, saveTriggers } = tasks;

const serverItems = computed$1(() =>
  props.servers.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
);

function statusColor(task) {
  if (task.status_type === 'running') return 'primary'
  if (task.status_type === 'success') return 'success'
  if (task.status_type === 'error') return 'error'
  if (task.status_type === 'cancelled') return 'warning'
  return 'grey'
}

onMounted$1(load);

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VCardTitle = _resolveComponent$1("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$1("VCardSubtitle");
  const _component_VSelect = _resolveComponent$1("VSelect");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VCardItem = _resolveComponent$1("VCardItem");
  const _component_VProgressLinear = _resolveComponent$1("VProgressLinear");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VDivider = _resolveComponent$1("VDivider");
  const _component_VTextField = _resolveComponent$1("VTextField");
  const _component_VSpacer = _resolveComponent$1("VSpacer");
  const _component_VCardActions = _resolveComponent$1("VCardActions");
  const _component_VCard = _resolveComponent$1("VCard");
  const _component_VDialog = _resolveComponent$1("VDialog");

  return (_openBlock$1(), _createBlock$1(_component_VCard, {
    variant: "tonal",
    class: "ec-tasks"
  }, {
    default: _withCtx$1(() => [
      _createVNode$1(_component_VCardItem, { class: "ec-tasks-head" }, {
        append: _withCtx$1(() => [
          _createElementVNode$1("div", _hoisted_1$1, [
            (serverItems.value.length > 1)
              ? (_openBlock$1(), _createBlock$1(_component_VSelect, {
                  key: 0,
                  modelValue: _unref$1(state).server,
                  "onUpdate:modelValue": [
                    _cache[0] || (_cache[0] = $event => ((_unref$1(state).server) = $event)),
                    _unref$1(load)
                  ],
                  items: serverItems.value,
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  class: "ec-server"
                }, null, 8, ["modelValue", "items", "onUpdate:modelValue"]))
              : _createCommentVNode$1("", true),
            _createVNode$1(_component_VBtn, {
              size: "small",
              variant: "text",
              loading: _unref$1(state).loading,
              onClick: _unref$1(load)
            }, {
              default: _withCtx$1(() => [...(_cache[3] || (_cache[3] = [
                _createTextVNode$1("刷新", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "onClick"])
          ])
        ]),
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCardTitle, { class: "text-subtitle-1" }, {
            default: _withCtx$1(() => [
              _cache[2] || (_cache[2] = _createTextVNode$1(" Emby 任务中心 ", -1)),
              (_unref$1(state).runningCount)
                ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                    key: 0,
                    color: "primary",
                    variant: "tonal",
                    size: "small",
                    label: "",
                    class: "ms-2"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(_unref$1(state).runningCount) + " 运行中 ", 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$1("", true)
            ]),
            _: 1
          }),
          (_unref$1(state).updatedAt)
            ? (_openBlock$1(), _createBlock$1(_component_VCardSubtitle, {
                key: 0,
                class: "text-caption"
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(" 更新于 " + _toDisplayString$1(_unref$1(state).updatedAt), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode$1("", true)
        ]),
        _: 1
      }),
      (_unref$1(state).loading)
        ? (_openBlock$1(), _createBlock$1(_component_VProgressLinear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            height: "2"
          }))
        : _createCommentVNode$1("", true),
      _createVNode$1(_component_VCardText, null, {
        default: _withCtx$1(() => [
          (_unref$1(state).error)
            ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "mb-2"
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(_toDisplayString$1(_unref$1(state).error), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode$1("", true),
          (!_unref$1(state).categories.length && !_unref$1(state).error)
            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_2$1, " 暂无任务数据。 "))
            : _createCommentVNode$1("", true),
          (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(_unref$1(state).categories, (category) => {
            return (_openBlock$1(), _createElementBlock$1("div", {
              key: category.name,
              class: "ec-group"
            }, [
              _createElementVNode$1("div", _hoisted_3$1, _toDisplayString$1(category.name) + "（" + _toDisplayString$1(category.count) + "）", 1),
              (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(category.tasks, (task) => {
                return (_openBlock$1(), _createElementBlock$1("div", {
                  key: task.id,
                  class: "ec-task"
                }, [
                  _createElementVNode$1("div", _hoisted_4$1, [
                    _createElementVNode$1("div", _hoisted_5, _toDisplayString$1(task.name), 1),
                    _createElementVNode$1("div", _hoisted_6, [
                      _createTextVNode$1(_toDisplayString$1(task.trigger_summary) + " ", 1),
                      (task.last_run_time)
                        ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_7, " · 上次 " + _toDisplayString$1(task.last_run_time), 1))
                        : _createCommentVNode$1("", true)
                    ])
                  ]),
                  _createElementVNode$1("div", _hoisted_8, [
                    _createVNode$1(_component_VChip, {
                      color: statusColor(task),
                      variant: "tonal",
                      size: "x-small",
                      label: ""
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(task.status_label), 1)
                      ]),
                      _: 2
                    }, 1032, ["color"]),
                    (task.is_running)
                      ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_9, _toDisplayString$1(task.progress) + "%", 1))
                      : _createCommentVNode$1("", true),
                    _createVNode$1(_component_VBtn, {
                      size: "x-small",
                      variant: "text",
                      loading: _unref$1(state).actionId === task.id,
                      onClick: $event => (_unref$1(run)(task.id))
                    }, {
                      default: _withCtx$1(() => [...(_cache[4] || (_cache[4] = [
                        _createTextVNode$1(" 运行 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "onClick"]),
                    (task.is_running)
                      ? (_openBlock$1(), _createBlock$1(_component_VBtn, {
                          key: 1,
                          size: "x-small",
                          variant: "text",
                          loading: _unref$1(state).actionId === task.id,
                          onClick: $event => (_unref$1(stop)(task.id))
                        }, {
                          default: _withCtx$1(() => [...(_cache[5] || (_cache[5] = [
                            _createTextVNode$1(" 停止 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["loading", "onClick"]))
                      : _createCommentVNode$1("", true),
                    _createVNode$1(_component_VBtn, {
                      size: "x-small",
                      variant: "text",
                      onClick: $event => (_unref$1(openTriggers)(task))
                    }, {
                      default: _withCtx$1(() => [...(_cache[6] || (_cache[6] = [
                        _createTextVNode$1("触发器", -1)
                      ]))]),
                      _: 1
                    }, 8, ["onClick"])
                  ])
                ]))
              }), 128))
            ]))
          }), 128))
        ]),
        _: 1
      }),
      _createVNode$1(_component_VDialog, {
        modelValue: _unref$1(dialog).visible,
        "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((_unref$1(dialog).visible) = $event)),
        "max-width": "760",
        persistent: _unref$1(dialog).saving
      }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCard, null, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VCardItem, null, {
                append: _withCtx$1(() => [
                  _createVNode$1(_component_VBtn, {
                    size: "small",
                    icon: "",
                    variant: "text",
                    disabled: _unref$1(dialog).saving,
                    onClick: _unref$1(closeDialog)
                  }, {
                    default: _withCtx$1(() => [
                      _createVNode$1(_component_VIcon, {
                        icon: "mdi-close",
                        size: "18"
                      })
                    ]),
                    _: 1
                  }, 8, ["disabled", "onClick"])
                ]),
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VCardTitle, { class: "text-subtitle-1" }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1("触发器 · " + _toDisplayString$1(_unref$1(dialog).taskName), 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode$1(_component_VDivider),
              _createVNode$1(_component_VCardText, { class: "ec-trigger-body" }, {
                default: _withCtx$1(() => [
                  (_unref$1(dialog).loading)
                    ? (_openBlock$1(), _createBlock$1(_component_VProgressLinear, {
                        key: 0,
                        indeterminate: "",
                        color: "primary",
                        height: "2"
                      }))
                    : _createCommentVNode$1("", true),
                  (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(_unref$1(dialog).triggers, (draft, index) => {
                    return (_openBlock$1(), _createElementBlock$1("div", {
                      key: index,
                      class: "ec-trigger-row"
                    }, [
                      _createVNode$1(_component_VSelect, {
                        modelValue: draft.type,
                        "onUpdate:modelValue": $event => ((draft.type) = $event),
                        items: _unref$1(TRIGGER_TYPE_OPTIONS),
                        label: "类型",
                        density: "compact",
                        variant: "outlined",
                        "hide-details": ""
                      }, null, 8, ["modelValue", "onUpdate:modelValue", "items"]),
                      (draft.type === 'DailyTrigger' || draft.type === 'WeeklyTrigger')
                        ? (_openBlock$1(), _createBlock$1(_component_VTextField, {
                            key: 0,
                            modelValue: draft.time,
                            "onUpdate:modelValue": $event => ((draft.time) = $event),
                            label: "时间 HH:MM",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                        : _createCommentVNode$1("", true),
                      (draft.type === 'WeeklyTrigger')
                        ? (_openBlock$1(), _createBlock$1(_component_VSelect, {
                            key: 1,
                            modelValue: draft.day_of_week,
                            "onUpdate:modelValue": $event => ((draft.day_of_week) = $event),
                            items: _unref$1(WEEK_DAY_OPTIONS),
                            label: "星期",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue", "items"]))
                        : _createCommentVNode$1("", true),
                      (draft.type === 'IntervalTrigger')
                        ? (_openBlock$1(), _createBlock$1(_component_VTextField, {
                            key: 2,
                            modelValue: draft.interval_hours,
                            "onUpdate:modelValue": $event => ((draft.interval_hours) = $event),
                            type: "number",
                            label: "间隔（小时）",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                        : _createCommentVNode$1("", true),
                      _createVNode$1(_component_VTextField, {
                        modelValue: draft.max_runtime_hours,
                        "onUpdate:modelValue": $event => ((draft.max_runtime_hours) = $event),
                        type: "number",
                        label: "最长运行（小时，可空）",
                        density: "compact",
                        variant: "outlined",
                        "hide-details": ""
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _createVNode$1(_component_VBtn, {
                        size: "small",
                        icon: "",
                        variant: "text",
                        disabled: _unref$1(dialog).saving,
                        onClick: $event => (_unref$1(removeDraft)(index))
                      }, {
                        default: _withCtx$1(() => [
                          _createVNode$1(_component_VIcon, {
                            icon: "mdi-delete-outline",
                            size: "18"
                          })
                        ]),
                        _: 1
                      }, 8, ["disabled", "onClick"])
                    ]))
                  }), 128)),
                  _createVNode$1(_component_VBtn, {
                    size: "small",
                    variant: "text",
                    "prepend-icon": "mdi-plus",
                    disabled: _unref$1(dialog).saving,
                    onClick: _unref$1(addDraft)
                  }, {
                    default: _withCtx$1(() => [...(_cache[7] || (_cache[7] = [
                      _createTextVNode$1(" 添加计划 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "onClick"])
                ]),
                _: 1
              }),
              _createVNode$1(_component_VDivider),
              _createVNode$1(_component_VCardActions, null, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VSpacer),
                  _createVNode$1(_component_VBtn, {
                    variant: "text",
                    disabled: _unref$1(dialog).saving,
                    onClick: _unref$1(closeDialog)
                  }, {
                    default: _withCtx$1(() => [...(_cache[8] || (_cache[8] = [
                      _createTextVNode$1("取消", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "onClick"]),
                  _createVNode$1(_component_VBtn, {
                    color: "primary",
                    variant: "flat",
                    loading: _unref$1(dialog).saving,
                    disabled: _unref$1(dialog).saving,
                    onClick: _unref$1(saveTriggers)
                  }, {
                    default: _withCtx$1(() => [...(_cache[9] || (_cache[9] = [
                      _createTextVNode$1(" 保存触发器 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading", "disabled", "onClick"])
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue", "persistent"])
    ]),
    _: 1
  }))
}
}

};
const EmbyTasksPanel = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-9e46884c"]]);

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,unref:_unref,normalizeClass:_normalizeClass,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment} = await importShared('vue');


const _hoisted_1 = { class: "ec-row" };
const _hoisted_2 = { class: "ec-row" };
const _hoisted_3 = { class: "ec-row" };
const _hoisted_4 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};

const {computed,onMounted,ref} = await importShared('vue');

/**
 * 插件详情页 / 侧栏整页内容。
 *
 * 展示插件与媒体服务器状态，并提供连通性测试与设置入口。
 */

const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  appPage: { type: Boolean, default: false },
},
  emits: ['switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const loading = ref(false);
const status = ref({});
const loadError = ref('');
const actionMessage = ref('');
const actionOk = ref(true);

const backendVersion = computed(() => String(status.value.plugin_version || ''));
const versionMismatched = computed(
  () => !!backendVersion.value && backendVersion.value !== FRONTEND_VERSION,
);
const servers = computed(() => (Array.isArray(status.value.servers) ? status.value.servers : []));

async function load() {
  if (loading.value) return
  loading.value = true;
  loadError.value = '';
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status')) || {};
  } catch (error) {
    loadError.value = error?.message || '状态读取失败';
  } finally {
    loading.value = false;
  }
}

async function ping() {
  actionMessage.value = '';
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'ping')) || {};
    actionOk.value = true;
    actionMessage.value = `连通正常 · 后端 v${data.plugin_version || backendVersion.value || '?'}`;
  } catch (error) {
    actionOk.value = false;
    actionMessage.value = error?.message || '连通性测试失败';
  }
}

function onNotify(message, ok = true) {
  actionOk.value = ok !== false;
  actionMessage.value = message || '';
}

onMounted(load);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: _normalizeClass(["ec-page", { 'ec-page--app': props.appPage }])
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VToolbar, {
        density: "comfortable",
        class: "ec-toolbar"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            rounded: "lg",
            size: "32",
            class: "ms-3 me-2"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-image-multiple-outline" })
            ]),
            _: 1
          }),
          _cache[5] || (_cache[5] = _createElementVNode("div", { class: "ec-heading" }, [
            _createElementVNode("div", { class: "text-h6" }, "胖虎封面中心"),
            _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "Emby 媒体库封面生成与任务中心")
          ], -1)),
          _createVNode(_component_VSpacer),
          _createVNode(_component_VBtn, {
            size: "small",
            variant: "text",
            loading: loading.value,
            onClick: load
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: "mdi-refresh",
                size: "18"
              }),
              _cache[2] || (_cache[2] = _createElementVNode("span", { class: "ec-label" }, "刷新", -1))
            ]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_VBtn, {
            size: "small",
            variant: "text",
            onClick: ping
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: "mdi-lan-connect",
                size: "18"
              }),
              _cache[3] || (_cache[3] = _createElementVNode("span", { class: "ec-label" }, "连通测试", -1))
            ]),
            _: 1
          }),
          _createVNode(_component_VBtn, {
            size: "small",
            variant: "text",
            onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: "mdi-cog-outline",
                size: "18"
              }),
              _cache[4] || (_cache[4] = _createElementVNode("span", { class: "ec-label" }, "设置", -1))
            ]),
            _: 1
          }),
          (!props.appPage)
            ? (_openBlock(), _createBlock(_component_VBtn, {
                key: 0,
                size: "small",
                icon: "",
                variant: "text",
                onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-close",
                    size: "18"
                  })
                ]),
                _: 1
              }))
            : _createCommentVNode("", true)
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      (loading.value)
        ? (_openBlock(), _createBlock(_component_VProgressLinear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            height: "2"
          }))
        : _createCommentVNode("", true),
      _createVNode(_component_VCardText, { class: "ec-flow" }, {
        default: _withCtx(() => [
          (loadError.value)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "ec-span"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(loadError.value) + " ", 1),
                  _createVNode(_component_VBtn, {
                    size: "x-small",
                    variant: "text",
                    class: "text-none",
                    onClick: load
                  }, {
                    default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                      _createTextVNode("重试", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          (versionMismatched.value)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 1,
                type: "info",
                variant: "tonal",
                density: "compact",
                class: "ec-span"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(" 前端组件 v" + _toDisplayString(_unref(FRONTEND_VERSION)) + " ≠ 后端 v" + _toDisplayString(backendVersion.value) + "：浏览器仍在使用旧联邦组件， 请按 Ctrl + Shift + R 硬刷新；若仍不一致，说明插件未真正更新。 ", 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          (actionMessage.value)
            ? (_openBlock(), _createElementBlock("div", {
                key: 2,
                class: _normalizeClass(["ec-span", actionOk.value ? 'text-success' : 'text-error'])
              }, _toDisplayString(actionMessage.value), 3))
            : _createCommentVNode("", true),
          _createVNode(_component_VCard, {
            variant: "tonal",
            class: "ec-card"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardItem, null, {
                default: _withCtx(() => [
                  _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                    default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                      _createTextVNode("运行状态", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VCardText, { class: "ec-kv" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_1, [
                    _cache[8] || (_cache[8] = _createElementVNode("span", null, "插件版本", -1)),
                    _createElementVNode("b", null, "v" + _toDisplayString(backendVersion.value || '—'), 1)
                  ]),
                  _createElementVNode("div", _hoisted_2, [
                    _cache[9] || (_cache[9] = _createElementVNode("span", null, "启用状态", -1)),
                    _createElementVNode("b", null, _toDisplayString(status.value.enabled ? '已启用' : '已停用'), 1)
                  ]),
                  _createElementVNode("div", _hoisted_3, [
                    _cache[10] || (_cache[10] = _createElementVNode("span", null, "媒体服务器", -1)),
                    _createElementVNode("b", null, _toDisplayString(servers.value.length), 1)
                  ])
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode(_component_VCard, {
            variant: "tonal",
            class: "ec-card"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardItem, null, {
                default: _withCtx(() => [
                  _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                    default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
                      _createTextVNode("媒体服务器", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VCardText, null, {
                default: _withCtx(() => [
                  (!servers.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_4, " 未发现已启用的媒体服务器，请在 MoviePilot「设置 · 媒体服务器」中配置 Emby / Jellyfin。 "))
                    : _createCommentVNode("", true),
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(servers.value, (server) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: server.name,
                      class: "ec-row"
                    }, [
                      _createElementVNode("span", null, _toDisplayString(server.name), 1),
                      _createElementVNode("b", {
                        class: _normalizeClass(server.active ? 'text-success' : 'text-warning')
                      }, _toDisplayString(server.type || '—') + " · " + _toDisplayString(server.active ? '已连接' : '未连接'), 3)
                    ]))
                  }), 128))
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode(EmbyTasksPanel, {
            api: props.api,
            "plugin-id": props.pluginId,
            servers: servers.value,
            onNotify: onNotify
          }, null, 8, ["api", "plugin-id", "servers"])
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["class"]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-efc183ba"]]);

export { Page as default };
