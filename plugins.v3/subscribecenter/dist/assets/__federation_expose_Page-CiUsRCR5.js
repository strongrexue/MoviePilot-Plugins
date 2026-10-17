import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, F as FRONTEND_VERSION, u as unwrap, p as postPluginApi, a as getPluginApi } from './_plugin-vue_export-helper-BJogUCoJ.js';

const {resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "sc-root" };
const _hoisted_2 = { class: "sc-kv" };
const _hoisted_3 = { class: "sc-kv" };
const _hoisted_4 = { class: "sc-kv" };
const _hoisted_5 = { class: "sc-kv" };
const _hoisted_6 = { class: "sc-kv" };
const _hoisted_7 = { class: "sc-kv" };
const _hoisted_8 = { class: "sc-kv" };
const _hoisted_9 = { class: "sc-kv" };
const _hoisted_10 = { class: "sc-kv" };
const _hoisted_11 = { class: "d-flex align-center ga-2 flex-wrap" };
const _hoisted_12 = { class: "sc-hint" };
const _hoisted_13 = {
  key: 0,
  class: "sc-error"
};
const _hoisted_14 = { class: "d-flex flex-wrap ga-2 my-3" };
const _hoisted_15 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_16 = { class: "d-flex align-center flex-wrap ga-2" };
const _hoisted_17 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_18 = { class: "sc-hint" };
const _hoisted_19 = {
  key: 2,
  class: "sc-hint"
};
const _hoisted_20 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_21 = { class: "sc-hint mx-2" };

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
  skipped_out_of_window: '超出窗口',
  skipped_not_future: '定档已过',
  skipped_daily_limit: '触达上限',
  pending_review: '待确认',
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

onMounted(() => {
  refreshAll();
  refreshTimer = setInterval(refreshAll, 30000);
});

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
});

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCardActions = _resolveComponent("VCardActions");

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
    _createVNode(_component_VRow, { dense: "" }, {
      default: _withCtx(() => [
        _createVNode(_component_VCol, {
          cols: "12",
          md: "4"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCard, {
              variant: "tonal",
              class: "h-100"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                  default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                    _createTextVNode("运行状态", -1)
                  ]))]),
                  _: 1
                }),
                (status.value)
                  ? (_openBlock(), _createBlock(_component_VCardText, { key: 0 }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_2, [
                          _cache[6] || (_cache[6] = _createElementVNode("span", null, "插件版本", -1)),
                          _createElementVNode("b", null, "v" + _toDisplayString(status.value.plugin_version), 1)
                        ]),
                        _createElementVNode("div", _hoisted_3, [
                          _cache[7] || (_cache[7] = _createElementVNode("span", null, "启用", -1)),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            color: status.value.enabled ? 'success' : 'default',
                            variant: "flat"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(status.value.enabled ? '是' : '否'), 1)
                            ]),
                            _: 1
                          }, 8, ["color"])
                        ]),
                        _createElementVNode("div", _hoisted_4, [
                          _cache[8] || (_cache[8] = _createElementVNode("span", null, "dry-run", -1)),
                          _createElementVNode("b", null, _toDisplayString(status.value.dry_run ? '是（不写入）' : '否'), 1)
                        ]),
                        _createElementVNode("div", _hoisted_5, [
                          _cache[9] || (_cache[9] = _createElementVNode("span", null, "首次试运行", -1)),
                          _createElementVNode("b", null, _toDisplayString(status.value.first_run_completed ? '已完成' : '未完成（下次强制 dry-run）'), 1)
                        ]),
                        _createElementVNode("div", _hoisted_6, [
                          _cache[10] || (_cache[10] = _createElementVNode("span", null, "今日写入", -1)),
                          _createElementVNode("b", null, _toDisplayString(status.value.written_today) + " / " + _toDisplayString(status.value.daily_limit), 1)
                        ]),
                        _createElementVNode("div", _hoisted_7, [
                          _cache[11] || (_cache[11] = _createElementVNode("span", null, "时区", -1)),
                          _createElementVNode("b", null, _toDisplayString(status.value.timezone), 1)
                        ]),
                        _createElementVNode("div", _hoisted_8, [
                          _cache[12] || (_cache[12] = _createElementVNode("span", null, "最近运行", -1)),
                          _createElementVNode("b", null, _toDisplayString(status.value.last_run || '—'), 1)
                        ]),
                        _createElementVNode("div", _hoisted_9, [
                          _cache[13] || (_cache[13] = _createElementVNode("span", null, "映射缓存", -1)),
                          _createElementVNode("b", null, _toDisplayString(status.value.mapping_cache_size) + " 条", 1)
                        ]),
                        _createElementVNode("div", _hoisted_10, [
                          _cache[14] || (_cache[14] = _createElementVNode("span", null, "当前任务", -1)),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            color: status.value.busy ? 'warning' : 'default',
                            variant: "flat"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(status.value.busy ? '运行中' : '空闲'), 1)
                            ]),
                            _: 1
                          }, 8, ["color"])
                        ])
                      ]),
                      _: 1
                    }))
                  : (_openBlock(), _createBlock(_component_VCardText, {
                      key: 1,
                      class: "sc-hint"
                    }, {
                      default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                        _createTextVNode("状态加载中…", -1)
                      ]))]),
                      _: 1
                    }))
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VCol, {
          cols: "12",
          md: "8"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCard, {
              variant: "outlined",
              class: "h-100"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                  default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                    _createTextVNode("数据源", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardText, null, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((status.value?.sources || []), (s) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: s.source,
                        class: "sc-source"
                      }, [
                        _createElementVNode("div", _hoisted_11, [
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
                                default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
                                  _createTextVNode(" 当前版本未实现 ", -1)
                                ]))]),
                                _: 1
                              }))
                            : _createCommentVNode("", true),
                          _createElementVNode("span", _hoisted_12, "最近 " + _toDisplayString(s.last_count) + " 条 · " + _toDisplayString(s.last_run || '从未运行'), 1)
                        ]),
                        (s.last_error)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_13, "失败：" + _toDisplayString(s.last_error), 1))
                          : _createCommentVNode("", true)
                      ]))
                    }), 128))
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
    _createElementVNode("div", _hoisted_14, [
      _createVNode(_component_VBtn, {
        color: "primary",
        size: "small",
        "prepend-icon": "mdi-radar",
        loading: busy.value === 'run',
        onClick: runOnce
      }, {
        default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
          _createTextVNode(" 立即运行一次 ", -1)
        ]))]),
        _: 1
      }, 8, ["loading"]),
      _createVNode(_component_VBtn, {
        size: "small",
        variant: "tonal",
        "prepend-icon": "mdi-refresh",
        loading: loading.value,
        onClick: refreshAll
      }, {
        default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
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
        default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
          _createTextVNode("设置", -1)
        ]))]),
        _: 1
      }),
      (!__props.appPage)
        ? (_openBlock(), _createBlock(_component_VBtn, {
            key: 0,
            size: "small",
            variant: "text",
            "prepend-icon": "mdi-close",
            onClick: _cache[2] || (_cache[2] = $event => (emit('close')))
          }, {
            default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
              _createTextVNode(" 关闭 ", -1)
            ]))]),
            _: 1
          }))
        : _createCommentVNode("", true)
    ]),
    _createVNode(_component_VCard, { variant: "outlined" }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardTitle, { class: "d-flex align-center flex-wrap ga-2 text-subtitle-1" }, {
          default: _withCtx(() => [
            _cache[22] || (_cache[22] = _createElementVNode("span", null, "发现流水", -1)),
            _createVNode(_component_VSelect, {
              modelValue: filter.value,
              "onUpdate:modelValue": [
                _cache[3] || (_cache[3] = $event => ((filter).value = $event)),
                _cache[4] || (_cache[4] = $event => {history.value.page = 1; loadHistory();})
              ],
              items: [{ title: '全部', value: '' }, ...Object.entries(DECISION_LABELS).map(([value, title]) => ({ title, value }))],
              density: "compact",
              "hide-details": "",
              style: {"max-width":"180px"}
            }, null, 8, ["modelValue", "items"]),
            _createVNode(_component_VChip, {
              size: "x-small",
              variant: "tonal"
            }, {
              default: _withCtx(() => [
                _createTextVNode("共 " + _toDisplayString(history.value.total) + " 条", 1)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VCardText, null, {
          default: _withCtx(() => [
            (!history.value.items.length)
              ? (_openBlock(), _createElementBlock("div", _hoisted_15, " 还没有流水。插件启用后点「立即运行一次」即可看到发现结果。 "))
              : _createCommentVNode("", true),
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value.items, (item, index) => {
              return (_openBlock(), _createElementBlock("div", {
                key: index,
                class: "sc-row"
              }, [
                _createElementVNode("div", _hoisted_16, [
                  _createVNode(_component_VChip, {
                    size: "x-small",
                    variant: "flat",
                    color: decisionColor(item.decision)
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(decisionLabel(item.decision)), 1)
                    ]),
                    _: 2
                  }, 1032, ["color"]),
                  _createElementVNode("b", null, _toDisplayString(item.title), 1),
                  (item.year)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_17, "(" + _toDisplayString(item.year) + ")", 1))
                    : _createCommentVNode("", true),
                  _createElementVNode("span", _hoisted_18, _toDisplayString(item.source), 1),
                  (item.confidence)
                    ? (_openBlock(), _createBlock(_component_VChip, {
                        key: 1,
                        size: "x-small",
                        variant: "text"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("身份 " + _toDisplayString(item.confidence), 1)
                        ]),
                        _: 2
                      }, 1024))
                    : _createCommentVNode("", true),
                  (item.release_date)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_19, "放送 " + _toDisplayString(item.release_date), 1))
                    : _createCommentVNode("", true)
                ]),
                (item.reason)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_20, _toDisplayString(item.reason), 1))
                  : _createCommentVNode("", true)
              ]))
            }), 128))
          ]),
          _: 1
        }),
        (history.value.total > history.value.count)
          ? (_openBlock(), _createBlock(_component_VCardActions, {
              key: 0,
              class: "justify-center"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  disabled: history.value.page <= 1,
                  onClick: prevPage
                }, {
                  default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                    _createTextVNode("上一页", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createElementVNode("span", _hoisted_21, "第 " + _toDisplayString(history.value.page) + " 页 · 共 " + _toDisplayString(history.value.total) + " 条", 1),
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  disabled: history.value.page * history.value.count >= history.value.total,
                  onClick: nextPage
                }, {
                  default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                    _createTextVNode(" 下一页 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"])
              ]),
              _: 1
            }))
          : _createCommentVNode("", true)
      ]),
      _: 1
    })
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-7cb18dc5"]]);

export { Page as default };
