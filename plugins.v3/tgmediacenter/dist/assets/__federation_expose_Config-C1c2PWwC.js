import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as useConfigForm, C as ConfigTgPane, a as ConfigPan115Pane, b as ConfigMonitorPane, c as ConfigCachePane, d as ConfigForwardPane, e as ConfigP9Pane } from './Config.vue_vue_type_style_index_0_scoped_9f3c533c_lang-BZSFkd9z.js';
import { _ as _export_sfc } from './decision-DOayHGVg.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,unref:_unref,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');


const _hoisted_1 = { class: "tg-config" };
const _hoisted_2 = { class: "tg-body" };
const _hoisted_3 = { class: "tg-nav" };
const _hoisted_4 = { class: "tg-content" };

const {computed,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const config = useConfigForm({
  api: () => props.api,
  pluginId: () => props.pluginId,
  initialConfig: () => props.initialConfig,
  emit,
});

const modules = [
  { key: 'tg', title: 'TG 凭证', icon: 'mdi-send-lock-outline', desc: '登录向导、冷却与保活、对话列表' },
  { key: 'pan115', title: '115 网盘', icon: 'mdi-cloud-outline', desc: '登录态、目标目录、批量提交与通知' },
  { key: 'monitor', title: '资源监控', icon: 'mdi-radar', desc: '监听频道、推送目标、仅缺集' },
  { key: 'cache', title: '消息缓存', icon: 'mdi-database-outline', desc: '缓存频道、同步与检索' },
  { key: 'forward', title: '通用转发', icon: 'mdi-share-outline', desc: '关键词与扩展名匹配、置顶与内容转换' },
  { key: 'p9', title: '重复获取治理', icon: 'mdi-shield-sync-outline', desc: '宿主能力探针、PT 侧的暂停开关' },
];

const activeModule = ref(modules[0].key);
const current = computed(() => modules.find(item => item.key === activeModule.value) || modules[0]);

onMounted(config.loadConfig);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      flat: "",
      class: "tg-card"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardItem, { class: "tg-header" }, {
          prepend: _withCtx(() => [
            _createVNode(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              size: "44",
              rounded: "lg"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-send-circle-outline",
                  size: "24"
                })
              ]),
              _: 1
            })
          ]),
          append: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: _unref(config).form.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((_unref(config).form.enabled) = $event)),
              color: "success",
              "hide-details": "",
              inset: "",
              label: _unref(config).form.enabled ? '已启用' : '已停用'
            }, null, 8, ["modelValue", "label"]),
            _createVNode(_component_VSwitch, {
              modelValue: _unref(config).form.discovery_page_enabled,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((_unref(config).form.discovery_page_enabled) = $event)),
              color: "primary",
              "hide-details": "",
              inset: "",
              class: "ms-4",
              disabled: !_unref(config).form.enabled,
              label: '发现页',
              title: "在 MP 左侧「发现」分区增加本插件的整页入口（内容为运行详情 / 仪表盘）。插件未启用时不生效；改动随底部「保存配置」生效。"
            }, null, 8, ["modelValue", "disabled"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
                _createTextVNode("胖虎媒体中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(current.value.desc), 1)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VDivider),
        _createElementVNode("div", _hoisted_2, [
          _createElementVNode("nav", _hoisted_3, [
            _createVNode(_component_VList, {
              density: "comfortable",
              nav: "",
              class: "py-2"
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(modules, (item) => {
                  return _createVNode(_component_VListItem, {
                    key: item.key,
                    active: activeModule.value === item.key,
                    color: "primary",
                    rounded: "lg",
                    onClick: $event => (activeModule.value = item.key)
                  }, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_VIcon, {
                        icon: item.icon
                      }, null, 8, ["icon"])
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_VListItemTitle, null, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.title), 1)
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _: 2
                  }, 1032, ["active", "onClick"])
                }), 64))
              ]),
              _: 1
            })
          ]),
          _createElementVNode("section", _hoisted_4, [
            (_unref(config).loading)
              ? (_openBlock(), _createBlock(_component_VProgressLinear, {
                  key: 0,
                  indeterminate: "",
                  color: "primary",
                  height: "2",
                  class: "mb-3"
                }))
              : _createCommentVNode("", true),
            (_unref(config).error)
              ? (_openBlock(), _createBlock(_component_VAlert, {
                  key: 1,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(_unref(config).error), 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode("", true),
            (activeModule.value === 'tg')
              ? (_openBlock(), _createBlock(ConfigTgPane, {
                  key: 2,
                  api: props.api,
                  "plugin-id": props.pluginId,
                  config: _unref(config)
                }, null, 8, ["api", "plugin-id", "config"]))
              : (activeModule.value === 'pan115')
                ? (_openBlock(), _createBlock(ConfigPan115Pane, {
                    key: 3,
                    api: props.api,
                    "plugin-id": props.pluginId,
                    config: _unref(config)
                  }, null, 8, ["api", "plugin-id", "config"]))
                : (activeModule.value === 'monitor')
                  ? (_openBlock(), _createBlock(ConfigMonitorPane, {
                      key: 4,
                      api: props.api,
                      "plugin-id": props.pluginId,
                      config: _unref(config)
                    }, null, 8, ["api", "plugin-id", "config"]))
                  : (activeModule.value === 'cache')
                    ? (_openBlock(), _createBlock(ConfigCachePane, {
                        key: 5,
                        api: props.api,
                        "plugin-id": props.pluginId,
                        config: _unref(config)
                      }, null, 8, ["api", "plugin-id", "config"]))
                    : (activeModule.value === 'forward')
                      ? (_openBlock(), _createBlock(ConfigForwardPane, {
                          key: 6,
                          api: props.api,
                          "plugin-id": props.pluginId,
                          config: _unref(config)
                        }, null, 8, ["api", "plugin-id", "config"]))
                      : (activeModule.value === 'p9')
                        ? (_openBlock(), _createBlock(ConfigP9Pane, {
                            key: 7,
                            api: props.api,
                            "plugin-id": props.pluginId,
                            config: _unref(config)
                          }, null, 8, ["api", "plugin-id", "config"]))
                        : _createCommentVNode("", true)
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, null, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[2] || (_cache[2] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-content-save-outline",
              onClick: _unref(config).saveConfig
            }, {
              default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                _createTextVNode(" 保存配置 ", -1)
              ]))]),
              _: 1
            }, 8, ["onClick"])
          ]),
          _: 1
        })
      ]),
      _: 1
    })
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-9f3c533c"]]);

export { Config as default };
