import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, F as FRONTEND_VERSION, u as unwrap, p as postPluginApi, a as getPluginApi } from './_plugin-vue_export-helper-Di38gPn5.js';

const {resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createVNode:_createVNode,createElementVNode:_createElementVNode,unref:_unref,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "sc-root" };
const _hoisted_2 = { class: "sc-top" };
const _hoisted_3 = { class: "sc-top-left" };
const _hoisted_4 = { class: "sc-logo" };
const _hoisted_5 = { class: "sc-top-text" };
const _hoisted_6 = { class: "sc-title" };
const _hoisted_7 = { class: "sc-top-actions" };
const _hoisted_8 = { class: "sc-stat-grid" };
const _hoisted_9 = { class: "sc-stat-top" };
const _hoisted_10 = { class: "sc-stat-label" };
const _hoisted_11 = { class: "sc-stat-value" };
const _hoisted_12 = { class: "sc-stat-sub" };
const _hoisted_13 = { class: "sc-sources" };
const _hoisted_14 = { class: "sc-source-head" };
const _hoisted_15 = { class: "sc-source-sub" };
const _hoisted_16 = {
  key: 0,
  class: "sc-error"
};
const _hoisted_17 = { class: "sc-card" };
const _hoisted_18 = { class: "sc-card-head" };
const _hoisted_19 = {
  key: 0,
  class: "sc-empty"
};
const _hoisted_20 = {
  key: 1,
  class: "sc-table"
};
const _hoisted_21 = { class: "sc-mono" };
const _hoisted_22 = { class: "sc-dim" };
const _hoisted_23 = { class: "sc-media" };
const _hoisted_24 = {
  key: 0,
  class: "sc-dim"
};
const _hoisted_25 = {
  key: 1,
  class: "sc-dim"
};
const _hoisted_26 = { class: "sc-dim" };
const _hoisted_27 = { class: "sc-dim sc-reason" };
const _hoisted_28 = {
  key: 2,
  class: "sc-pager"
};
const _hoisted_29 = { class: "sc-hint" };

const {computed,onMounted,onUnmounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'SubscribeCenter' },
  // 作为 MP 左侧「发现」分区的整页入口渲染时置 true：整页没有"关闭"语义，隐藏关闭按钮。
  appPage: { type: Boolean, default: false },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

/**
 * 详情页（插件管理里的弹窗 / 侧栏整页共用）。
 *
 * 展示运行状态、各数据源情况、最近流水，并提供「立即运行一次」。
 * 与仪表盘共用 /status 与 /history 接口。
 */
const props = __props;
const emit = __emit;

const loading = ref(false);
const busy = ref('');
const tip = ref({ show: false, ok: true, text: '' });
const status = ref(null);
const history = ref({ items: [], total: 0, page: 1, count: 20 });
const filter = ref('');

let refreshTimer = null;

const backendVersion = computed(() => String(status.value?.plugin_version || ''));
const versionMismatch = computed(() => {
  if (!backendVersion.value) return ''
  return backendVersion.value === FRONTEND_VERSION
    ? ''
    : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backendVersion.value}`
});

const DECISION_LABELS = {
  added: '新增订阅',
  skipped_dry_run: 'dry-run 跳过',
  skipped_first_run_dry: '首次试运行',
  skipped_already_subscribed: '已订阅',
  skipped_already_completed: '已完成过',
  skipped_duplicate: '跨源重复',
  skipped_rating: '评分不足',
  skipped_popularity: '关注度不足',
  skipped_out_of_window: '超出窗口',
  skipped_not_future: '定档已过',
  skipped_daily_limit: '触达上限',
  pending_review: '待确认',
  skipped_special: '特别篇（不处理）',
  skipped_finished: '已播完（跳过）',
  skipped_no_date: '无日期（跳过）',
  skipped_want: '想看不足（跳过）',
  skipped_source_disabled: '源未启用',
};

function decisionLabel(value) {
  return DECISION_LABELS[value] || value || '—'
}

function decisionColor(value) {
  if (value === 'added') return 'success'
  if (value === 'pending_review') return 'warning'
  if (String(value || '').startsWith('skipped')) return 'default'
  return 'default'
}

function setTip(text, ok = true) {
  tip.value = { show: true, ok, text };
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status'));
  } catch (error) {
    setTip(error?.message || '状态加载失败', false);
  }
}

async function loadHistory() {
  loading.value = true;
  try {
    const params = new URLSearchParams({
      page: String(history.value.page || 1),
      count: String(history.value.count || 20),
    });
    if (filter.value) params.set('decision', filter.value);
    history.value = unwrap(
      await getPluginApi(props.api, props.pluginId, `history?${params.toString()}`),
    );
  } catch (error) {
    setTip(error?.message || '流水加载失败', false);
  } finally {
    loading.value = false;
  }
}

async function refreshAll() {
  await Promise.all([loadStatus(), loadHistory()]);
}

async function runOnce() {
  if (busy.value) return
  busy.value = 'run';
  try {
    const result = unwrap(
      await postPluginApi(props.api, props.pluginId, 'run_once', {}, { timeoutMs: 600000 }),
    );
    if (result?.skipped) {
      setTip('已有发现任务正在运行，本次跳过');
    } else {
      const s = result?.summary || {};
      setTip(
        `本次完成：拉取 ${s.fetched ?? 0} 条 / 新增 ${s.added ?? 0} 条 / `
          + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`,
      );
    }
    await refreshAll();
  } catch (error) {
    setTip(error?.message || '运行失败', false);
  } finally {
    busy.value = '';
  }
}

function prevPage() {
  if (history.value.page <= 1) return
  history.value.page -= 1;
  loadHistory();
}

function nextPage() {
  const total = Number(history.value.total) || 0;
  const count = Number(history.value.count) || 20;
  if (history.value.page * count >= total) return
  history.value.page += 1;
  loadHistory();
}

/** 上次运行的详细数字（通知里只报新增，细节放这里看）。 */
const lastSummary = computed(() => status.value?.last_summary || null);

/** 顶部统计卡：状态一览。 */
const statCards = computed(() => {
  const s = status.value || {};
  const summary = lastSummary.value || {};
  const sources = s.sources || [];
  const enabledSources = sources.filter((row) => row.enabled);
  return [
    {
      icon: 'mdi-download-network-outline',
      label: '今日写入',
      value: `${s.written_today ?? 0}`,
      sub:
        s.daily_limit == null
          ? '上限未知'
          : Number(s.daily_limit) <= 0
            ? '不限条数'
            : `上限 ${s.daily_limit} 条`,
      color: 'primary',
    },
    {
      icon: 'mdi-radar',
      label: '数据源',
      value: `${enabledSources.length}/${sources.length}`,
      sub: s.enabled ? '插件已启用' : '插件未启用',
      color: s.enabled ? 'success' : 'warning',
    },
    {
      icon: 'mdi-plus-circle-outline',
      label: '上次新增',
      value: `${summary.added ?? 0}`,
      sub: summary.fetched != null ? `拉取 ${summary.fetched} 条` : '尚无运行记录',
      color: 'success',
    },
    {
      icon: 'mdi-clock-outline',
      label: '最近运行',
      value: s.last_run ? String(s.last_run).slice(11) : '—',
      sub: s.last_run ? String(s.last_run).slice(0, 10) : '从未运行',
      color: 'info',
    },
  ]
});

onMounted(() => {
  refreshAll();
  refreshTimer = setInterval(refreshAll, 30000);
});

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
});

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VSelect = _resolveComponent("VSelect");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (versionMismatch.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3",
          text: `${versionMismatch.value}：浏览器仍在用缓存的旧联邦组件。请按 Ctrl+Shift+R 硬刷新页面。`
        }, null, 8, ["text"]))
      : _createCommentVNode("", true),
    (tip.value.show)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: tip.value.ok ? 'success' : 'error',
          variant: "tonal",
          density: "compact",
          class: "mb-3",
          closable: "",
          text: tip.value.text,
          "onClick:close": _cache[0] || (_cache[0] = $event => (tip.value.show = false))
        }, null, 8, ["type", "text"]))
      : _createCommentVNode("", true),
    _createElementVNode("div", _hoisted_2, [
      _createElementVNode("div", _hoisted_3, [
        _createElementVNode("div", _hoisted_4, [
          _createVNode(_component_VIcon, {
            icon: "mdi-movie-open-star-outline",
            size: "20"
          })
        ]),
        _createElementVNode("div", _hoisted_5, [
          _createElementVNode("div", _hoisted_6, [
            _cache[4] || (_cache[4] = _createTextVNode(" 胖虎订阅中心 ", -1)),
            _createVNode(_component_VChip, {
              size: "x-small",
              variant: "flat",
              color: "primary",
              class: "ml-2"
            }, {
              default: _withCtx(() => [
                _createTextVNode(" v" + _toDisplayString(_unref(FRONTEND_VERSION)), 1)
              ]),
              _: 1
            })
          ]),
          _cache[5] || (_cache[5] = _createElementVNode("div", { class: "sc-subtitle" }, "发现片源 → 解析身份 → 去重 → 写订阅", -1))
        ])
      ]),
      _createElementVNode("div", _hoisted_7, [
        _createVNode(_component_VBtn, {
          color: "primary",
          size: "small",
          variant: "flat",
          "prepend-icon": "mdi-radar",
          loading: busy.value === 'run',
          onClick: runOnce
        }, {
          default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
            _createTextVNode(" 立即运行一次 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-refresh",
          loading: loading.value,
          onClick: refreshAll
        }, {
          default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
            _createTextVNode(" 刷新 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-cog",
          onClick: _cache[1] || (_cache[1] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
            _createTextVNode("设置", -1)
          ]))]),
          _: 1
        })
      ])
    ]),
    _createElementVNode("div", _hoisted_8, [
      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(statCards.value, (card) => {
        return (_openBlock(), _createElementBlock("div", {
          key: card.label,
          class: "sc-stat"
        }, [
          _createElementVNode("div", _hoisted_9, [
            _createVNode(_component_VIcon, {
              icon: card.icon,
              size: "17",
              color: card.color
            }, null, 8, ["icon", "color"]),
            _createElementVNode("span", _hoisted_10, _toDisplayString(card.label), 1)
          ]),
          _createElementVNode("div", _hoisted_11, _toDisplayString(card.value), 1),
          _createElementVNode("div", _hoisted_12, _toDisplayString(card.sub), 1)
        ]))
      }), 128))
    ]),
    _createElementVNode("div", _hoisted_13, [
      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((status.value?.sources || []), (s) => {
        return (_openBlock(), _createElementBlock("div", {
          key: s.source,
          class: "sc-source-chip"
        }, [
          _createElementVNode("div", _hoisted_14, [
            _createElementVNode("b", null, _toDisplayString(s.source), 1),
            _createVNode(_component_VChip, {
              size: "x-small",
              variant: "flat",
              color: s.enabled ? 'success' : 'default'
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(s.enabled ? '已启用' : '未启用'), 1)
              ]),
              _: 2
            }, 1032, ["color"]),
            (!s.implemented)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 0,
                  size: "x-small",
                  variant: "flat",
                  color: "warning"
                }, {
                  default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
                    _createTextVNode(" 未实现 ", -1)
                  ]))]),
                  _: 1
                }))
              : _createCommentVNode("", true)
          ]),
          _createElementVNode("div", _hoisted_15, " 最近 " + _toDisplayString(s.last_count) + " 条 · " + _toDisplayString(s.last_run || '从未运行'), 1),
          (s.last_error)
            ? (_openBlock(), _createElementBlock("div", _hoisted_16, "失败：" + _toDisplayString(s.last_error), 1))
            : _createCommentVNode("", true)
        ]))
      }), 128))
    ]),
    _createElementVNode("div", _hoisted_17, [
      _createElementVNode("div", _hoisted_18, [
        _cache[11] || (_cache[11] = _createElementVNode("span", { class: "sc-card-title" }, "发现流水", -1)),
        _createVNode(_component_VSelect, {
          modelValue: filter.value,
          "onUpdate:modelValue": [
            _cache[2] || (_cache[2] = $event => ((filter).value = $event)),
            _cache[3] || (_cache[3] = $event => {history.value.page = 1; loadHistory();})
          ],
          items: [{ title: '全部状态', value: '' }, ...Object.entries(DECISION_LABELS).map(([value, title]) => ({ title, value }))],
          density: "compact",
          "hide-details": "",
          variant: "outlined",
          style: {"max-width":"190px"}
        }, null, 8, ["modelValue", "items"]),
        _createVNode(_component_VChip, {
          size: "x-small",
          variant: "tonal"
        }, {
          default: _withCtx(() => [
            _createTextVNode("共 " + _toDisplayString(history.value.total) + " 部作品", 1)
          ]),
          _: 1
        }),
        _createVNode(_component_VChip, {
          size: "x-small",
          variant: "text"
        }, {
          default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
            _createTextVNode("每部只显示最新状态", -1)
          ]))]),
          _: 1
        })
      ]),
      (!history.value.items.length)
        ? (_openBlock(), _createElementBlock("div", _hoisted_19, " 还没有流水。点「立即运行一次」即可看到发现结果。 "))
        : (_openBlock(), _createElementBlock("div", _hoisted_20, [
            _cache[12] || (_cache[12] = _createElementVNode("div", { class: "sc-tr sc-tr-head" }, [
              _createElementVNode("span", null, "时间"),
              _createElementVNode("span", null, "来源"),
              _createElementVNode("span", null, "媒体"),
              _createElementVNode("span", null, "身份"),
              _createElementVNode("span", null, "决策"),
              _createElementVNode("span", null, "说明")
            ], -1)),
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value.items, (item, index) => {
              return (_openBlock(), _createElementBlock("div", {
                key: index,
                class: "sc-tr"
              }, [
                _createElementVNode("span", _hoisted_21, _toDisplayString(String(item.run_at || '').slice(5, 16)), 1),
                _createElementVNode("span", _hoisted_22, _toDisplayString(item.source), 1),
                _createElementVNode("span", _hoisted_23, [
                  _createElementVNode("b", null, _toDisplayString(item.title), 1),
                  (item.year)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_24, "(" + _toDisplayString(item.year) + ")", 1))
                    : _createCommentVNode("", true),
                  (item.media_type)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_25, _toDisplayString(item.media_type), 1))
                    : _createCommentVNode("", true)
                ]),
                _createElementVNode("span", _hoisted_26, _toDisplayString(item.confidence || '—'), 1),
                _createElementVNode("span", null, [
                  _createVNode(_component_VChip, {
                    size: "x-small",
                    variant: "flat",
                    color: decisionColor(item.decision)
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(decisionLabel(item.decision)), 1)
                    ]),
                    _: 2
                  }, 1032, ["color"])
                ]),
                _createElementVNode("span", _hoisted_27, _toDisplayString(item.reason || '—'), 1)
              ]))
            }), 128))
          ])),
      (history.value.total > history.value.count)
        ? (_openBlock(), _createElementBlock("div", _hoisted_28, [
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "text",
              disabled: history.value.page <= 1,
              onClick: prevPage
            }, {
              default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                _createTextVNode("上一页", -1)
              ]))]),
              _: 1
            }, 8, ["disabled"]),
            _createElementVNode("span", _hoisted_29, "第 " + _toDisplayString(history.value.page) + " 页 · 共 " + _toDisplayString(history.value.total) + " 部作品", 1),
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "text",
              disabled: history.value.page * history.value.count >= history.value.total,
              onClick: nextPage
            }, {
              default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                _createTextVNode(" 下一页 ", -1)
              ]))]),
              _: 1
            }, 8, ["disabled"])
          ]))
        : _createCommentVNode("", true)
    ])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-aad7b435"]]);

export { Page as default };
