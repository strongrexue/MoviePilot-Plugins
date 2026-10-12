import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, u as unwrap } from './_plugin-vue_export-helper--Uc9iKY6.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = {
  key: 2,
  class: "tg-status-raw"
};

const {onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const loading = ref(false);
const loadError = ref('');
const status = ref(null);

async function loadStatus() {
  loading.value = true;
  loadError.value = '';
  try {
    const response = await getPluginApi(props.api, props.pluginId, 'status', { timeoutMs: 8000 });
    status.value = unwrap(response);
  } catch (error) {
    loadError.value = error?.message || '状态加载失败';
  } finally {
    loading.value = false;
  }
}

onMounted(loadStatus);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: "tg-page"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VToolbar, {
        density: "comfortable",
        class: "tg-toolbar"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            rounded: "lg",
            class: "ms-3 me-2"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-send-circle-outline" })
            ]),
            _: 1
          }),
          _cache[4] || (_cache[4] = _createElementVNode("div", { class: "tg-heading" }, [
            _createElementVNode("div", { class: "text-h6" }, "TG媒体中心 · 运行详情"),
            _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "TG 客户端 → 消息流水线 → 缓存 / 监控 / 转发")
          ], -1)),
          _createVNode(_component_VSpacer),
          _createVNode(_component_VBtn, {
            variant: "text",
            size: "small",
            loading: loading.value,
            "prepend-icon": "mdi-refresh",
            onClick: loadStatus
          }, {
            default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
              _createTextVNode(" 刷新 ", -1)
            ]))]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_VBtn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-cog-outline",
            onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
          }, {
            default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
              _createTextVNode("设置", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VBtn, {
            icon: "",
            variant: "text",
            size: "small",
            onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-close" })
            ]),
            _: 1
          })
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
      _createVNode(_component_VCardText, { class: "pa-3" }, {
        default: _withCtx(() => [
          (loadError.value)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(loadError.value), 1)
                ]),
                _: 1
              }))
            : (_openBlock(), _createBlock(_component_VAlert, {
                key: 1,
                type: "info",
                variant: "tonal",
                density: "compact"
              }, {
                default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                  _createTextVNode(" 运行状态面板待实现（TG 客户端 / 115 / 缓存统计 / 命中流水）。 ", -1)
                ]))]),
                _: 1
              })),
          (status.value)
            ? (_openBlock(), _createElementBlock("pre", _hoisted_1, _toDisplayString(JSON.stringify(status.value, null, 2)), 1))
            : _createCommentVNode("", true)
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-d901a11b"]]);

export { Page as default };
