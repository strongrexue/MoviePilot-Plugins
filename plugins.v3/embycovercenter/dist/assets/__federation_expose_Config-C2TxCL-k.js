import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as unwrap, a as getPluginApi, p as postPluginApi, _ as _export_sfc } from './_plugin-vue_export-helper-bD9RbwOy.js';
import { C as CoverDesignPane } from './CoverDesignPane-Be32Nmzd.js';

const {toDisplayString:_toDisplayString$2,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,createVNode:_createVNode$2,createElementVNode:_createElementVNode$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$2,renderList:_renderList$1,Fragment:_Fragment$1,normalizeClass:_normalizeClass,withModifiers:_withModifiers,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1$2 = { class: "ec-acl" };
const _hoisted_2$1 = { class: "ec-acl-head" };
const _hoisted_3$1 = { class: "ec-acl-title" };
const _hoisted_4$1 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_5 = ["onClick"];
const _hoisted_6 = { class: "ec-acl-name" };
const _hoisted_7 = { class: "ec-acl-count" };
const _hoisted_8 = { class: "ec-acl-grid" };
const _hoisted_9 = ["disabled", "onClick"];
const _hoisted_10 = { class: "ec-acl-chip-text" };
const _hoisted_11 = {
  key: 0,
  class: "text-caption text-error ec-acl-error"
};
const _hoisted_12 = {
  key: 1,
  class: "text-caption text-medium-emphasis ec-acl-error"
};

const {computed: computed$1,onMounted: onMounted$2,reactive: reactive$1,ref: ref$2,watch} = await importShared('vue');

/**
 * 自动封面目标媒体库选择（ChillPoster 风格）：
 * 按服务器分节可折叠，节头「全选」复选框 + 选中数徽标，媒体库为复选 chips
 * （选中 tonal 填充 + 品牌色描边）。v-model 为 { 服务器名: [库ID, ...] }；
 * 与「参与封面的服务器」的交集由后端执行时再取，本组件只管选择。
 */

const _sfc_main$2 = {
  __name: 'AutoCoverLibraries',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  modelValue: { type: Object, default: () => ({}) },
  servers: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
},
  emits: ['update:modelValue'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const sections = ref$2([]);
const loading = ref$2(false);
const open = reactive$1({});

const selectedTotal = computed$1(() =>
  Object.values(props.modelValue || {}).reduce(
    (sum, list) => sum + (Array.isArray(list) ? list.length : 0),
    0,
  ),
);

function isSelected(server, libraryId) {
  const list = props.modelValue?.[server];
  return Array.isArray(list) && list.includes(libraryId)
}

function countSelected(section) {
  const list = props.modelValue?.[section.name];
  return Array.isArray(list) ? list.length : 0
}

function allSelected(section) {
  return section.libraries.length > 0 && countSelected(section) >= section.libraries.length
}

function emitValue(next) {
  emit('update:modelValue', { ...next });
}

function toggle(server, libraryId) {
  if (props.disabled) return
  const current = props.modelValue?.[server];
  const list = Array.isArray(current) ? [...current] : [];
  const index = list.indexOf(libraryId);
  if (index >= 0) list.splice(index, 1);
  else list.push(libraryId);
  const next = { ...(props.modelValue || {}) };
  if (list.length) next[server] = list;
  else delete next[server];
  emitValue(next);
}

function toggleSection(section) {
  if (props.disabled) return
  const next = { ...(props.modelValue || {}) };
  if (allSelected(section)) delete next[section.name];
  else next[section.name] = section.libraries.map(library => library.id);
  emitValue(next);
}

function toggleOpen(name) {
  open[name] = !open[name];
}

async function loadAll() {
  if (loading.value) return
  if (!props.servers.length) {
    sections.value = [];
    return
  }
  loading.value = true;
  const results = await Promise.all(
    props.servers.map(async server => {
      try {
        const query = server.name ? `?server=${encodeURIComponent(server.name)}` : '';
        const data = unwrap(await getPluginApi(props.api, props.pluginId, `libraries${query}`)) || {};
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
  );
  sections.value = results;
  for (const section of results) open[section.name] = true;
  loading.value = false;
}

// servers 由父组件异步加载，就绪后（或变化时）重拉媒体库
watch(
  () => props.servers,
  () => loadAll(),
);
onMounted$2(loadAll);

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$2("VChip");
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VCheckboxBtn = _resolveComponent$2("VCheckboxBtn");

  return (_openBlock$2(), _createElementBlock$1("div", _hoisted_1$2, [
    _createElementVNode$2("div", _hoisted_2$1, [
      _createElementVNode$2("div", _hoisted_3$1, [
        _cache[1] || (_cache[1] = _createTextVNode$2(" 目标媒体库 ", -1)),
        _createVNode$2(_component_VChip, {
          size: "x-small",
          variant: "tonal",
          color: "primary",
          class: "ms-2"
        }, {
          default: _withCtx$2(() => [
            _createTextVNode$2("已选 " + _toDisplayString$2(selectedTotal.value), 1)
          ]),
          _: 1
        })
      ]),
      _createVNode$2(_component_VBtn, {
        size: "small",
        variant: "text",
        loading: loading.value,
        onClick: loadAll
      }, {
        default: _withCtx$2(() => [...(_cache[2] || (_cache[2] = [
          _createTextVNode$2("刷新", -1)
        ]))]),
        _: 1
      }, 8, ["loading"])
    ]),
    (!sections.value.length && !loading.value)
      ? (_openBlock$2(), _createElementBlock$1("div", _hoisted_4$1, " 未获取到媒体服务器：请先在「参与封面的服务器」里确认宿主已启用 Emby。 "))
      : _createCommentVNode$2("", true),
    (_openBlock$2(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(sections.value, (section) => {
      return (_openBlock$2(), _createElementBlock$1("div", {
        key: section.name,
        class: "ec-acl-section"
      }, [
        _createElementVNode$2("div", {
          class: "ec-acl-row",
          role: "button",
          onClick: $event => (toggleOpen(section.name))
        }, [
          _createVNode$2(_component_VIcon, {
            icon: "mdi-chevron-down",
            size: "18",
            class: _normalizeClass(["ec-acl-caret", { 'ec-acl-caret--closed': !open[section.name] }])
          }, null, 8, ["class"]),
          _createElementVNode$2("span", _hoisted_6, _toDisplayString$2(section.name), 1),
          _createElementVNode$2("span", _hoisted_7, _toDisplayString$2(countSelected(section)) + "/" + _toDisplayString$2(section.libraries.length), 1),
          _createVNode$2(_component_VCheckboxBtn, {
            "model-value": allSelected(section),
            indeterminate: countSelected(section) > 0 && !allSelected(section),
            disabled: props.disabled || !section.libraries.length,
            color: "primary",
            "hide-details": "",
            density: "compact",
            onClick: _cache[0] || (_cache[0] = _withModifiers(() => {}, ["stop"])),
            "onUpdate:modelValue": $event => (toggleSection(section))
          }, null, 8, ["model-value", "indeterminate", "disabled", "onUpdate:modelValue"])
        ], 8, _hoisted_5),
        _withDirectives(_createElementVNode$2("div", _hoisted_8, [
          (_openBlock$2(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(section.libraries, (library) => {
            return (_openBlock$2(), _createElementBlock$1("button", {
              key: library.id,
              type: "button",
              class: _normalizeClass(["ec-acl-chip", { 'ec-acl-chip--on': isSelected(section.name, library.id) }]),
              disabled: props.disabled,
              onClick: $event => (toggle(section.name, library.id))
            }, [
              _createVNode$2(_component_VIcon, {
                icon: isSelected(section.name, library.id) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline',
                size: "14"
              }, null, 8, ["icon"]),
              _createElementVNode$2("span", _hoisted_10, _toDisplayString$2(library.name || library.id), 1)
            ], 10, _hoisted_9))
          }), 128)),
          (section.error)
            ? (_openBlock$2(), _createElementBlock$1("div", _hoisted_11, _toDisplayString$2(section.error), 1))
            : (!section.libraries.length)
              ? (_openBlock$2(), _createElementBlock$1("div", _hoisted_12, " 该服务器暂无媒体库 "))
              : _createCommentVNode$2("", true)
        ], 512), [
          [_vShow, open[section.name]]
        ])
      ]))
    }), 128))
  ]))
}
}

};

const {createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,createVNode:_createVNode$1,toDisplayString:_toDisplayString$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,createElementVNode:_createElementVNode$1} = await importShared('vue');


const _hoisted_1$1 = {
  key: 2,
  class: "text-caption text-medium-emphasis py-4 text-center"
};
const _hoisted_2 = { class: "d-flex align-center mb-1" };
const _hoisted_3 = { class: "text-subtitle-2" };
const _hoisted_4 = { class: "ec-bk-versions" };

const {onMounted: onMounted$1,ref: ref$1} = await importShared('vue');

/**
 * 封面备份管理：按服务器分节列出各媒体库的备份版本，支持恢复（指定版本或最新）。
 * 备份由自动封面在覆盖上传前自动生成（每库保留最近 3 版），本组件只做展示与恢复。
 */

const _sfc_main$1 = {
  __name: 'CoverBackups',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  modelValue: { type: Boolean, default: false },
},
  emits: ['update:modelValue'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const backups = ref$1([]);
const loading = ref$1(false);
const error = ref$1('');
const message = ref$1('');
const messageOk = ref$1(false);
const restoring = ref$1('');

function close() {
  emit('update:modelValue', false);
}

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'cover_backups')) || {};
    backups.value = Array.isArray(data.backups) ? data.backups : [];
  } catch (err) {
    error.value = err?.message || '读取备份列表失败';
    backups.value = [];
  } finally {
    loading.value = false;
  }
}

async function restore(item, timestamp) {
  const key = `${item.server}/${item.library_id}/${timestamp || 'latest'}`;
  if (restoring.value) return
  restoring.value = key;
  message.value = '';
  try {
    const data =
      unwrap(await postPluginApi(props.api, props.pluginId, 'cover_backup/restore', {
        server: item.server,
        library_id: item.library_id,
        timestamp: timestamp || '',
      })) || {};
    message.value = data.message || '封面已从备份恢复';
    messageOk.value = true;
  } catch (err) {
    message.value = err?.message || '恢复失败';
    messageOk.value = false;
  } finally {
    restoring.value = '';
  }
}

function formatSize(size) {
  const kb = Number(size || 0) / 1024;
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`
}

function formatStamp(stamp) {
  const raw = String(stamp || '');
  if (raw.length !== 15) return raw
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)} ${raw.slice(9, 11)}:${raw.slice(11, 13)}:${raw.slice(13, 15)}`
}

onMounted$1(load);

return (_ctx, _cache) => {
  const _component_VCardTitle = _resolveComponent$1("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$1("VCardSubtitle");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VCardItem = _resolveComponent$1("VCardItem");
  const _component_VDivider = _resolveComponent$1("VDivider");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VProgressCircular = _resolveComponent$1("VProgressCircular");
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VCard = _resolveComponent$1("VCard");
  const _component_VDialog = _resolveComponent$1("VDialog");

  return (_openBlock$1(), _createBlock$1(_component_VDialog, {
    "model-value": props.modelValue,
    "max-width": "640",
    scrollable: "",
    "onUpdate:modelValue": _cache[0] || (_cache[0] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$1(() => [
      _createVNode$1(_component_VCard, { class: "ec-bk" }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCardItem, { class: "py-3" }, {
            append: _withCtx$1(() => [
              _createVNode$1(_component_VBtn, {
                icon: "mdi-refresh",
                size: "small",
                variant: "text",
                loading: loading.value,
                onClick: load
              }, null, 8, ["loading"]),
              _createVNode$1(_component_VBtn, {
                icon: "mdi-close",
                size: "small",
                variant: "text",
                onClick: close
              })
            ]),
            default: _withCtx$1(() => [
              _createVNode$1(_component_VCardTitle, { class: "text-subtitle-1" }, {
                default: _withCtx$1(() => [...(_cache[1] || (_cache[1] = [
                  _createTextVNode$1("封面备份管理", -1)
                ]))]),
                _: 1
              }),
              _createVNode$1(_component_VCardSubtitle, { class: "text-caption" }, {
                default: _withCtx$1(() => [...(_cache[2] || (_cache[2] = [
                  _createTextVNode$1("自动封面覆盖上传前自动保存原版封面，每库保留最近 3 版", -1)
                ]))]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$1(_component_VDivider),
          _createVNode$1(_component_VCardText, { class: "ec-bk-body" }, {
            default: _withCtx$1(() => [
              (error.value)
                ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                    key: 0,
                    type: "warning",
                    variant: "tonal",
                    density: "compact",
                    class: "mb-2"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(error.value), 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$1("", true),
              (message.value)
                ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                    key: 1,
                    type: messageOk.value ? 'success' : 'error',
                    variant: "tonal",
                    density: "compact",
                    class: "mb-2"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(message.value), 1)
                    ]),
                    _: 1
                  }, 8, ["type"]))
                : _createCommentVNode$1("", true),
              (!loading.value && !backups.value.length)
                ? (_openBlock$1(), _createElementBlock("div", _hoisted_1$1, " 暂无备份。开启自动封面并执行一轮任务后，原版封面会自动存到这里。 "))
                : _createCommentVNode$1("", true),
              (_openBlock$1(true), _createElementBlock(_Fragment, null, _renderList(backups.value, (item) => {
                return (_openBlock$1(), _createElementBlock("div", {
                  key: `${item.server}/${item.library_id}`,
                  class: "ec-bk-lib mb-3"
                }, [
                  _createElementVNode$1("div", _hoisted_2, [
                    _createVNode$1(_component_VIcon, {
                      icon: "mdi-folder-outline",
                      size: "16",
                      class: "mr-1 text-medium-emphasis"
                    }),
                    _createElementVNode$1("span", _hoisted_3, _toDisplayString$1(item.server) + " · " + _toDisplayString$1(item.library_name), 1)
                  ]),
                  _createElementVNode$1("div", _hoisted_4, [
                    (_openBlock$1(true), _createElementBlock(_Fragment, null, _renderList(item.versions, (version) => {
                      return (_openBlock$1(), _createBlock$1(_component_VChip, {
                        key: version.filename,
                        size: "small",
                        variant: "tonal",
                        color: "primary",
                        class: "ma-1",
                        disabled: !!restoring.value,
                        onClick: $event => (restore(item, version.timestamp))
                      }, {
                        default: _withCtx$1(() => [
                          (restoring.value === `${item.server}/${item.library_id}/${version.timestamp}`)
                            ? (_openBlock$1(), _createBlock$1(_component_VProgressCircular, {
                                key: 0,
                                size: "12",
                                width: "2",
                                indeterminate: "",
                                class: "mr-1"
                              }))
                            : _createCommentVNode$1("", true),
                          _createTextVNode$1(" " + _toDisplayString$1(formatStamp(version.timestamp)) + " · " + _toDisplayString$1(formatSize(version.size)), 1)
                        ]),
                        _: 2
                      }, 1032, ["disabled", "onClick"]))
                    }), 128)),
                    (item.versions.length > 1)
                      ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                          key: 0,
                          size: "small",
                          variant: "outlined",
                          class: "ma-1",
                          disabled: !!restoring.value,
                          onClick: $event => (restore(item, item.versions[0].timestamp))
                        }, {
                          default: _withCtx$1(() => [...(_cache[3] || (_cache[3] = [
                            _createTextVNode$1(" 恢复最新 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled", "onClick"]))
                      : _createCommentVNode$1("", true)
                  ])
                ]))
              }), 128))
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["model-value"]))
}
}

};

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = { class: "ec-body" };

const {computed,onMounted,reactive,ref} = await importShared('vue');

/**
 * 插件配置面板：顶部总开关 + 两个分区（基础设置 / 封面设计）。
 *
 * 纪律：字段与后端 model/config.py 的 default_config() 保持一致；配置由宿主
 * `plugin/<id>` 的 GET/PUT 承载，本组件只负责渲染与回填，不做本地持久化。
 */

const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  initialConfig: { type: Object, default: () => ({}) },
  busy: { type: Boolean, default: false },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const tab = ref('base');

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
});

const servers = ref([]);
const loadingServers = ref(false);
const serverError = ref('');
const templates = ref([]);
const coverRef = ref(null);
const runningCover = ref(false);
const runMessage = ref('');
const runOk = ref(true);
const showBackups = ref(false);

/** 执行频率：预设 + 自定义。单独维护下拉选择值——选中「自定义」时若直接绑
 * form.cover_cron，computed getter 会立刻弹回旧预设（表现为点了没反应）。 */
const scheduleOptions = [
  { title: '每天 04:00', value: '0 4 * * *' },
  { title: '每 6 小时', value: '0 */6 * * *' },
  { title: '每周一 04:00', value: '0 4 * * 1' },
  { title: '每小时', value: '0 * * * *' },
  { title: '每 30 分钟', value: '*/30 * * * *' },
  { title: '自定义 Cron', value: '__custom__' },
];
const scheduleChoice = ref(
  scheduleOptions.some(item => item.value === form.cover_cron) ? form.cover_cron : '__custom__',
);
function onScheduleChange(value) {
  scheduleChoice.value = value;
  if (value && value !== '__custom__') form.cover_cron = value;
}

const serverItems = computed(() =>
  servers.value.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
);

const templateItems = computed(() => [
  { title: '跟随封面设计', value: '' },
  ...templates.value.map(template => ({
    title: template.name || template.filename,
    value: template.filename,
  })),
]);

async function loadServers() {
  if (loadingServers.value) return
  loadingServers.value = true;
  serverError.value = '';
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'status')) || {};
    servers.value = Array.isArray(data.servers) ? data.servers : [];
  } catch (error) {
    servers.value = [];
    serverError.value = error?.message || '媒体服务器读取失败';
  } finally {
    loadingServers.value = false;
  }
}

async function loadTemplates() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'templates')) || {};
    templates.value = Array.isArray(data.templates) ? data.templates : [];
  } catch (error) {
    templates.value = [];
  }
}

async function runAutoCover() {
  if (runningCover.value) return
  runningCover.value = true;
  runMessage.value = '';
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'auto_cover/run', {})) || {};
    runMessage.value = data.message || '自动封面任务已在后台启动';
    runOk.value = true;
  } catch (error) {
    runMessage.value = error?.message || '启动失败';
    runOk.value = false;
  } finally {
    runningCover.value = false;
  }
}

function submit() {
  if (props.busy) return
  const cover = coverRef.value?.snapshot ? coverRef.value.snapshot() : {};
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
  });
}

onMounted(() => {
  loadServers();
  loadTemplates();
});

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
  const _component_VWindow = _resolveComponent("VWindow");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: "ec-config"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardItem, { class: "ec-header" }, {
        prepend: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            size: "44",
            rounded: "lg"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: "mdi-image-multiple-outline",
                size: "24"
              })
            ]),
            _: 1
          })
        ]),
        append: _withCtx(() => [
          _createVNode(_component_VSwitch, {
            modelValue: form.enabled,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.enabled) = $event)),
            color: "success",
            "hide-details": "",
            inset: "",
            label: form.enabled ? '已启用' : '已停用'
          }, null, 8, ["modelValue", "label"])
        ]),
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "text-h6" }, {
            default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
              _createTextVNode("胖虎封面中心", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
            default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
              _createTextVNode("Emby 媒体库封面生成与任务中心", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      _createVNode(_component_VTabs, {
        modelValue: tab.value,
        "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((tab).value = $event)),
        density: "comfortable",
        color: "primary",
        class: "ec-tabs"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VTab, {
            value: "base",
            "prepend-icon": "mdi-cog-outline"
          }, {
            default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
              _createTextVNode("基础设置", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VTab, {
            value: "cover",
            "prepend-icon": "mdi-image-edit-outline"
          }, {
            default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
              _createTextVNode("封面设计", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue"]),
      _createVNode(_component_VDivider),
      _createElementVNode("div", _hoisted_1, [
        _createVNode(_component_VWindow, {
          modelValue: tab.value,
          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((tab).value = $event)),
          touch: false
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VWindowItem, {
              value: "base",
              class: "ec-pane"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCard, {
                          variant: "tonal",
                          class: "ec-block"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VCardItem, { class: "py-2" }, {
                              default: _withCtx(() => [
                                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                                  default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                                    _createTextVNode("基础", -1)
                                  ]))]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            }),
                            _createVNode(_component_VCardText, null, {
                              default: _withCtx(() => [
                                _createVNode(_component_VSwitch, {
                                  modelValue: form.discovery_page_enabled,
                                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.discovery_page_enabled) = $event)),
                                  color: "primary",
                                  "hide-details": "",
                                  inset: "",
                                  class: "mb-3",
                                  label: "在「发现」分区显示整页入口"
                                }, null, 8, ["modelValue"]),
                                _createVNode(_component_VSwitch, {
                                  modelValue: form.auto_refresh_on_webhook,
                                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.auto_refresh_on_webhook) = $event)),
                                  color: "primary",
                                  "hide-details": "",
                                  inset: "",
                                  class: "mb-3",
                                  label: "Emby 入库后自动刷新对应媒体库封面"
                                }, null, 8, ["modelValue"]),
                                _createVNode(_component_VSwitch, {
                                  modelValue: form.notify_on_task_finish,
                                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.notify_on_task_finish) = $event)),
                                  color: "primary",
                                  "hide-details": "",
                                  inset: "",
                                  label: "任务完成后发送通知（走 MP 通知渠道）"
                                }, null, 8, ["modelValue"])
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCard, {
                          variant: "tonal",
                          class: "ec-block"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VCardItem, { class: "py-2" }, {
                              append: _withCtx(() => [
                                _createVNode(_component_VBtn, {
                                  size: "small",
                                  variant: "text",
                                  loading: loadingServers.value,
                                  onClick: loadServers
                                }, {
                                  default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                                    _createTextVNode("刷新", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["loading"])
                              ]),
                              default: _withCtx(() => [
                                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                                  default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                                    _createTextVNode("媒体服务器", -1)
                                  ]))]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            }),
                            _createVNode(_component_VCardText, null, {
                              default: _withCtx(() => [
                                (serverError.value)
                                  ? (_openBlock(), _createBlock(_component_VAlert, {
                                      key: 0,
                                      type: "warning",
                                      variant: "tonal",
                                      density: "compact",
                                      class: "mb-2"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(serverError.value), 1)
                                      ]),
                                      _: 1
                                    }))
                                  : _createCommentVNode("", true),
                                _createVNode(_component_VSelect, {
                                  modelValue: form.selected_servers,
                                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.selected_servers) = $event)),
                                  items: serverItems.value,
                                  label: "参与封面的服务器",
                                  chips: "",
                                  multiple: "",
                                  clearable: "",
                                  density: "compact",
                                  variant: "outlined",
                                  disabled: !servers.value.length
                                }, null, 8, ["modelValue", "items", "disabled"]),
                                _cache[22] || (_cache[22] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mt-1" }, " 留空表示使用全部已启用的媒体服务器。 ", -1))
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCard, {
                          variant: "tonal",
                          class: "ec-block"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VCardItem, { class: "py-2" }, {
                              append: _withCtx(() => [
                                _createVNode(_component_VBtn, {
                                  size: "small",
                                  variant: "text",
                                  "prepend-icon": "mdi-backup-restore",
                                  onClick: _cache[6] || (_cache[6] = $event => (showBackups.value = true))
                                }, {
                                  default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                                    _createTextVNode(" 备份管理 ", -1)
                                  ]))]),
                                  _: 1
                                }),
                                _createVNode(_component_VBtn, {
                                  size: "small",
                                  variant: "tonal",
                                  "prepend-icon": "mdi-play",
                                  loading: runningCover.value,
                                  disabled: !form.enabled,
                                  onClick: runAutoCover
                                }, {
                                  default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
                                    _createTextVNode(" 立即运行 ", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["loading", "disabled"])
                              ]),
                              default: _withCtx(() => [
                                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                                  default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                                    _createTextVNode("自动封面任务", -1)
                                  ]))]),
                                  _: 1
                                }),
                                _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
                                  default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                                    _createTextVNode(" 定时 / Emby 入库时，为选中媒体库自动生成并应用封面 ", -1)
                                  ]))]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            }),
                            _createVNode(_component_VCardText, null, {
                              default: _withCtx(() => [
                                (runMessage.value)
                                  ? (_openBlock(), _createBlock(_component_VAlert, {
                                      key: 0,
                                      type: runOk.value ? 'success' : 'error',
                                      variant: "tonal",
                                      density: "compact",
                                      class: "mb-2"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(runMessage.value), 1)
                                      ]),
                                      _: 1
                                    }, 8, ["type"]))
                                  : _createCommentVNode("", true),
                                _createVNode(_component_VRow, { dense: "" }, {
                                  default: _withCtx(() => [
                                    _createVNode(_component_VCol, {
                                      cols: "12",
                                      md: "4"
                                    }, {
                                      default: _withCtx(() => [
                                        _createVNode(_component_VSwitch, {
                                          modelValue: form.auto_cover_enabled,
                                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.auto_cover_enabled) = $event)),
                                          color: "primary",
                                          "hide-details": "",
                                          inset: "",
                                          class: "mt-2",
                                          label: "启用定时自动封面"
                                        }, null, 8, ["modelValue"])
                                      ]),
                                      _: 1
                                    }),
                                    _createVNode(_component_VCol, {
                                      cols: "12",
                                      md: "4"
                                    }, {
                                      default: _withCtx(() => [
                                        _createVNode(_component_VSelect, {
                                          modelValue: form.auto_cover_template,
                                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.auto_cover_template) = $event)),
                                          items: templateItems.value,
                                          label: "封面方案",
                                          density: "compact",
                                          variant: "outlined",
                                          "hide-details": ""
                                        }, null, 8, ["modelValue", "items"])
                                      ]),
                                      _: 1
                                    }),
                                    _createVNode(_component_VCol, {
                                      cols: "12",
                                      md: "4"
                                    }, {
                                      default: _withCtx(() => [
                                        _createVNode(_component_VSelect, {
                                          "model-value": scheduleChoice.value,
                                          items: scheduleOptions,
                                          label: "执行频率",
                                          density: "compact",
                                          variant: "outlined",
                                          "hide-details": "",
                                          "onUpdate:modelValue": onScheduleChange
                                        }, null, 8, ["model-value"])
                                      ]),
                                      _: 1
                                    }),
                                    _createVNode(_component_VCol, { cols: "12" }, {
                                      default: _withCtx(() => [
                                        _createVNode(_component_VSwitch, {
                                          modelValue: form.auto_backup_enabled,
                                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.auto_backup_enabled) = $event)),
                                          color: "primary",
                                          "hide-details": "",
                                          inset: "",
                                          label: "覆盖前自动备份原版封面（每库保留最近 3 版，可在「备份管理」恢复）"
                                        }, null, 8, ["modelValue"])
                                      ]),
                                      _: 1
                                    }),
                                    (scheduleChoice.value === '__custom__')
                                      ? (_openBlock(), _createBlock(_component_VCol, {
                                          key: 0,
                                          cols: "12",
                                          md: "6"
                                        }, {
                                          default: _withCtx(() => [
                                            _createVNode(_component_VTextField, {
                                              modelValue: form.cover_cron,
                                              "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.cover_cron) = $event)),
                                              label: "Cron 表达式",
                                              placeholder: "分 时 日 月 周，如 30 5 * * *",
                                              density: "compact",
                                              variant: "outlined",
                                              "hide-details": ""
                                            }, null, 8, ["modelValue"])
                                          ]),
                                          _: 1
                                        }))
                                      : _createCommentVNode("", true),
                                    _createVNode(_component_VCol, { cols: "12" }, {
                                      default: _withCtx(() => [
                                        _createVNode(_sfc_main$2, {
                                          modelValue: form.auto_cover_libraries,
                                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.auto_cover_libraries) = $event)),
                                          api: props.api,
                                          "plugin-id": props.pluginId,
                                          servers: servers.value,
                                          disabled: !servers.value.length
                                        }, null, 8, ["modelValue", "api", "plugin-id", "servers", "disabled"])
                                      ]),
                                      _: 1
                                    }),
                                    _createVNode(_component_VCol, { cols: "12" }, {
                                      default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                                        _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, " 「跟随封面设计」使用封面设计 Tab 当前保存的布局与参数；执行时只处理所选媒体库与 「参与封面的服务器」的交集。Emby 入库自动刷新由上方开关控制，同样只刷新这里勾选的媒体库。 ", -1)
                                      ]))]),
                                      _: 1
                                    })
                                  ]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        })
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VWindowItem, {
              value: "cover",
              class: "ec-pane"
            }, {
              default: _withCtx(() => [
                _createVNode(CoverDesignPane, {
                  ref_key: "coverRef",
                  ref: coverRef,
                  api: props.api,
                  "plugin-id": props.pluginId,
                  "initial-config": props.initialConfig,
                  servers: servers.value
                }, null, 8, ["api", "plugin-id", "initial-config", "servers"])
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"])
      ]),
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardActions, null, {
        default: _withCtx(() => [
          _createVNode(_component_VSpacer),
          _createVNode(_component_VBtn, {
            variant: "text",
            disabled: props.busy,
            onClick: _cache[13] || (_cache[13] = $event => (emit('close')))
          }, {
            default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
              _createTextVNode("取消", -1)
            ]))]),
            _: 1
          }, 8, ["disabled"]),
          _createVNode(_component_VBtn, {
            color: "primary",
            variant: "flat",
            "prepend-icon": "mdi-content-save-outline",
            loading: props.busy,
            disabled: props.busy,
            onClick: submit
          }, {
            default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
              _createTextVNode(" 保存配置 ", -1)
            ]))]),
            _: 1
          }, 8, ["loading", "disabled"])
        ]),
        _: 1
      }),
      _createVNode(_sfc_main$1, {
        modelValue: showBackups.value,
        "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((showBackups).value = $event)),
        api: props.api,
        "plugin-id": props.pluginId
      }, null, 8, ["modelValue", "api", "plugin-id"])
    ]),
    _: 1
  }))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-e7449dfc"]]);

export { Config as default };
