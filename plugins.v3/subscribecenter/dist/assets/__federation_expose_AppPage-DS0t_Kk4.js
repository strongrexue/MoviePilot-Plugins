import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Page from './__federation_expose_Page-CbsREzW2.js';
import Config from './__federation_expose_Config-DIKle0v1.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-CvFbctZh.js';

const {openBlock:_openBlock,createBlock:_createBlock,createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "sc-app-page" };

const {ref} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'SubscribeCenter' },
},
  setup(__props) {

/**
 * 「发现」分区侧栏整页入口的承载组件。
 *
 * 整页模式下没有"关闭"语义：直接复用 Page 并置 appPage=true 隐藏关闭按钮；
 * 用 navKey 拼 :key 保证切换入口时强制重挂载（否则 Vue 沿用旧实例，数据不刷新）。
 */
const props = __props;

const pageKey = ref(0);
const settingsDialog = ref(false);

function openSettings() {
  settingsDialog.value = true;
}

function afterSave() {
  settingsDialog.value = false;
  // 配置保存后重挂载 Page，让它重新拉状态
  pageKey.value += 1;
}

return (_ctx, _cache) => {
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (_openBlock(), _createBlock(Page, {
      key: `${props.pluginId}-${props.navKey}-${pageKey.value}`,
      api: __props.api,
      "plugin-id": __props.pluginId,
      "app-page": "",
      onSwitch: openSettings
    }, null, 8, ["api", "plugin-id"])),
    _createVNode(_component_VDialog, {
      modelValue: settingsDialog.value,
      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((settingsDialog).value = $event)),
      "max-width": "760",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "d-flex align-center" }, {
              default: _withCtx(() => [
                _cache[3] || (_cache[3] = _createElementVNode("span", null, "胖虎订阅中心 · 设置", -1)),
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  variant: "text",
                  size: "small",
                  onClick: _cache[0] || (_cache[0] = $event => (settingsDialog.value = false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createVNode(Config, {
                  api: __props.api,
                  "plugin-id": __props.pluginId,
                  onSave: afterSave,
                  onClose: _cache[1] || (_cache[1] = $event => (settingsDialog.value = false))
                }, null, 8, ["api", "plugin-id"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-a82907a1"]]);

export { AppPage as default };
