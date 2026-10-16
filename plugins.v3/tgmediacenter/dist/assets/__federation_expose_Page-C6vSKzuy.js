import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, d as decisionLabel, b as decisionColor, u as unwrap, a as getPluginApi, p as postPluginApi } from './decision-Cpnhqhp6.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass,Fragment:_Fragment,createElementBlock:_createElementBlock,renderList:_renderList,unref:_unref} = await importShared('vue');


const _hoisted_1 = { class: "tg-grid" };
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

const {computed,onMounted,onUnmounted,ref,watch} = await importShared('vue');

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

const _sfc_main = {
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

const loading = ref(false);
const busy = ref('');
const message = ref('');
const messageOk = ref(true);
const data = ref(null);

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

async function startBackfill() {
  if (busy.value) return
  busy.value = 'backfill';
  setMessage('正在启动增量补扫…');
  try {
    const response = unwrap(await postPluginApi(
      props.api, props.pluginId, 'cache/backfill/start', { full: false },
      { timeoutMs: 30000 },
    ));
    setMessage(response?.message || (response?.started ? '补扫已启动' : '补扫未启动'), Boolean(response?.started));
    await loadOverview();
  } catch (error) {
    setMessage(error?.message || '启动补扫失败', false);
  } finally {
    busy.value = '';
  }
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
const hitTab = ref('monitor');            // 'monitor' | 'forward'
const hits = ref([]);
const hitsLoading = ref(false);
const hitsTotal = ref(0);
const hitsPage = ref(1);
const decisionFilter = ref('');
// 关键词用可写 computed 包一层：Vuetify clearable 清除会置 null，归一避免 .trim() 抛错
const hitKeywordRaw = ref('');
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
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VBtnToggle = _resolveComponent("VBtnToggle");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VTable = _resolveComponent("VTable");

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
          _cache[7] || (_cache[7] = _createElementVNode("div", { class: "tg-heading" }, [
            _createElementVNode("div", { class: "text-h6" }, "胖虎媒体中心 · 运行详情"),
            _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, " TG 客户端 → 消息流水线 → 缓存 / 监控 / 转发 ")
          ], -1)),
          _createVNode(_component_VSpacer),
          (data.value?.plugin_version)
            ? (_openBlock(), _createBlock(_component_VChip, {
                key: 0,
                size: "small",
                variant: "tonal",
                color: "primary",
                label: "",
                class: "me-2"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(" v" + _toDisplayString(data.value.plugin_version), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          _createVNode(_component_VBtn, {
            variant: "text",
            size: "small",
            loading: loading.value,
            "prepend-icon": "mdi-refresh",
            onClick: refreshAll
          }, {
            default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
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
            default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
              _createTextVNode("设置", -1)
            ]))]),
            _: 1
          }),
          (!__props.appPage)
            ? (_openBlock(), _createBlock(_component_VBtn, {
                key: 1,
                icon: "",
                variant: "text",
                size: "small",
                onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VIcon, { icon: "mdi-close" })
                ]),
                _: 1
              }))
            : _createCommentVNode("", true)
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
          (message.value)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 0,
                type: messageOk.value ? 'info' : 'warning',
                variant: "tonal",
                density: "compact",
                class: "mb-3"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(message.value), 1)
                ]),
                _: 1
              }, 8, ["type"]))
            : _createCommentVNode("", true),
          _createElementVNode("div", _hoisted_1, [
            _createVNode(_component_VCard, {
              flat: "",
              class: "tg-card"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardItem, { density: "compact" }, {
                  prepend: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-send-outline",
                      size: "20"
                    })
                  ]),
                  append: _withCtx(() => [
                    _createVNode(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: tgState.value.color,
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(tgState.value.text), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  default: _withCtx(() => [
                    _createVNode(_component_VCardTitle, { class: "text-subtitle-2" }, {
                      default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                        _createTextVNode("TG 客户端", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardText, { class: "tg-lines" }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", null, [
                      _cache[9] || (_cache[9] = _createElementVNode("span", { class: "tg-key" }, "账号", -1)),
                      _createElementVNode("span", null, _toDisplayString(tg.value.phone_masked || '未配置'), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[10] || (_cache[10] = _createElementVNode("span", { class: "tg-key" }, "监听会话", -1)),
                      _createElementVNode("span", null, _toDisplayString(tg.value.dialog_count ?? 0) + " 个", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[11] || (_cache[11] = _createElementVNode("span", { class: "tg-key" }, "对话缓存", -1)),
                      _createElementVNode("span", null, _toDisplayString(fmtTime(tg.value.dialogs_updated_at)), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[12] || (_cache[12] = _createElementVNode("span", { class: "tg-key" }, "全局冷却", -1)),
                      _createElementVNode("span", null, _toDisplayString(tg.value.user_cooldown_seconds ?? 5) + " 秒 / 次", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[13] || (_cache[13] = _createElementVNode("span", { class: "tg-key" }, "FloodWait", -1)),
                      _createElementVNode("span", {
                        class: _normalizeClass({ 'tg-warn': (monitor.value.flood_remaining ?? 0) > 0 })
                      }, _toDisplayString((monitor.value.flood_remaining ?? 0) > 0 ? `退避中（约 ${monitor.value.flood_remaining} 秒）` : '无'), 3)
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCard, {
              flat: "",
              class: "tg-card"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardItem, { density: "compact" }, {
                  prepend: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-cloud-outline",
                      size: "20"
                    })
                  ]),
                  append: _withCtx(() => [
                    _createVNode(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: pan115State.value.color,
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(pan115State.value.text), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  default: _withCtx(() => [
                    _createVNode(_component_VCardTitle, { class: "text-subtitle-2" }, {
                      default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                        _createTextVNode("115 网盘", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardText, { class: "tg-lines" }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", null, [
                      _cache[15] || (_cache[15] = _createElementVNode("span", { class: "tg-key" }, "账号", -1)),
                      _createElementVNode("span", null, _toDisplayString(pan115.value.account || '—'), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[16] || (_cache[16] = _createElementVNode("span", { class: "tg-key" }, "登录设备", -1)),
                      _createElementVNode("span", null, _toDisplayString(pan115.value.login_device || '—'), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[17] || (_cache[17] = _createElementVNode("span", { class: "tg-key" }, "空间", -1)),
                      _createElementVNode("span", null, _toDisplayString(spaceLine()), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[18] || (_cache[18] = _createElementVNode("span", { class: "tg-key" }, "转存目录", -1)),
                      _createElementVNode("span", _hoisted_2, _toDisplayString(pan115.value.target_cid || '默认根目录'), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[19] || (_cache[19] = _createElementVNode("span", { class: "tg-key" }, "上次检测", -1)),
                      _createElementVNode("span", null, _toDisplayString(fmtTime(pan115.value.last_check)), 1)
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCard, {
              flat: "",
              class: "tg-card"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardItem, { density: "compact" }, {
                  prepend: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-database-outline",
                      size: "20"
                    })
                  ]),
                  append: _withCtx(() => [
                    _createVNode(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: cacheState.value.color,
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(cacheState.value.text), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  default: _withCtx(() => [
                    _createVNode(_component_VCardTitle, { class: "text-subtitle-2" }, {
                      default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                        _createTextVNode("消息缓存", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardText, { class: "tg-lines" }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", null, [
                      _cache[21] || (_cache[21] = _createElementVNode("span", { class: "tg-key" }, "缓存频道", -1)),
                      _createElementVNode("span", null, _toDisplayString(cache.value.chats ?? 0) + " 个", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[22] || (_cache[22] = _createElementVNode("span", { class: "tg-key" }, "消息总数", -1)),
                      _createElementVNode("span", null, _toDisplayString(cache.value.total ?? 0) + " 条", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[23] || (_cache[23] = _createElementVNode("span", { class: "tg-key" }, "最近同步", -1)),
                      _createElementVNode("span", null, _toDisplayString(fmtTime(cache.value.sync?.finished_at || cache.value.sync?.started_at)), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[24] || (_cache[24] = _createElementVNode("span", { class: "tg-key" }, "订阅回搜", -1)),
                      _createElementVNode("span", null, [
                        _createTextVNode(_toDisplayString(cache.value.subscribe?.enabled === false ? '已关闭' : '已开启') + " ", 1),
                        (cache.value.subscribe?.last_check_at)
                          ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                              _createTextVNode(" · 上次 " + _toDisplayString(fmtTime(cache.value.subscribe.last_check_at)) + " （新增 " + _toDisplayString(cache.value.subscribe.last_check_new ?? 0) + " / 推送 " + _toDisplayString(cache.value.subscribe.last_check_pushed ?? 0) + "） ", 1)
                            ], 64))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    (cache.value.subscribe?.last_error || cache.value.sync?.last_error)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_3, _toDisplayString(cache.value.subscribe?.last_error || cache.value.sync?.last_error), 1))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCard, {
              flat: "",
              class: "tg-card"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardItem, { density: "compact" }, {
                  prepend: _withCtx(() => [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-sitemap-outline",
                      size: "20"
                    })
                  ]),
                  append: _withCtx(() => [
                    _createVNode(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: pipelineState.value.color,
                      label: ""
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(pipelineState.value.text), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  default: _withCtx(() => [
                    _createVNode(_component_VCardTitle, { class: "text-subtitle-2" }, {
                      default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                        _createTextVNode("消息流水线", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardText, { class: "tg-lines" }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", null, [
                      _cache[26] || (_cache[26] = _createElementVNode("span", { class: "tg-key" }, "监控规则", -1)),
                      _createElementVNode("span", null, _toDisplayString(monitor.value.rules_count ?? 0) + " 条（关心 " + _toDisplayString(monitor.value.watched_chats ?? 0) + " 个会话）", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[27] || (_cache[27] = _createElementVNode("span", { class: "tg-key" }, "转发规则", -1)),
                      _createElementVNode("span", null, _toDisplayString(forward.value.rules_count ?? 0) + " 条（关心 " + _toDisplayString(forward.value.watched_chats ?? 0) + " 个会话）", 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[28] || (_cache[28] = _createElementVNode("span", { class: "tg-key" }, "累计处理", -1)),
                      _createElementVNode("span", null, _toDisplayString(pipeline.value.processed ?? 0) + " 条 · 监控命中 " + _toDisplayString(pipeline.value.hit ?? 0) + " · 转发命中 " + _toDisplayString(pipeline.value.forward_hit ?? 0), 1)
                    ]),
                    _createElementVNode("div", null, [
                      _cache[29] || (_cache[29] = _createElementVNode("span", { class: "tg-key" }, "推送队列", -1)),
                      _createElementVNode("span", null, [
                        _createTextVNode("待处理 " + _toDisplayString(pipeline.value.push_pending ?? 0) + " · 成功 " + _toDisplayString(pipeline.value.push_done ?? 0) + " · 失败 ", 1),
                        _createElementVNode("span", {
                          class: _normalizeClass({ 'tg-warn': (pipeline.value.push_failed ?? 0) > 0 })
                        }, _toDisplayString(pipeline.value.push_failed ?? 0), 3)
                      ])
                    ]),
                    _createElementVNode("div", null, [
                      _cache[30] || (_cache[30] = _createElementVNode("span", { class: "tg-key" }, "最近事件", -1)),
                      _createElementVNode("span", null, _toDisplayString(fmtTime(pipeline.value.last_event_at)), 1)
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _createElementVNode("div", _hoisted_4, [
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'tg',
              "prepend-icon": "mdi-connection",
              onClick: connectTg
            }, {
              default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                _createTextVNode(" 连接 TG ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'dialogs',
              "prepend-icon": "mdi-account-multiple-outline",
              onClick: refreshDialogs
            }, {
              default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                _createTextVNode(" 刷新对话列表 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'pan115',
              "prepend-icon": "mdi-cloud-check-outline",
              onClick: checkPan115
            }, {
              default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                _createTextVNode(" 检测 115 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'cache',
              "prepend-icon": "mdi-sync",
              onClick: syncCache
            }, {
              default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                _createTextVNode(" 同步缓存 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "tonal",
              loading: busy.value === 'backfill',
              disabled: Boolean(cache.value?.backfill?.running),
              "prepend-icon": "mdi-refresh-circle",
              onClick: startBackfill
            }, {
              default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                _createTextVNode(" 立即增量补扫 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "disabled"])
          ]),
          _createVNode(_component_VCard, {
            flat: "",
            class: "tg-card mt-3"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardItem, { density: "compact" }, {
                append: _withCtx(() => [
                  _createVNode(_component_VBtnToggle, {
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
                    default: _withCtx(() => [
                      _createVNode(_component_VBtn, {
                        value: "monitor",
                        size: "small"
                      }, {
                        default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
                          _createTextVNode("监控", -1)
                        ]))]),
                        _: 1
                      }),
                      _createVNode(_component_VBtn, {
                        value: "forward",
                        size: "small"
                      }, {
                        default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                          _createTextVNode("转发", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                default: _withCtx(() => [
                  _createVNode(_component_VCardTitle, { class: "text-subtitle-2" }, {
                    default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                      _createTextVNode("最近流水", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_VCardText, null, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_5, [
                    _createVNode(_component_VSelect, {
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
                    _createVNode(_component_VTextField, {
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
                  _createVNode(_component_VTable, {
                    density: "compact",
                    class: "tg-hits"
                  }, {
                    default: _withCtx(() => [
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
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(hits.value, (item) => {
                          return (_openBlock(), _createElementBlock("tr", {
                            key: `${hitTab.value}-${item.id}`
                          }, [
                            _createElementVNode("td", _hoisted_6, _toDisplayString(fmtTime(item.created_at)), 1),
                            _createElementVNode("td", null, _toDisplayString(item.rule_name), 1),
                            _createElementVNode("td", _hoisted_7, _toDisplayString(chatTitleMap.value[item.chat_id] || item.chat_id), 1),
                            _createElementVNode("td", null, _toDisplayString(mediaName(item)), 1),
                            _createElementVNode("td", _hoisted_8, [
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                variant: "tonal",
                                color: _unref(decisionColor)(item.decision),
                                label: ""
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(_unref(decisionLabel)(item.decision)), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            _createElementVNode("td", _hoisted_9, _toDisplayString(item.detail), 1)
                          ]))
                        }), 128)),
                        (!hits.value.length)
                          ? (_openBlock(), _createElementBlock("tr", _hoisted_10, [...(_cache[39] || (_cache[39] = [
                              _createElementVNode("td", {
                                colspan: "6",
                                class: "tg-empty"
                              }, "暂无流水", -1)
                            ]))]))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    _: 1
                  }),
                  _createElementVNode("div", _hoisted_11, [
                    _createVNode(_component_VBtn, {
                      size: "small",
                      variant: "text",
                      disabled: hitsPage.value <= 1 || hitsLoading.value,
                      "prepend-icon": "mdi-chevron-left",
                      onClick: prevHits
                    }, {
                      default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
                        _createTextVNode(" 上一页 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["disabled"]),
                    _createElementVNode("span", _hoisted_12, "第 " + _toDisplayString(hitsPage.value) + " 页 · 共 " + _toDisplayString(hitsTotal.value) + " 条", 1),
                    _createVNode(_component_VBtn, {
                      size: "small",
                      variant: "text",
                      disabled: hitsPage.value * hitsPageSize >= hitsTotal.value || hitsLoading.value,
                      "append-icon": "mdi-chevron-right",
                      onClick: nextHits
                    }, {
                      default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
                        _createTextVNode(" 下一页 ", -1)
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
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-d7fb2648"]]);

export { Page as default };
