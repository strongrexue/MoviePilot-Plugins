import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, u as unwrap, g as getPluginApi } from './_plugin-vue_export-helper--Uc9iKY6.js';
import { d as decisionLabel } from './decision-pgT01eSj.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,unref:_unref} = await importShared('vue');


const _hoisted_1 = { class: "tg-chips" };
const _hoisted_2 = {
  key: 0,
  class: "tg-recent"
};
const _hoisted_3 = { class: "tg-recent-media" };
const _hoisted_4 = { class: "tg-recent-meta" };
const _hoisted_5 = {
  key: 1,
  class: "tg-empty"
};

const {computed,onMounted,ref} = await importShared('vue');

/**
 * 插件仪表盘卡片（宿主首页的模块卡片）。
 *
 * 与详情页（Page.vue）共用 ``/overview`` 聚合接口：卡片只放"一眼可见"的
 * 汇总（TG / 115 / 缓存 / 队列）+ 最近几条监控流水，详细排查去详情页。
 */

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
const data = ref(null);

const dashboardPluginId = () => String(props.pluginId || '').trim() || 'TgMediaCenter';

async function loadData() {
  loading.value = true;
  loadError.value = '';
  try {
    data.value = unwrap(await getPluginApi(props.api, dashboardPluginId(), 'overview', { timeoutMs: 15000 }));
  } catch (error) {
    loadError.value = error?.message || '概览加载失败';
  } finally {
    loading.value = false;
  }
}

const tg = computed(() => data.value?.tg || {});
const pan115 = computed(() => data.value?.pan115 || {});
const cache = computed(() => data.value?.cache || {});
const monitor = computed(() => data.value?.monitor || {});
const forward = computed(() => data.value?.forward || {});
const pipeline = computed(() => monitor.value.pipeline || {});
const recent = computed(() => (data.value?.recent_hits || []).slice(0, 5));

const tgOk = computed(() => Boolean(tg.value.connected && tg.value.authorized));
const pan115Ok = computed(() => Boolean(pan115.value.enabled && pan115.value.authorized));
const cacheOk = computed(() => Boolean(cache.value.enabled));

function fmtTime(value) {
  return String(value || '').replace('T', ' ').slice(5, 16) || '—'
}

function mediaName(item) {
  if (!item.title) return `消息 #${item.message_id}`
  const year = item.year ? ` (${item.year})` : '';
  let name = `${item.title}${year}`;
  if (item.season || item.episode) {
    const s = String(item.season ?? 1).padStart(2, '0');
    const e = String(item.episode ?? 0).padStart(2, '0');
    const end = Number(item.episode_end ?? 0);
    if (end > (item.episode ?? 0)) {
      name += ` S${s}E${e}-E${String(end).padStart(2, '0')}`;
    } else {
      name += ` S${s}E${e}`;
    }
  }
  return name
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
  const _component_VChip = _resolveComponent("VChip");
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
            default: _withCtx(() => [
              _createTextVNode(" TG / 115 / 缓存概览 · 缓存 " + _toDisplayString(cache.value.total ?? 0) + " 条 · 队列待处理 " + _toDisplayString(pipeline.value.push_pending ?? 0), 1)
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
            : (data.value)
              ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                  _createElementVNode("div", _hoisted_1, [
                    _createVNode(_component_VChip, {
                      size: "small",
                      variant: "tonal",
                      color: tgOk.value ? 'success' : 'warning',
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" TG " + _toDisplayString(tgOk.value ? '已连接' : (tg.value.api_configured ? '未连接' : '未配置')), 1)
                      ]),
                      _: 1
                    }, 8, ["color"]),
                    _createVNode(_component_VChip, {
                      size: "small",
                      variant: "tonal",
                      color: pan115Ok.value ? 'success' : 'default',
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 115 " + _toDisplayString(pan115Ok.value ? '已登录' : (pan115.value.enabled ? '未登录' : '未启用')), 1)
                      ]),
                      _: 1
                    }, 8, ["color"]),
                    _createVNode(_component_VChip, {
                      size: "small",
                      variant: "tonal",
                      color: cacheOk.value ? 'info' : 'default',
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 缓存 " + _toDisplayString(cache.value.chats ?? 0) + " 频道 ", 1)
                      ]),
                      _: 1
                    }, 8, ["color"]),
                    _createVNode(_component_VChip, {
                      size: "small",
                      variant: "tonal",
                      color: "primary",
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 监控命中 " + _toDisplayString(pipeline.value.hit ?? 0), 1)
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VChip, {
                      size: "small",
                      variant: "tonal",
                      color: "primary",
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 转发命中 " + _toDisplayString(pipeline.value.forward_hit ?? 0), 1)
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VChip, {
                      size: "small",
                      variant: "tonal",
                      color: (pipeline.value.push_failed ?? 0) > 0 ? 'error' : 'default',
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 失败 " + _toDisplayString(pipeline.value.push_failed ?? 0), 1)
                      ]),
                      _: 1
                    }, 8, ["color"]),
                    _createVNode(_component_VChip, {
                      size: "small",
                      variant: "tonal",
                      color: "default",
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 规则 " + _toDisplayString((monitor.value.rules_count ?? 0) + (forward.value.rules_count ?? 0)) + " 条 ", 1)
                      ]),
                      _: 1
                    })
                  ]),
                  (recent.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
                        _cache[1] || (_cache[1] = _createElementVNode("div", { class: "tg-recent-title" }, "最近流水", -1)),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recent.value, (item) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: `${item.kind}-${item.id}`,
                            class: "tg-recent-row"
                          }, [
                            _createElementVNode("span", _hoisted_3, _toDisplayString(mediaName(item)), 1),
                            _createElementVNode("span", _hoisted_4, _toDisplayString(_unref(decisionLabel)(item.decision)) + " · " + _toDisplayString(fmtTime(item.created_at)), 1)
                          ]))
                        }), 128))
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_5, "暂无命中记录：规则命中后会在这里出现。"))
                ], 64))
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
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-e9b62b47"]]);

export { Dashboard as default };
