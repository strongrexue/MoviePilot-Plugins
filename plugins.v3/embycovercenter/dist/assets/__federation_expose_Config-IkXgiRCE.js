import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, u as unwrap, a as getPluginApi } from './_plugin-vue_export-helper-C6TXstWj.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode} = await importShared('vue');


const {computed,onMounted,reactive,ref} = await importShared('vue');

/**
 * 插件配置面板。
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

const form = reactive({
  enabled: props.initialConfig.enabled === true,
  discovery_page_enabled: props.initialConfig.discovery_page_enabled === true,
  selected_servers: Array.isArray(props.initialConfig.selected_servers)
    ? [...props.initialConfig.selected_servers]
    : [],
  auto_refresh_on_webhook: props.initialConfig.auto_refresh_on_webhook !== false,
  cover_cron: props.initialConfig.cover_cron || '0 4 * * *',
  notify_on_task_finish: props.initialConfig.notify_on_task_finish !== false,
});

const servers = ref([]);
const loadingServers = ref(false);
const serverError = ref('');

const cronPresets = [
  { title: '每天 04:00', value: '0 4 * * *' },
  { title: '每 6 小时', value: '0 */6 * * *' },
  { title: '每周一 04:00', value: '0 4 * * 1' },
];

const serverItems = computed(() =>
  servers.value.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
);

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

function submit() {
  if (props.busy) return
  emit('save', {
    enabled: form.enabled,
    discovery_page_enabled: form.discovery_page_enabled,
    selected_servers: [...form.selected_servers],
    auto_refresh_on_webhook: form.auto_refresh_on_webhook,
    cover_cron: form.cover_cron,
    notify_on_task_finish: form.notify_on_task_finish,
  });
}

onMounted(loadServers);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCombobox = _resolveComponent("VCombobox");
  const _component_VRow = _resolveComponent("VRow");
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
            default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
              _createTextVNode("胖虎封面中心", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
            default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
              _createTextVNode("Emby 媒体库封面生成与任务中心", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardText, { class: "ec-body" }, {
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
                    class: "ec-pane"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VCardItem, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                            default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
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
                            "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.discovery_page_enabled) = $event)),
                            color: "primary",
                            "hide-details": "",
                            inset: "",
                            class: "mb-3",
                            label: "在「发现」分区显示整页入口"
                          }, null, 8, ["modelValue"]),
                          _createVNode(_component_VSwitch, {
                            modelValue: form.auto_refresh_on_webhook,
                            "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.auto_refresh_on_webhook) = $event)),
                            color: "primary",
                            "hide-details": "",
                            inset: "",
                            class: "mb-3",
                            label: "Emby 入库后自动刷新对应媒体库封面"
                          }, null, 8, ["modelValue"]),
                          _createVNode(_component_VSwitch, {
                            modelValue: form.notify_on_task_finish,
                            "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.notify_on_task_finish) = $event)),
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
                    class: "ec-pane"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VCardItem, null, {
                        append: _withCtx(() => [
                          _createVNode(_component_VBtn, {
                            size: "small",
                            variant: "text",
                            loading: loadingServers.value,
                            onClick: loadServers
                          }, {
                            default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
                              _createTextVNode(" 刷新 ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["loading"])
                        ]),
                        default: _withCtx(() => [
                          _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                            default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
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
                            "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.selected_servers) = $event)),
                            items: serverItems.value,
                            label: "参与封面的服务器",
                            chips: "",
                            multiple: "",
                            clearable: "",
                            disabled: !servers.value.length
                          }, null, 8, ["modelValue", "items", "disabled"]),
                          _cache[12] || (_cache[12] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, " 留空表示使用全部已启用的媒体服务器。 ", -1))
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
                    class: "ec-pane"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VCardItem, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                            default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                              _createTextVNode("定时封面任务", -1)
                            ]))]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VCardText, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCombobox, {
                            modelValue: form.cover_cron,
                            "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.cover_cron) = $event)),
                            items: cronPresets,
                            label: "Cron 表达式",
                            hint: "自动生成媒体库封面的执行时间",
                            "persistent-hint": ""
                          }, null, 8, ["modelValue"])
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
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardActions, null, {
        default: _withCtx(() => [
          _createVNode(_component_VSpacer),
          _createVNode(_component_VBtn, {
            variant: "text",
            disabled: props.busy,
            onClick: _cache[6] || (_cache[6] = $event => (emit('close')))
          }, {
            default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
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
            default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
              _createTextVNode(" 保存配置 ", -1)
            ]))]),
            _: 1
          }, 8, ["loading", "disabled"])
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-c18ad0e7"]]);

export { Config as default };
