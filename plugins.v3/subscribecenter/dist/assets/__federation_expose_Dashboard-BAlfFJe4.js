import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, F as FRONTEND_VERSION, u as unwrap, a as getPluginApi } from './_plugin-vue_export-helper-nS8jbhE_.js';

const {resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,createVNode:_createVNode,createElementVNode:_createElementVNode,Fragment:_Fragment,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "sc-dash" };
const _hoisted_2 = { class: "d-flex align-center flex-wrap ga-2 mb-2" };
const _hoisted_3 = { class: "sc-hint mb-1" };
const _hoisted_4 = { class: "sc-hint" };
const _hoisted_5 = { class: "sc-hint" };
const _hoisted_6 = {
  key: 3,
  class: "sc-hint"
};

const {computed,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'SubscribeCenter' },
  config: { type: Object, default: () => ({}) },
},
  setup(__props) {

/**
 * 仪表盘小组件：紧凑展示运行状态与今日写入进度。
 */
const props = __props;

const status = ref(null);
const error = ref('');

const backendVersion = computed(() => String(status.value?.plugin_version || ''));
const versionMismatch = computed(
  () => backendVersion.value && backendVersion.value !== FRONTEND_VERSION,
);

const progress = computed(() => {
  const s = status.value;
  if (!s) return 0
  const limit = Number(s.daily_limit) || 0;
  if (!limit) return 0
  return Math.min(100, Math.round((Number(s.written_today) / limit) * 100))
});

async function load() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status'));
    error.value = '';
  } catch (err) {
    error.value = err?.message || '状态加载失败';
  }
}

onMounted(load);

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (versionMismatch.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-2",
          text: "前端组件与后端版本不一致，请 Ctrl+Shift+R 硬刷新。"
        }))
      : _createCommentVNode("", true),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "error",
          variant: "tonal",
          density: "compact",
          class: "mb-2",
          text: error.value
        }, null, 8, ["text"]))
      : _createCommentVNode("", true),
    (status.value)
      ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
          _createElementVNode("div", _hoisted_2, [
            _createVNode(_component_VChip, {
              size: "small",
              variant: "flat",
              color: status.value.enabled ? 'success' : 'default'
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(status.value.enabled ? '已启用' : '未启用'), 1)
              ]),
              _: 1
            }, 8, ["color"]),
            (status.value.dry_run)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 0,
                  size: "small",
                  variant: "flat",
                  color: "info"
                }, {
                  default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
                    _createTextVNode("dry-run", -1)
                  ]))]),
                  _: 1
                }))
              : _createCommentVNode("", true),
            (status.value.busy)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 1,
                  size: "small",
                  variant: "flat",
                  color: "warning"
                }, {
                  default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
                    _createTextVNode("运行中", -1)
                  ]))]),
                  _: 1
                }))
              : _createCommentVNode("", true),
            (!status.value.first_run_completed)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 2,
                  size: "small",
                  variant: "flat",
                  color: "warning"
                }, {
                  default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
                    _createTextVNode(" 首次将 dry-run ", -1)
                  ]))]),
                  _: 1
                }))
              : _createCommentVNode("", true)
          ]),
          _createElementVNode("div", _hoisted_3, " 今日写入 " + _toDisplayString(status.value.written_today) + " / " + _toDisplayString(status.value.daily_limit), 1),
          _createVNode(_component_VProgressLinear, {
            "model-value": progress.value,
            height: "6",
            rounded: "",
            class: "mb-2"
          }, null, 8, ["model-value"]),
          _createElementVNode("div", _hoisted_4, "最近运行：" + _toDisplayString(status.value.last_run || '—'), 1),
          _createElementVNode("div", _hoisted_5, " 上次拉取 " + _toDisplayString(status.value.last_summary?.fetched ?? 0) + " 条 · 新增 " + _toDisplayString(status.value.last_summary?.added ?? 0) + " 条 · 待确认 " + _toDisplayString(status.value.last_summary?.pending_review ?? 0) + " 条 ", 1)
        ], 64))
      : (_openBlock(), _createElementBlock("div", _hoisted_6, "状态加载中…"))
  ]))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-dbb6a260"]]);

export { Dashboard as default };
