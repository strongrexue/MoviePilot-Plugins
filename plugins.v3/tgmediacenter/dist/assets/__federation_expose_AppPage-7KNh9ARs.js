import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as useConfigForm, C as ConfigTgPane, a as ConfigPan115Pane, b as ConfigMonitorPane, c as ConfigCachePane, d as ConfigForwardPane, e as ConfigP9Pane } from './Config.vue_vue_type_style_index_0_scoped_9f3c533c_lang-BZSFkd9z.js';
import { _ as _export_sfc, d as decisionLabel, a as decisionColor, u as unwrap, g as getPluginApi, p as postPluginApi, b as getPluginConfig, s as savePluginConfig } from './decision-DOayHGVg.js';
/* empty css                                                              */

const {resolveComponent:_resolveComponent$2,createVNode:_createVNode$2,withCtx:_withCtx$2,createTextVNode:_createTextVNode$2,toDisplayString:_toDisplayString$2,unref:_unref$1,renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createElementVNode:_createElementVNode$1,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2} = await importShared('vue');


const _hoisted_1$2 = { class: "tg-config" };
const _hoisted_2$1 = { class: "tg-body" };
const _hoisted_3$1 = { class: "tg-nav" };
const _hoisted_4$1 = { class: "tg-content" };

const {computed: computed$1,onMounted: onMounted$1,ref: ref$2} = await importShared('vue');


const _sfc_main$2 = {
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

const activeModule = ref$2(modules[0].key);
const current = computed$1(() => modules.find(item => item.key === activeModule.value) || modules[0]);

onMounted$1(config.loadConfig);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VAvatar = _resolveComponent$2("VAvatar");
  const _component_VCardTitle = _resolveComponent$2("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$2("VCardSubtitle");
  const _component_VSwitch = _resolveComponent$2("VSwitch");
  const _component_VCardItem = _resolveComponent$2("VCardItem");
  const _component_VDivider = _resolveComponent$2("VDivider");
  const _component_VListItemTitle = _resolveComponent$2("VListItemTitle");
  const _component_VListItem = _resolveComponent$2("VListItem");
  const _component_VList = _resolveComponent$2("VList");
  const _component_VProgressLinear = _resolveComponent$2("VProgressLinear");
  const _component_VAlert = _resolveComponent$2("VAlert");
  const _component_VSpacer = _resolveComponent$2("VSpacer");
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VCardActions = _resolveComponent$2("VCardActions");
  const _component_VCard = _resolveComponent$2("VCard");

  return (_openBlock$2(), _createElementBlock$2("div", _hoisted_1$2, [
    _createVNode$2(_component_VCard, {
      flat: "",
      class: "tg-card"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCardItem, { class: "tg-header" }, {
          prepend: _withCtx$2(() => [
            _createVNode$2(_component_VAvatar, {
              color: "primary",
              variant: "tonal",
              size: "44",
              rounded: "lg"
            }, {
              default: _withCtx$2(() => [
                _createVNode$2(_component_VIcon, {
                  icon: "mdi-send-circle-outline",
                  size: "24"
                })
              ]),
              _: 1
            })
          ]),
          append: _withCtx$2(() => [
            _createVNode$2(_component_VSwitch, {
              modelValue: _unref$1(config).form.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((_unref$1(config).form.enabled) = $event)),
              color: "success",
              "hide-details": "",
              inset: "",
              label: _unref$1(config).form.enabled ? '已启用' : '已停用'
            }, null, 8, ["modelValue", "label"]),
            _createVNode$2(_component_VSwitch, {
              modelValue: _unref$1(config).form.discovery_page_enabled,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((_unref$1(config).form.discovery_page_enabled) = $event)),
              color: "primary",
              "hide-details": "",
              inset: "",
              class: "ms-4",
              disabled: !_unref$1(config).form.enabled,
              label: '发现页',
              title: "在 MP 左侧「发现」分区增加本插件的整页入口（内容为运行详情 / 仪表盘）。插件未启用时不生效；改动随底部「保存配置」生效。"
            }, null, 8, ["modelValue", "disabled"])
          ]),
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx$2(() => [...(_cache[3] || (_cache[3] = [
                _createTextVNode$2("胖虎媒体中心", -1)
              ]))]),
              _: 1
            }),
            _createVNode$2(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx$2(() => [
                _createTextVNode$2(_toDisplayString$2(current.value.desc), 1)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$2(_component_VDivider),
        _createElementVNode$1("div", _hoisted_2$1, [
          _createElementVNode$1("nav", _hoisted_3$1, [
            _createVNode$2(_component_VList, {
              density: "comfortable",
              nav: "",
              class: "py-2"
            }, {
              default: _withCtx$2(() => [
                (_openBlock$2(), _createElementBlock$2(_Fragment$1, null, _renderList$1(modules, (item) => {
                  return _createVNode$2(_component_VListItem, {
                    key: item.key,
                    active: activeModule.value === item.key,
                    color: "primary",
                    rounded: "lg",
                    onClick: $event => (activeModule.value = item.key)
                  }, {
                    prepend: _withCtx$2(() => [
                      _createVNode$2(_component_VIcon, {
                        icon: item.icon
                      }, null, 8, ["icon"])
                    ]),
                    default: _withCtx$2(() => [
                      _createVNode$2(_component_VListItemTitle, null, {
                        default: _withCtx$2(() => [
                          _createTextVNode$2(_toDisplayString$2(item.title), 1)
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
          _createElementVNode$1("section", _hoisted_4$1, [
            (_unref$1(config).loading)
              ? (_openBlock$2(), _createBlock$2(_component_VProgressLinear, {
                  key: 0,
                  indeterminate: "",
                  color: "primary",
                  height: "2",
                  class: "mb-3"
                }))
              : _createCommentVNode$2("", true),
            (_unref$1(config).error)
              ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
                  key: 1,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3"
                }, {
                  default: _withCtx$2(() => [
                    _createTextVNode$2(_toDisplayString$2(_unref$1(config).error), 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode$2("", true),
            (activeModule.value === 'tg')
              ? (_openBlock$2(), _createBlock$2(ConfigTgPane, {
                  key: 2,
                  api: props.api,
                  "plugin-id": props.pluginId,
                  config: _unref$1(config)
                }, null, 8, ["api", "plugin-id", "config"]))
              : (activeModule.value === 'pan115')
                ? (_openBlock$2(), _createBlock$2(ConfigPan115Pane, {
                    key: 3,
                    api: props.api,
                    "plugin-id": props.pluginId,
                    config: _unref$1(config)
                  }, null, 8, ["api", "plugin-id", "config"]))
                : (activeModule.value === 'monitor')
                  ? (_openBlock$2(), _createBlock$2(ConfigMonitorPane, {
                      key: 4,
                      api: props.api,
                      "plugin-id": props.pluginId,
                      config: _unref$1(config)
                    }, null, 8, ["api", "plugin-id", "config"]))
                  : (activeModule.value === 'cache')
                    ? (_openBlock$2(), _createBlock$2(ConfigCachePane, {
                        key: 5,
                        api: props.api,
                        "plugin-id": props.pluginId,
                        config: _unref$1(config)
                      }, null, 8, ["api", "plugin-id", "config"]))
                    : (activeModule.value === 'forward')
                      ? (_openBlock$2(), _createBlock$2(ConfigForwardPane, {
                          key: 6,
                          api: props.api,
                          "plugin-id": props.pluginId,
                          config: _unref$1(config)
                        }, null, 8, ["api", "plugin-id", "config"]))
                      : (activeModule.value === 'p9')
                        ? (_openBlock$2(), _createBlock$2(ConfigP9Pane, {
                            key: 7,
                            api: props.api,
                            "plugin-id": props.pluginId,
                            config: _unref$1(config)
                          }, null, 8, ["api", "plugin-id", "config"]))
                        : _createCommentVNode$2("", true)
          ])
        ]),
        _createVNode$2(_component_VDivider),
        _createVNode$2(_component_VCardActions, null, {
          default: _withCtx$2(() => [
            _createVNode$2(_component_VSpacer),
            _createVNode$2(_component_VBtn, {
              variant: "text",
              onClick: _cache[2] || (_cache[2] = $event => (emit('close')))
            }, {
              default: _withCtx$2(() => [...(_cache[4] || (_cache[4] = [
                _createTextVNode$2("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode$2(_component_VBtn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-content-save-outline",
              onClick: _unref$1(config).saveConfig
            }, {
              default: _withCtx$2(() => [...(_cache[5] || (_cache[5] = [
                _createTextVNode$2(" 保存配置 ", -1)
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-9f3c533c"]]);

const {resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,withCtx:_withCtx$1,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,normalizeClass:_normalizeClass,Fragment:_Fragment,createElementBlock:_createElementBlock$1,renderList:_renderList,unref:_unref} = await importShared('vue');


const _hoisted_1$1 = { class: "tg-grid" };
const _hoisted_2 = { class: "tg-mono" };
const _hoisted_3 = {
  key: 0,
  class: "tg-warn"
};
const _hoisted_4 = { class: "tg-actions" };
const _hoisted_5 = { class: "tg-hits-tools" };
const _hoisted_6 = { class: "tg-nowrap tg-dim" };
const _hoisted_7 = { class: "tg-nowrap" };
const _hoisted_8 = { class: "tg-nowrap" };
const _hoisted_9 = { class: "tg-dim" };
const _hoisted_10 = { key: 0 };
const _hoisted_11 = { class: "tg-pager" };
const _hoisted_12 = { class: "tg-pager-info" };

const {computed,onMounted,onUnmounted,ref: ref$1,watch} = await importShared('vue');

/**
 * 插件详情页（运行详情）：TG / 115 / 缓存三张状态卡 + 监控与转发统计 +
 * 最近流水（监控 / 转发 可切换，分页 + 决策筛选 + 关键词搜索）+ 快捷操作。
 * 决策徽章显示中文文案（映射在 ./decision.js）。
 *
 * 数据只走一个聚合接口 ``/overview``（一次请求拿齐各模块状态与最近流水）：
 * 详情页是"总览"，逐个模块并发拉取既慢又容易半屏空白；后端对每个模块单独
 * 容错，某块失败只影响那块。
 *
 * 纪律（沿用全项目约定）：
 * - 模板/脚本用到的变量全部在 script setup 声明 ref；
 * - 重入保护只留在按钮处理器，内部 fetch 函数无保护；
 * - 操作完成后重新拉 overview，不用本地推测状态。
 */
const hitsPageSize = 10;                  // 详情页每页 10 条

const _sfc_main$1 = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  // 作为 MP 左侧「发现」分区的整页入口渲染时置 true（1.8.0）：
  // 整页没有"关闭"语义，隐藏关闭按钮；「设置」仍由外层弹出配置弹窗。
  appPage: { type: Boolean, default: false },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const loading = ref$1(false);
const busy = ref$1('');
const message = ref$1('');
const messageOk = ref$1(true);
const data = ref$1(null);

let refreshTimer = null;

function setMessage(text, ok = true) {
  message.value = text || '';
  messageOk.value = ok;
}

// ------------------------------------------------------------------ 数据加载（无重入保护）

async function loadOverview() {
  loading.value = true;
  try {
    data.value = unwrap(await getPluginApi(props.api, props.pluginId, 'overview', { timeoutMs: 15000 }));
  } catch (error) {
    setMessage(error?.message || '状态加载失败', false);
  } finally {
    loading.value = false;
  }
}

async function refreshAll() {
  setMessage('');
  await loadOverview();
}

// ------------------------------------------------------------------ 快捷操作

async function runAction(key, path, body, okText) {
  if (busy.value) return
  busy.value = key;
  setMessage('正在执行…');
  try {
    const response = unwrap(await postPluginApi(props.api, props.pluginId, path, body || {}, { timeoutMs: 60000 }));
    setMessage(response?.message || okText || '已完成');
    await loadOverview();
  } catch (error) {
    setMessage(error?.message || '操作失败', false);
  } finally {
    busy.value = '';
  }
}

function connectTg() {
  runAction('tg', 'telegram/connect', {}, 'TG 客户端已连接');
}

function refreshDialogs() {
  runAction('dialogs', 'telegram/refresh_dialogs', {}, '对话列表已刷新');
}

function checkPan115() {
  runAction('pan115', 'pan115/check', {}, '115 连接正常');
}

function syncCache() {
  runAction('cache', 'cache/sync', {}, '缓存同步已触发');
}

function checkSubscriptions() {
  runAction('subs', 'cache/check_subscriptions', {}, '订阅回搜已执行');
}

// ------------------------------------------------------------------ 展示辅助

const tg = computed(() => data.value?.tg || {});
const pan115 = computed(() => data.value?.pan115 || {});
const cache = computed(() => data.value?.cache || {});
const monitor = computed(() => data.value?.monitor || {});
const forward = computed(() => data.value?.forward || {});
const pipeline = computed(() => monitor.value.pipeline || {});
// 最近流水：监控 / 转发 两个来源，分页 + 筛选 + 搜索（与设置页同款交互）。
// 详情页之前走 overview 的 recent_hits 摘要（写死 10 条、无翻页），1.6.7 改为
// 直连 /monitor/hits 与 /forward/hits 分页接口，彻底去掉这个"锁"。
const hitTab = ref$1('monitor');            // 'monitor' | 'forward'
const hits = ref$1([]);
const hitsLoading = ref$1(false);
const hitsTotal = ref$1(0);
const hitsPage = ref$1(1);
const decisionFilter = ref$1('');
// 关键词用可写 computed 包一层：Vuetify clearable 清除会置 null，归一避免 .trim() 抛错
const hitKeywordRaw = ref$1('');
const hitKeyword = computed({
  get: () => String(hitKeywordRaw.value ?? ''),
  set: (value) => { hitKeywordRaw.value = value == null ? '' : String(value); },
});

// 决策下拉：value 用后端权威英文常量（与 /monitor/hits、/forward/hits 的 decision 过滤
// 参数完全一致，保证一定能筛到）；title 统一走 decisionLabel()，与流水「决策」徽章
// 逐字对齐（此前硬编的中文名与徽章对不上，导致用户选不准、以为筛不到）。
// 监控 / 转发各取各自实际会出现的取值集合。
const MONITOR_DECISION_VALUES = [
  'hit', 'skipped_not_missing', 'skipped_not_subscribed',
  'skipped_unrecognized', 'skipped_keyword', 'skipped_no_link',
  'skipped_unknown', 'skipped_extension', 'failed',
];
const FORWARD_DECISION_VALUES = ['hit', 'skipped_keyword', 'skipped_extension'];
const monitorDecisions = MONITOR_DECISION_VALUES.map(v => ({ value: v, title: decisionLabel(v) }));
const forwardDecisions = FORWARD_DECISION_VALUES.map(v => ({ value: v, title: decisionLabel(v) }));
const decisionOptions = computed(() => [
  { value: '', title: '全部决策' },
  ...(hitTab.value === 'forward' ? forwardDecisions : monitorDecisions),
]);

const hitsPath = computed(() => (hitTab.value === 'forward' ? 'forward/hits' : 'monitor/hits'));

async function loadHits() {
  hitsLoading.value = true;
  try {
    // 总数缩小时把越界页码夹回最后一页（轮询期间结果被删的场景）
    const maxPage = hitsTotal.value > 0
      ? Math.max(1, Math.ceil(hitsTotal.value / hitsPageSize))
      : 1;
    if (hitsPage.value > maxPage) hitsPage.value = maxPage;
    const params = new URLSearchParams();
    params.set('page', String(hitsPage.value));
    params.set('page_size', String(hitsPageSize));
    if (decisionFilter.value) params.set('decision', decisionFilter.value);
    if (hitKeyword.value.trim()) params.set('keyword', hitKeyword.value.trim());
    const res = unwrap(await getPluginApi(
      props.api, props.pluginId, `${hitsPath.value}?${params.toString()}`, { timeoutMs: 15000 },
    ));
    hits.value = res?.items || [];
    hitsTotal.value = res?.total || 0;
  } catch (error) {
    setMessage(error?.message || '流水加载失败', false);
    hits.value = [];
  } finally {
    hitsLoading.value = false;
  }
}

function onHitTabChange() {
  hitsPage.value = 1;
  decisionFilter.value = '';
  loadHits();
}

function onDecisionFilter() {
  hitsPage.value = 1;
  loadHits();
}

function prevHits() {
  if (hitsPage.value <= 1) return
  hitsPage.value -= 1;
  loadHits();
}

function nextHits() {
  if (hitsPage.value * hitsPageSize >= hitsTotal.value) return
  hitsPage.value += 1;
  loadHits();
}

// 关键词输入防抖 300ms：边打字边查会把后端打满（流水可能上万行）
let keywordTimer = null;
watch(hitKeyword, () => {
  clearTimeout(keywordTimer);
  keywordTimer = setTimeout(() => {
    hitsPage.value = 1;
    loadHits();
  }, 300);
});

// 来源会话 ID → 标题：合并监控与转发两个状态卡的 watched_detail（两 tab 共用一个映射）
const chatTitleMap = computed(() => {
  const map = {};
  for (const which of ['monitor', 'forward']) {
    const detail = data.value?.[which]?.pipeline?.watched_detail || [];
    for (const w of detail) {
      if (w.resolved && w.title) map[w.chat_id] = w.title;
    }
  }
  return map
});

const tgState = computed(() => {
  const item = tg.value;
  if (!item.api_configured) return { color: 'warning', text: '未配置 API' }
  if (item.connected && item.authorized) return { color: 'success', text: '已连接' }
  if (item.session_present) return { color: 'warning', text: '已登录但未连接' }
  return { color: 'error', text: '未登录' }
});

const pan115State = computed(() => {
  const item = pan115.value;
  if (!item.enabled) return { color: 'default', text: '未启用' }
  if (item.authorized) return { color: 'success', text: '已登录' }
  return { color: 'warning', text: '未登录' }
});

const cacheState = computed(() => {
  const item = cache.value;
  if (!item.enabled) return { color: 'default', text: '未启用' }
  if (item.sync?.running) return { color: 'info', text: '同步中' }
  return { color: 'success', text: '运行中' }
});

const pipelineState = computed(() => {
  if (!monitor.value.enabled && !forward.value.enabled) return { color: 'default', text: '未启用' }
  if (pipeline.value.running && pipeline.value.handler_registered) return { color: 'success', text: '运行中' }
  if (pipeline.value.running) return { color: 'warning', text: '运行中（监听未注册）' }
  return { color: 'warning', text: '未运行' }
});

function spaceLine() {
  const space = pan115.value.space || {};
  if (!space.total) return '—'
  return `${space.used || '?'} / ${space.total}`
}

function fmtTime(value) {
  return String(value || '').replace('T', ' ') || '—'
}

function mediaName(item) {
  if (!item.title) return '—'
  const year = item.year ? ` (${item.year})` : '';
  let name = `${item.title}${year}`;
  if (item.season || item.episode) {
    const s = String(item.season ?? 1).padStart(2, '0');
    const e = String(item.episode ?? 0).padStart(2, '0');
    const end = Number(item.episode_end ?? 0);
    // 多集区间（如 S01E05-E06）：结束集 > 起始集时拼区间
    if (end > (item.episode ?? 0)) {
      name += ` S${s}E${e}-E${String(end).padStart(2, '0')}`;
    } else {
      name += ` S${s}E${e}`;
    }
  }
  return name
}

onMounted(async () => {
  await Promise.all([loadOverview(), loadHits()]);
  // 轻量轮询：详情页常开着看状态，30 秒刷新一次；流水刷新保持当前页（不重置页码）
  refreshTimer = window.setInterval(() => {
    loadOverview();
    loadHits();
  }, 30000);
});

onUnmounted(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  if (keywordTimer) {
    window.clearTimeout(keywordTimer);
    keywordTimer = null;
  }
});

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VAvatar = _resolveComponent$1("VAvatar");
  const _component_VSpacer = _resolveComponent$1("VSpacer");
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VToolbar = _resolveComponent$1("VToolbar");
  const _component_VDivider = _resolveComponent$1("VDivider");
  const _component_VProgressLinear = _resolveComponent$1("VProgressLinear");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VCardTitle = _resolveComponent$1("VCardTitle");
  const _component_VCardItem = _resolveComponent$1("VCardItem");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VCard = _resolveComponent$1("VCard");
  const _component_VBtnToggle = _resolveComponent$1("VBtnToggle");
  const _component_VSelect = _resolveComponent$1("VSelect");
  const _component_VTextField = _resolveComponent$1("VTextField");
  const _component_VTable = _resolveComponent$1("VTable");

  return (_openBlock$1(), _createBlock$1(_component_VCard, {
    flat: "",
    class: "tg-page"
  }, {
    default: _withCtx$1(() => [
      _createVNode$1(_component_VToolbar, {
        density: "comfortable",
        class: "tg-toolbar"
      }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            rounded: "lg",
            class: "ms-3 me-2"
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VIcon, { icon: "mdi-send-circle-outline" })
            ]),
            _: 1
          }),
          _cache[7] || (_cache[7] = _createElementVNode("div", { class: "tg-heading" }, [
            _createElementVNode("div", { class: "text-h6" }, "胖虎媒体中心 · 运行详情"),
            _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, " TG 客户端 → 消息流水线 → 缓存 / 监控 / 转发 ")
          ], -1)),
          _createVNode$1(_component_VSpacer),
          (data.value?.plugin_version)
            ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                key: 0,
                size: "small",
                variant: "tonal",
                color: "primary",
                label: "",
                class: "me-2"
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(" v" + _toDisplayString$1(data.value.plugin_version), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode$1("", true),
          _createVNode$1(_component_VBtn, {
            variant: "text",
            size: "small",
            loading: loading.value,
            "prepend-icon": "mdi-refresh",
            onClick: refreshAll
          }, {
            default: _withCtx$1(() => [...(_cache[5] || (_cache[5] = [
              _createTextVNode$1(" 刷新 ", -1)
            ]))]),
            _: 1
          }, 8, ["loading"]),
          _createVNode$1(_component_VBtn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-cog-outline",
            onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
          }, {
            default: _withCtx$1(() => [...(_cache[6] || (_cache[6] = [
              _createTextVNode$1("设置", -1)
            ]))]),
            _: 1
          }),
          (!__props.appPage)
            ? (_openBlock$1(), _createBlock$1(_component_VBtn, {
                key: 1,
                icon: "",
                variant: "text",
                size: "small",
                onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
              }, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VIcon, { icon: "mdi-close" })
                ]),
                _: 1
              }))
            : _createCommentVNode$1("", true)
        ]),
        _: 1
      }),
      _createVNode$1(_component_VDivider),
      (loading.value)
        ? (_openBlock$1(), _createBlock$1(_component_VProgressLinear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            height: "2"
          }))
        : _createCommentVNode$1("", true),
      _createVNode$1(_component_VCardText, { class: "pa-3" }, {
        default: _withCtx$1(() => [
          (message.value)
            ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                key: 0,
                type: messageOk.value ? 'info' : 'warning',
                variant: "tonal",
                density: "compact",
                class: "mb-3"
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(_toDisplayString$1(message.value), 1)
                ]),
                _: 1
              }, 8, ["type"]))
            : _createCommentVNode$1("", true),
          _createElementVNode("div", _hoisted_1$1, [
            _createVNode$1(_component_VCard, {
              flat: "",
              class: "tg-card"
            }, {
              default: _withCtx$1(() => [
                _createVNode$1(_component_VCardItem, { density: "compact" }, {
                  prepend: _withCtx$1(() => [
                    _createVNode$1(_component_VIcon, {
                      icon: "mdi-send-outline",
                      size: "20"
                    })
                  ]),
                  append: _withCtx$1(() => [
                    _createVNode$1(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: tgState.value.color,
                      label: ""
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(tgState.value.text), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
                      default: _withCtx$1(() => [...(_cache[8] || (_cache[8] = [
                        _createTextVNode$1("TG 客户端", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_VCardText, { class: "tg-lines" }, {
                  default: _withCtx$1(() => [
                    _createElementVNode("div", null, [
                      _cache[9] || (_cache[9] = _createElementVNode("span", { class: "tg-key" }, "账号", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(tg.value.phone_masked || '未配置'), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[10] || (_cache[10] = _createElementVNode("span", { class: "tg-key" }, "监听会话", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(tg.value.dialog_count ?? 0) + " 个", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[11] || (_cache[11] = _createElementVNode("span", { class: "tg-key" }, "对话缓存", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(fmtTime(tg.value.dialogs_updated_at)), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[12] || (_cache[12] = _createElementVNode("span", { class: "tg-key" }, "全局冷却", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(tg.value.user_cooldown_seconds ?? 5) + " 秒 / 次", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[13] || (_cache[13] = _createElementVNode("span", { class: "tg-key" }, "FloodWait", -1)),
                      _createElementVNode("span", {
                        class: _normalizeClass({ 'tg-warn': (monitor.value.flood_remaining ?? 0) > 0 })
                      }, _toDisplayString$1((monitor.value.flood_remaining ?? 0) > 0 ? `退避中（约 ${monitor.value.flood_remaining} 秒）` : '无'), 3)
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode$1(_component_VCard, {
              flat: "",
              class: "tg-card"
            }, {
              default: _withCtx$1(() => [
                _createVNode$1(_component_VCardItem, { density: "compact" }, {
                  prepend: _withCtx$1(() => [
                    _createVNode$1(_component_VIcon, {
                      icon: "mdi-cloud-outline",
                      size: "20"
                    })
                  ]),
                  append: _withCtx$1(() => [
                    _createVNode$1(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: pan115State.value.color,
                      label: ""
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(pan115State.value.text), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
                      default: _withCtx$1(() => [...(_cache[14] || (_cache[14] = [
                        _createTextVNode$1("115 网盘", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_VCardText, { class: "tg-lines" }, {
                  default: _withCtx$1(() => [
                    _createElementVNode("div", null, [
                      _cache[15] || (_cache[15] = _createElementVNode("span", { class: "tg-key" }, "账号", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(pan115.value.account || '—'), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[16] || (_cache[16] = _createElementVNode("span", { class: "tg-key" }, "登录设备", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(pan115.value.login_device || '—'), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[17] || (_cache[17] = _createElementVNode("span", { class: "tg-key" }, "空间", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(spaceLine()), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[18] || (_cache[18] = _createElementVNode("span", { class: "tg-key" }, "转存目录", -1)),
                      _createElementVNode("span", _hoisted_2, _toDisplayString$1(pan115.value.target_cid || '默认根目录'), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[19] || (_cache[19] = _createElementVNode("span", { class: "tg-key" }, "上次检测", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(fmtTime(pan115.value.last_check)), 1)
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode$1(_component_VCard, {
              flat: "",
              class: "tg-card"
            }, {
              default: _withCtx$1(() => [
                _createVNode$1(_component_VCardItem, { density: "compact" }, {
                  prepend: _withCtx$1(() => [
                    _createVNode$1(_component_VIcon, {
                      icon: "mdi-database-outline",
                      size: "20"
                    })
                  ]),
                  append: _withCtx$1(() => [
                    _createVNode$1(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: cacheState.value.color,
                      label: ""
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(cacheState.value.text), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
                      default: _withCtx$1(() => [...(_cache[20] || (_cache[20] = [
                        _createTextVNode$1("消息缓存", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_VCardText, { class: "tg-lines" }, {
                  default: _withCtx$1(() => [
                    _createElementVNode("div", null, [
                      _cache[21] || (_cache[21] = _createElementVNode("span", { class: "tg-key" }, "缓存频道", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(cache.value.chats ?? 0) + " 个", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[22] || (_cache[22] = _createElementVNode("span", { class: "tg-key" }, "消息总数", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(cache.value.total ?? 0) + " 条", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[23] || (_cache[23] = _createElementVNode("span", { class: "tg-key" }, "最近同步", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(fmtTime(cache.value.sync?.finished_at || cache.value.sync?.started_at)), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[24] || (_cache[24] = _createElementVNode("span", { class: "tg-key" }, "订阅回搜", -1)),
                      _createElementVNode("span", null, [
                        _createTextVNode$1(_toDisplayString$1(cache.value.subscribe?.enabled === false ? '已关闭' : '已开启') + " ", 1),
                        (cache.value.subscribe?.last_check_at)
                          ? (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 0 }, [
                              _createTextVNode$1(" · 上次 " + _toDisplayString$1(fmtTime(cache.value.subscribe.last_check_at)) + " （新增 " + _toDisplayString$1(cache.value.subscribe.last_check_new ?? 0) + " / 推送 " + _toDisplayString$1(cache.value.subscribe.last_check_pushed ?? 0) + "） ", 1)
                            ], 64))
                          : _createCommentVNode$1("", true)
                      ])
                    ]),
                    (cache.value.subscribe?.last_error || cache.value.sync?.last_error)
                      ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_3, _toDisplayString$1(cache.value.subscribe?.last_error || cache.value.sync?.last_error), 1))
                      : _createCommentVNode$1("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode$1(_component_VCard, {
              flat: "",
              class: "tg-card"
            }, {
              default: _withCtx$1(() => [
                _createVNode$1(_component_VCardItem, { density: "compact" }, {
                  prepend: _withCtx$1(() => [
                    _createVNode$1(_component_VIcon, {
                      icon: "mdi-sitemap-outline",
                      size: "20"
                    })
                  ]),
                  append: _withCtx$1(() => [
                    _createVNode$1(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: pipelineState.value.color,
                      label: ""
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(pipelineState.value.text), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
                      default: _withCtx$1(() => [...(_cache[25] || (_cache[25] = [
                        _createTextVNode$1("消息流水线", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_VCardText, { class: "tg-lines" }, {
                  default: _withCtx$1(() => [
                    _createElementVNode("div", null, [
                      _cache[26] || (_cache[26] = _createElementVNode("span", { class: "tg-key" }, "监控规则", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(monitor.value.rules_count ?? 0) + " 条（关心 " + _toDisplayString$1(monitor.value.watched_chats ?? 0) + " 个会话）", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[27] || (_cache[27] = _createElementVNode("span", { class: "tg-key" }, "转发规则", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(forward.value.rules_count ?? 0) + " 条（关心 " + _toDisplayString$1(forward.value.watched_chats ?? 0) + " 个会话）", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[28] || (_cache[28] = _createElementVNode("span", { class: "tg-key" }, "累计处理", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(pipeline.value.processed ?? 0) + " 条 · 监控命中 " + _toDisplayString$1(pipeline.value.hit ?? 0) + " · 转发命中 " + _toDisplayString$1(pipeline.value.forward_hit ?? 0), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[29] || (_cache[29] = _createElementVNode("span", { class: "tg-key" }, "推送队列", -1)),
                      _createElementVNode("span", null, [
                        _createTextVNode$1("待处理 " + _toDisplayString$1(pipeline.value.push_pending ?? 0) + " · 成功 " + _toDisplayString$1(pipeline.value.push_done ?? 0) + " · 失败 ", 1),
                        _createElementVNode("span", {
                          class: _normalizeClass({ 'tg-warn': (pipeline.value.push_failed ?? 0) > 0 })
                        }, _toDisplayString$1(pipeline.value.push_failed ?? 0), 3)
                      ])
                    ]),
                    _createElementVNode("div", null, [
                      _cache[30] || (_cache[30] = _createElementVNode("span", { class: "tg-key" }, "最近事件", -1)),
                      _createElementVNode("span", null, _toDisplayString$1(fmtTime(pipeline.value.last_event_at)), 1)
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _createElementVNode("div", _hoisted_4, [
            _createVNode$1(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'tg',
              "prepend-icon": "mdi-connection",
              onClick: connectTg
            }, {
              default: _withCtx$1(() => [...(_cache[31] || (_cache[31] = [
                _createTextVNode$1(" 连接 TG ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode$1(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'dialogs',
              "prepend-icon": "mdi-account-multiple-outline",
              onClick: refreshDialogs
            }, {
              default: _withCtx$1(() => [...(_cache[32] || (_cache[32] = [
                _createTextVNode$1(" 刷新对话列表 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode$1(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'pan115',
              "prepend-icon": "mdi-cloud-check-outline",
              onClick: checkPan115
            }, {
              default: _withCtx$1(() => [...(_cache[33] || (_cache[33] = [
                _createTextVNode$1(" 检测 115 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode$1(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'cache',
              "prepend-icon": "mdi-sync",
              onClick: syncCache
            }, {
              default: _withCtx$1(() => [...(_cache[34] || (_cache[34] = [
                _createTextVNode$1(" 同步缓存 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode$1(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'subs',
              "prepend-icon": "mdi-magnify-scan",
              onClick: checkSubscriptions
            }, {
              default: _withCtx$1(() => [...(_cache[35] || (_cache[35] = [
                _createTextVNode$1(" 检查新增订阅 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"])
          ]),
          _createVNode$1(_component_VCard, {
            flat: "",
            class: "tg-card mt-3"
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VCardItem, { density: "compact" }, {
                append: _withCtx$1(() => [
                  _createVNode$1(_component_VBtnToggle, {
                    modelValue: hitTab.value,
                    "onUpdate:modelValue": [
                      _cache[2] || (_cache[2] = $event => ((hitTab).value = $event)),
                      onHitTabChange
                    ],
                    density: "comfortable",
                    variant: "outlined",
                    divided: "",
                    mandatory: ""
                  }, {
                    default: _withCtx$1(() => [
                      _createVNode$1(_component_VBtn, {
                        value: "monitor",
                        size: "small"
                      }, {
                        default: _withCtx$1(() => [...(_cache[37] || (_cache[37] = [
                          _createTextVNode$1("监控", -1)
                        ]))]),
                        _: 1
                      }),
                      _createVNode$1(_component_VBtn, {
                        value: "forward",
                        size: "small"
                      }, {
                        default: _withCtx$1(() => [...(_cache[38] || (_cache[38] = [
                          _createTextVNode$1("转发", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
                    default: _withCtx$1(() => [...(_cache[36] || (_cache[36] = [
                      _createTextVNode$1("最近流水", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode$1(_component_VCardText, null, {
                default: _withCtx$1(() => [
                  _createElementVNode("div", _hoisted_5, [
                    _createVNode$1(_component_VSelect, {
                      modelValue: decisionFilter.value,
                      "onUpdate:modelValue": [
                        _cache[3] || (_cache[3] = $event => ((decisionFilter).value = $event)),
                        onDecisionFilter
                      ],
                      items: decisionOptions.value,
                      "item-title": "title",
                      "item-value": "value",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      class: "tg-filter"
                    }, null, 8, ["modelValue", "items"]),
                    _createVNode$1(_component_VTextField, {
                      modelValue: hitKeyword.value,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((hitKeyword).value = $event)),
                      placeholder: "按片名 / 规则 / 说明搜索",
                      "prepend-inner-icon": "mdi-magnify",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      clearable: "",
                      class: "tg-hits-search"
                    }, null, 8, ["modelValue"])
                  ]),
                  _createVNode$1(_component_VTable, {
                    density: "compact",
                    class: "tg-hits"
                  }, {
                    default: _withCtx$1(() => [
                      _cache[40] || (_cache[40] = _createElementVNode("thead", null, [
                        _createElementVNode("tr", null, [
                          _createElementVNode("th", { class: "tg-nowrap" }, "时间"),
                          _createElementVNode("th", null, "规则"),
                          _createElementVNode("th", { class: "tg-nowrap" }, "来源"),
                          _createElementVNode("th", null, "媒体"),
                          _createElementVNode("th", { class: "tg-nowrap" }, "决策"),
                          _createElementVNode("th", null, "说明")
                        ])
                      ], -1)),
                      _createElementVNode("tbody", null, [
                        (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(hits.value, (item) => {
                          return (_openBlock$1(), _createElementBlock$1("tr", {
                            key: `${hitTab.value}-${item.id}`
                          }, [
                            _createElementVNode("td", _hoisted_6, _toDisplayString$1(fmtTime(item.created_at)), 1),
                            _createElementVNode("td", null, _toDisplayString$1(item.rule_name), 1),
                            _createElementVNode("td", _hoisted_7, _toDisplayString$1(chatTitleMap.value[item.chat_id] || item.chat_id), 1),
                            _createElementVNode("td", null, _toDisplayString$1(mediaName(item)), 1),
                            _createElementVNode("td", _hoisted_8, [
                              _createVNode$1(_component_VChip, {
                                size: "x-small",
                                variant: "tonal",
                                color: _unref(decisionColor)(item.decision),
                                label: ""
                              }, {
                                default: _withCtx$1(() => [
                                  _createTextVNode$1(_toDisplayString$1(_unref(decisionLabel)(item.decision)), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            _createElementVNode("td", _hoisted_9, _toDisplayString$1(item.detail), 1)
                          ]))
                        }), 128)),
                        (!hits.value.length)
                          ? (_openBlock$1(), _createElementBlock$1("tr", _hoisted_10, [...(_cache[39] || (_cache[39] = [
                              _createElementVNode("td", {
                                colspan: "6",
                                class: "tg-empty"
                              }, "暂无流水", -1)
                            ]))]))
                          : _createCommentVNode$1("", true)
                      ])
                    ]),
                    _: 1
                  }),
                  _createElementVNode("div", _hoisted_11, [
                    _createVNode$1(_component_VBtn, {
                      size: "small",
                      variant: "text",
                      disabled: hitsPage.value <= 1 || hitsLoading.value,
                      "prepend-icon": "mdi-chevron-left",
                      onClick: prevHits
                    }, {
                      default: _withCtx$1(() => [...(_cache[41] || (_cache[41] = [
                        _createTextVNode$1(" 上一页 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled"]),
                    _createElementVNode("span", _hoisted_12, "第 " + _toDisplayString$1(hitsPage.value) + " 页 · 共 " + _toDisplayString$1(hitsTotal.value) + " 条", 1),
                    _createVNode$1(_component_VBtn, {
                      size: "small",
                      variant: "text",
                      disabled: hitsPage.value * hitsPageSize >= hitsTotal.value || hitsLoading.value,
                      "append-icon": "mdi-chevron-right",
                      onClick: nextHits
                    }, {
                      default: _withCtx$1(() => [...(_cache[42] || (_cache[42] = [
                        _createTextVNode$1(" 下一页 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled"])
                  ]),
                  _cache[43] || (_cache[43] = _createElementVNode("div", { class: "tg-note" }, " 「来源」列与资源监控流水同口径：监听会话 ID 反查标题；完整流水与筛选在对应设置面板查看。 ", -1))
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
  }))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-d3d02447"]]);

const {openBlock:_openBlock,createBlock:_createBlock,resolveComponent:_resolveComponent,createCommentVNode:_createCommentVNode,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "tg-app-page" };

const {ref} = await importShared('vue');

/**
 * MP 左侧「发现」分区的整页入口（1.8.0）。
 *
 * 页面内容就是本插件的「运行详情 / 仪表盘」——直接复用 Page.vue，不另做一套
 * 页面；整页场景没有"关闭"语义，所以工具栏的「设置」按钮改为在这里弹出配置
 * 弹窗（与插件详情页同一份 Config.vue）。显示与否由后端 ``get_sidebar_nav()``
 * 依据配置项 ``discovery_page_enabled``（配置页顶部「发现页」开关）决定。
 *
 * 纪律（与项目其它页面一致）：
 * - 模板/脚本用到的变量全部在 script setup 声明 ref；
 * - 重入保护只留在按钮处理器，内部 fetch 无保护；
 * - 保存后重挂 Page（key 变化）重新拉一次运行详情，不本地推测状态。
 */

const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'TgMediaCenter' },
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
              onSave: saveSettings,
              onClose: _cache[0] || (_cache[0] = $event => (settingsDialog.value = false))
            }, null, 8, ["api", "plugin-id", "initial-config"]))
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
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-85bb49b9"]]);

export { AppPage as default };
