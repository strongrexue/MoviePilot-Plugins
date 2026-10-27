import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, u as unwrap, a as getPluginApi } from './_plugin-vue_export-helper-BGiM_AXo.js';
import { F as FRONTEND_VERSION } from './version-CHwci9P4.js';

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,createElementVNode:_createElementVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,unref:_unref,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "ec-dash" };
const _hoisted_2 = { class: "ec-chips" };
const _hoisted_3 = { class: "ec-list" };
const _hoisted_4 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};

const {computed,onMounted,ref} = await importShared('vue');

/**
 * 仪表盘卡片：一眼概览插件与媒体服务器状态。
 */

const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
},
  setup(__props) {

const props = __props;

const status = ref({});
const loadError = ref('');

const backendVersion = computed(() => String(status.value.plugin_version || ''));
const versionMismatched = computed(
  () => !!backendVersion.value && backendVersion.value !== FRONTEND_VERSION,
);
const servers = computed(() => (Array.isArray(status.value.servers) ? status.value.servers : []));
const activeCount = computed(() => servers.value.filter(server => server.active).length);

async function load() {
  loadError.value = '';
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status')) || {};
  } catch (error) {
    loadError.value = error?.message || '状态读取失败';
  }
}

onMounted(load);

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent("VChip");
  const _component_VAlert = _resolveComponent("VAlert");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("div", _hoisted_2, [
      _createVNode(_component_VChip, {
        color: status.value.enabled ? 'success' : 'grey',
        variant: "tonal",
        size: "small",
        label: ""
      }, {
        default: _withCtx(() => [
          _createTextVNode(_toDisplayString(status.value.enabled ? '已启用' : '已停用'), 1)
        ]),
        _: 1
      }, 8, ["color"]),
      _createVNode(_component_VChip, {
        color: "primary",
        variant: "tonal",
        size: "small",
        label: ""
      }, {
        default: _withCtx(() => [
          _createTextVNode("v" + _toDisplayString(backendVersion.value || '—'), 1)
        ]),
        _: 1
      }),
      _createVNode(_component_VChip, {
        color: "info",
        variant: "tonal",
        size: "small",
        label: ""
      }, {
        default: _withCtx(() => [
          _createTextVNode(" 服务器 " + _toDisplayString(activeCount.value) + "/" + _toDisplayString(servers.value.length), 1)
        ]),
        _: 1
      })
    ]),
    (loadError.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mt-2"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(loadError.value), 1)
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
          class: "mt-2"
        }, {
          default: _withCtx(() => [
            _createTextVNode(" 前端组件 v" + _toDisplayString(_unref(FRONTEND_VERSION)) + " ≠ 后端 v" + _toDisplayString(backendVersion.value) + "，请 Ctrl + Shift + R 硬刷新。 ", 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createElementVNode("div", _hoisted_3, [
      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(servers.value, (server) => {
        return (_openBlock(), _createElementBlock("div", {
          key: server.name,
          class: "ec-row"
        }, [
          _createElementVNode("span", null, _toDisplayString(server.name), 1),
          _createElementVNode("b", {
            class: _normalizeClass(server.active ? 'text-success' : 'text-warning')
          }, _toDisplayString(server.active ? '已连接' : '未连接'), 3)
        ]))
      }), 128)),
      (!servers.value.length)
        ? (_openBlock(), _createElementBlock("div", _hoisted_4, " 未发现已启用的媒体服务器。 "))
        : _createCommentVNode("", true)
    ])
  ]))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-54ab2792"]]);

export { Dashboard as default };
