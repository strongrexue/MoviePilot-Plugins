import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, u as unwrap } from './_plugin-vue_export-helper-CF63hxE1.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = { class: "text-caption" };

const {onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, default: () => ({}) },
},
  setup(__props) {

const props = __props;

const loading = ref(false);
const loadError = ref('');
const cache = ref([]);

const dashboardPluginId = () => String(props.pluginId || '').trim() || 'TgMediaCenter';

async function loadData() {
  loading.value = true;
  loadError.value = '';
  try {
    const response = await getPluginApi(props.api, dashboardPluginId(), 'cache/status', { timeoutMs: 8000 });
    cache.value = unwrap(response) || [];
  } catch (error) {
    loadError.value = error?.message || '缓存统计加载失败';
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: "tg-dashboard"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardItem, { class: "tg-dashboard-header" }, {
        prepend: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            rounded: "lg",
            size: "40"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-chart-box-outline" })
            ]),
            _: 1
          })
        ]),
        append: _withCtx(() => [
          _createVNode(_component_VBtn, {
            icon: "",
            variant: "text",
            size: "small",
            loading: loading.value,
            onClick: loadData
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-refresh" })
            ]),
            _: 1
          }, 8, ["loading"])
        ]),
        default: _withCtx(() => [
          _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
            default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
              _createTextVNode("TG媒体中心", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
            default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
              _createTextVNode("缓存统计与近期命中", -1)
            ]))]),
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
            : (!cache.value.length)
              ? (_openBlock(), _createBlock(_component_VAlert, {
                  key: 1,
                  type: "info",
                  variant: "tonal",
                  density: "compact"
                }, {
                  default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
                    _createTextVNode(" 暂无缓存数据（仪表盘待实现）。 ", -1)
                  ]))]),
                  _: 1
                }))
              : (_openBlock(), _createBlock(_component_VList, {
                  key: 2,
                  density: "compact"
                }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cache.value, (item) => {
                      return (_openBlock(), _createBlock(_component_VListItem, {
                        key: item.chat_id,
                        title: String(item.chat_id)
                      }, {
                        append: _withCtx(() => [
                          _createElementVNode("span", _hoisted_1, _toDisplayString(item.message_count) + " 条", 1)
                        ]),
                        _: 2
                      }, 1032, ["title"]))
                    }), 128))
                  ]),
                  _: 1
                }))
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-157d01db"]]);

export { Dashboard as default };
