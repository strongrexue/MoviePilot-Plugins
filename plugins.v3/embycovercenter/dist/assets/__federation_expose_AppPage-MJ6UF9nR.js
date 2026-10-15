import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config from './__federation_expose_Config-DZY-0iaz.js';
import Page from './__federation_expose_Page-1t5RgVVb.js';
import { _ as _export_sfc, g as getPluginConfig, s as savePluginConfig } from './api-VNFYmuQY.js';

const {openBlock:_openBlock,createBlock:_createBlock,resolveComponent:_resolveComponent,createCommentVNode:_createCommentVNode,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "ec-app-page" };

const {ref} = await importShared('vue');

/**
 * MP 左侧「发现」分区的整页入口。
 *
 * 页面内容直接复用 Page.vue（与插件详情页同一份），不另做一套；整页场景没有
 * "关闭"语义，工具栏的「设置」按钮改为在这里弹出配置弹窗（与详情页同一份 Config.vue）。
 * 显示与否由后端 ``get_sidebar_nav()`` 依据配置项 ``discovery_page_enabled`` 决定。
 */

const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
},
  setup(__props) {

const props = __props;

const settingsDialog = ref(false);
const loadingSettings = ref(false);
const savingSettings = ref(false);
const settingsConfig = ref({});
const pageKey = ref(0);
const snackbar = ref({ show: false, message: '', color: 'success' });

async function openSettings() {
  if (loadingSettings.value) return
  loadingSettings.value = true;
  try {
    settingsConfig.value = await getPluginConfig(props.api, props.pluginId);
    settingsDialog.value = true;
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '设置加载失败', color: 'error' };
  } finally {
    loadingSettings.value = false;
  }
}

async function saveSettings(config) {
  if (savingSettings.value) return
  savingSettings.value = true;
  try {
    await savePluginConfig(props.api, props.pluginId, config);
    settingsConfig.value = { ...(config || {}) };
    settingsDialog.value = false;
    pageKey.value += 1;
    snackbar.value = { show: true, message: '设置已保存', color: 'success' };
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '设置保存失败', color: 'error' };
  } finally {
    savingSettings.value = false;
  }
}

return (_ctx, _cache) => {
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VSnackbar = _resolveComponent("VSnackbar");

  return (_openBlock(), _createElementBlock("main", _hoisted_1, [
    (_openBlock(), _createBlock(Page, {
      key: `${props.pluginId}-${props.navKey}-${pageKey.value}`,
      api: props.api,
      "plugin-id": props.pluginId,
      "app-page": "",
      onSwitch: openSettings
    }, null, 8, ["api", "plugin-id"])),
    _createVNode(_component_VDialog, {
      modelValue: settingsDialog.value,
      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((settingsDialog).value = $event)),
      "max-width": "1160",
      persistent: savingSettings.value || loadingSettings.value
    }, {
      default: _withCtx(() => [
        (loadingSettings.value)
          ? (_openBlock(), _createBlock(_component_VProgressLinear, {
              key: 0,
              indeterminate: "",
              color: "primary"
            }))
          : _createCommentVNode("", true),
        (!loadingSettings.value)
          ? (_openBlock(), _createBlock(Config, {
              key: 1,
              api: props.api,
              "plugin-id": props.pluginId,
              "initial-config": settingsConfig.value,
              busy: savingSettings.value,
              onSave: saveSettings,
              onClose: _cache[0] || (_cache[0] = $event => (settingsDialog.value = false))
            }, null, 8, ["api", "plugin-id", "initial-config", "busy"]))
          : _createCommentVNode("", true)
      ]),
      _: 1
    }, 8, ["modelValue", "persistent"]),
    _createVNode(_component_VSnackbar, {
      modelValue: snackbar.value.show,
      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((snackbar.value.show) = $event)),
      color: snackbar.value.color,
      timeout: "5000"
    }, {
      default: _withCtx(() => [
        _createTextVNode(_toDisplayString(snackbar.value.message), 1)
      ]),
      _: 1
    }, 8, ["modelValue", "color"])
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-cf51611b"]]);

export { AppPage as default };
