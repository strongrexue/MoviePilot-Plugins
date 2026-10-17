import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, F as FRONTEND_VERSION, g as getPluginConfig, u as unwrap, a as getPluginApi, s as savePluginConfig, p as postPluginApi } from './_plugin-vue_export-helper-B74nptcZ.js';

/**
 * 插件默认配置（前端快照）。
 *
 * ⚠️ 键集合必须与后端 `core/constants.py` 的 `default_config()` **严格一致**。
 * 宿主 `update_config()` 是整份覆盖：任一侧多一个键或少一个键，保存配置时
 * 都会被静默清掉。`tests/v3/subscribecenter/test_subscribecenter_plugin.py`
 * 对此设了回归锁（test_default_config_key_set_matches_frontend）。
 */
const configDefaults = {
  enabled: false,
  // ---------------- 数据源开关
  enable_tmdb: true,
  enable_bangumi: false,
  enable_douban_rss: false,
  enable_simkl: false,
  enable_justwatch: false,
  // ---------------- 发现窗口与阈值
  tmdb_future_days: 8,
  bangumi_future_days: 8,
  min_rating_tmdb: 6.0,
  min_rating_bangumi: 6.0,
  min_rating_douban: 6.0,
  min_rating_simkl: 6.0,
  min_popularity: 8.0,
  //: 是否只保留指定原始语言的条目
  filter_original_language: true,
  tmdb_original_languages: 'zh,ja,ko,en',
  // ---------------- 豆瓣 RSS 源列表
  douban_rss_sources: [],
  // ---------------- Simkl
  simkl_client_id: '',
  // ---------------- 写入
  daily_limit: 30,
  dry_run: false,
  // ---------------- 调度与通知
  cron: '0 3 * * *',
  timezone: 'Asia/Shanghai',
  notify: false,
  // ---------------- 界面
  discovery_page_enabled: false,
  // ---------------- 测试辅助
  //: 一次性开关：保存配置时把「今日已写入条数」清零，便于同一天反复测试
  reset_daily_counter: false,
  // ---------------- 一次性执行
  onlyonce: false,
};

/** 返回默认配置的深拷贝（避免多处共享同一份可变对象）。 */
function defaultConfig() {
  return JSON.parse(JSON.stringify(configDefaults))
}

const {resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,unref:_unref,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,createVNode:_createVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "sc-root" };
const _hoisted_2 = { class: "sc-hint ml-10" };
const _hoisted_3 = {
  key: 0,
  class: "sc-warn"
};
const _hoisted_4 = { class: "d-flex flex-wrap ga-2" };

const {computed,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'SubscribeCenter' },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

/**
 * 配置页。
 *
 * 设计要点：
 * - 表单值与后端 `default_config()` 键集合严格一致（宿主的保存是**整份覆盖**，
 *   少一个键就会被静默清掉）；
 * - 保存走两条路：emit('save') 交给宿主编排，同时自己 PUT 一次兜底 ——
 *   宿主在不同挂载方式下对 save 事件的处理不一致（参考 embycovercenter 的结论），
 *   自持保存能保证「点了保存就一定落库」；
 * - 顶部显示前端/后端版本号，不一致时明确提示硬刷新（remoteEntry.js 无哈希）。
 */
const props = __props;
const emit = __emit;

const form = ref(defaultConfig());
const loading = ref(false);
const busy = ref('');
const status = ref(null);
const tip = ref({ show: false, ok: true, text: '' });

/** 后端版本号；与前端不一致时提示硬刷新。 */
const backendVersion = computed(() => String(status.value?.plugin_version || ''));
const versionMismatch = computed(() => {
  if (!backendVersion.value) return ''
  return backendVersion.value === FRONTEND_VERSION
    ? ''
    : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backendVersion.value}`
});

/** 已实现的数据源（其余源在当前版本会在日志里明确跳过）。 */
const IMPLEMENTED = ['tmdb'];

const sourceRows = [
  { key: 'enable_tmdb', label: 'TMDB', hint: '核心定档源，自带 TMDB ID（当前唯一已实现）' },
  { key: 'enable_bangumi', label: 'Bangumi', hint: '日番 / 中文元数据（尚未实现）' },
  { key: 'enable_douban_rss', label: '豆瓣 RSS', hint: '需自建 RSSHub（尚未实现）' },
  { key: 'enable_simkl', label: 'Simkl Calendar', hint: '未来 33 天 TV + 动画 + 电影（尚未实现）' },
  { key: 'enable_justwatch', label: 'JustWatch', hint: '溪流媒体上线发现，只记日志（尚未实现）' },
];

function setTip(text, ok = true) {
  tip.value = { show: true, ok, text };
}

function mergeConfig(value) {
  const base = defaultConfig();
  if (value && typeof value === 'object') {
    for (const key of Object.keys(base)) {
      if (value[key] !== undefined && value[key] !== null) base[key] = value[key];
    }
  }
  return base
}

function buildPayload() {
  // 只提交 default_config 里声明过的键，避免把宿主的其它数据带回去
  const payload = {};
  for (const key of Object.keys(defaultConfig())) payload[key] = form.value[key];
  return payload
}

function cronValid() {
  return String(form.value.cron || '').trim().split(/\s+/).length === 5
}

async function loadConfig() {
  loading.value = true;
  try {
    const value = await getPluginConfig(props.api, props.pluginId);
    form.value = mergeConfig(value && Object.keys(value).length ? value : props.initialConfig);
  } catch (error) {
    form.value = mergeConfig(props.initialConfig);
    setTip(error?.message || '配置读取失败', false);
  } finally {
    loading.value = false;
  }
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status'));
  } catch (error) {
    // 状态失败不影响保存配置，只在控制台留痕
    console.warn('[SubscribeCenter] 状态读取失败：', error?.message || error);
  }
}

async function save() {
  if (busy.value) return
  if (!cronValid()) {
    setTip('cron 必须是 5 段式（分 时 日 月 周），例如 0 3 * * *', false);
    return
  }
  busy.value = 'save';
  try {
    const payload = buildPayload();
    // 两条路都走：宿主编排 + 自持保存
    emit('save', payload);
    await savePluginConfig(props.api, props.pluginId, payload);
    setTip('设置已保存');
    await loadStatus();
  } catch (error) {
    setTip(error?.message || '保存失败', false);
  } finally {
    busy.value = '';
  }
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
          + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`
          + (s.dry_run ? '（dry-run，未写入）' : ''),
      );
    }
    await loadStatus();
  } catch (error) {
    setTip(error?.message || '运行失败', false);
  } finally {
    busy.value = '';
  }
}

onMounted(() => {
  loadConfig();
  loadStatus();
});

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VBtn = _resolveComponent("VBtn");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (versionMismatch.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3",
          text: `${versionMismatch.value}：浏览器仍在用缓存的旧联邦组件。请按 Ctrl+Shift+R 硬刷新页面后再操作。`
        }, null, 8, ["text"]))
      : _createCommentVNode("", true),
    (tip.value.show)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: tip.value.ok ? 'success' : 'error',
          variant: "tonal",
          density: "compact",
          class: "mb-3",
          text: tip.value.text
        }, null, 8, ["type", "text"]))
      : _createCommentVNode("", true),
    _createVNode(_component_VCard, {
      variant: "tonal",
      class: "mb-3"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardTitle, { class: "d-flex align-center flex-wrap ga-2" }, {
          default: _withCtx(() => [
            _cache[15] || (_cache[15] = _createElementVNode("span", null, "胖虎订阅中心", -1)),
            _createVNode(_component_VChip, {
              size: "small",
              variant: "flat",
              color: "primary"
            }, {
              default: _withCtx(() => [
                _createTextVNode("v" + _toDisplayString(_unref(FRONTEND_VERSION)), 1)
              ]),
              _: 1
            }),
            (status.value)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 0,
                  size: "small",
                  variant: "tonal",
                  color: status.value.enabled ? 'success' : 'default'
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(status.value.enabled ? '已启用' : '未启用'), 1)
                  ]),
                  _: 1
                }, 8, ["color"]))
              : _createCommentVNode("", true),
            (status.value)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 1,
                  size: "small",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 今日写入 " + _toDisplayString(status.value.written_today) + " / " + _toDisplayString(status.value.daily_limit), 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode("", true),
            (status.value && !status.value.first_run_completed)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 2,
                  size: "small",
                  variant: "tonal",
                  color: "warning"
                }, {
                  default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                    _createTextVNode(" 首次运行将强制 dry-run ", -1)
                  ]))]),
                  _: 1
                }))
              : _createCommentVNode("", true)
          ]),
          _: 1
        }),
        _createVNode(_component_VCardText, { class: "sc-hint" }, {
          default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
            _createTextVNode(" 只做三件事：发现 → 去重 → 写订阅。版本控制、洗版与下载优先级由 MoviePilot 后台订阅规则接管，本插件不介入。 ", -1)
          ]))]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VCard, {
      variant: "outlined",
      class: "mb-3"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
          default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
            _createTextVNode("基础", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VCardText, null, {
          default: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: form.value.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.value.enabled) = $event)),
              label: "启用插件",
              density: "compact",
              "hide-details": "",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_VSwitch, {
              modelValue: form.value.discovery_page_enabled,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.value.discovery_page_enabled) = $event)),
              label: "在「发现」分区显示入口",
              density: "compact",
              "hide-details": "",
              disabled: !form.value.enabled,
              class: "mb-2"
            }, null, 8, ["modelValue", "disabled"]),
            _createVNode(_component_VSwitch, {
              modelValue: form.value.dry_run,
              "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.value.dry_run) = $event)),
              label: "dry-run（只记录不写入）",
              density: "compact",
              "hide-details": "",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_VSwitch, {
              modelValue: form.value.notify,
              "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.value.notify) = $event)),
              label: "发送运行摘要通知",
              density: "compact",
              "hide-details": ""
            }, null, 8, ["modelValue"]),
            _createVNode(_component_VSwitch, {
              modelValue: form.value.reset_daily_counter,
              "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.value.reset_daily_counter) = $event)),
              label: "清零今日写入计数（测试用，保存后自动关闭）",
              density: "compact",
              "hide-details": "",
              color: "warning",
              class: "mt-2"
            }, null, 8, ["modelValue"]),
            _cache[18] || (_cache[18] = _createElementVNode("div", { class: "sc-hint mt-1" }, [
              _createTextVNode(" 勾选并保存后，本次会把「今日已写入 N 条」清零，方便同一天反复测。 "),
              _createElementVNode("b", null, "这是测试开关"),
              _createTextVNode("，目标达成后会评估是否保留；保存即自动置回关闭， 不会让每日上限永久失效。 ")
            ], -1)),
            _cache[19] || (_cache[19] = _createElementVNode("div", { class: "sc-hint mt-2" }, " 首次运行无论此开关如何都会强制 dry-run 一次，确认结果后再按本开关执行。 ", -1))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VCard, {
      variant: "outlined",
      class: "mb-3"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
          default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
            _createTextVNode("数据源", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VCardText, null, {
          default: _withCtx(() => [
            (_openBlock(), _createElementBlock(_Fragment, null, _renderList(sourceRows, (row) => {
              return _createElementVNode("div", {
                key: row.key,
                class: "mb-2"
              }, [
                _createVNode(_component_VSwitch, {
                  modelValue: form.value[row.key],
                  "onUpdate:modelValue": $event => ((form.value[row.key]) = $event),
                  label: row.label,
                  density: "compact",
                  "hide-details": ""
                }, null, 8, ["modelValue", "onUpdate:modelValue", "label"]),
                _createElementVNode("div", _hoisted_2, [
                  _createTextVNode(_toDisplayString(row.hint) + " ", 1),
                  (!IMPLEMENTED.includes(row.key.replace('enable_', '')))
                    ? (_openBlock(), _createElementBlock("span", _hoisted_3, " （当前版本已启用也不会运行） "))
                    : _createCommentVNode("", true)
                ])
              ])
            }), 64))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VCard, {
      variant: "outlined",
      class: "mb-3"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
          default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
            _createTextVNode("发现窗口与阈值", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VCardText, null, {
          default: _withCtx(() => [
            _createVNode(_component_VRow, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_VCol, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: form.value.tmdb_future_days,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.value.tmdb_future_days) = $event)),
                      modelModifiers: { number: true },
                      label: "TMDB 发现窗口（天）",
                      type: "number",
                      min: "1",
                      max: "90",
                      density: "compact",
                      "hide-details": "",
                      class: "mb-2"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: form.value.min_rating_tmdb,
                      "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.value.min_rating_tmdb) = $event)),
                      modelModifiers: { number: true },
                      label: "TMDB 最低评分",
                      type: "number",
                      step: "0.1",
                      min: "0",
                      max: "10",
                      density: "compact",
                      "hide-details": "",
                      class: "mb-2"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: form.value.min_popularity,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.value.min_popularity) = $event)),
                      modelModifiers: { number: true },
                      label: "最低关注度（popularity）",
                      type: "number",
                      step: "1",
                      min: "0",
                      density: "compact",
                      "hide-details": "",
                      class: "mb-2"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _cache[22] || (_cache[22] = _createElementVNode("div", { class: "sc-hint" }, " TMDB 只保留「今天 ~ 今天 + N 天」内的定档条目。注意宿主 discover 不支持按地区过滤， 结果会偏欧美。 ", -1)),
            _cache[23] || (_cache[23] = _createElementVNode("div", { class: "sc-hint mt-1" }, [
              _createElementVNode("b", null, "最低关注度"),
              _createTextVNode("：新片还没人评分，popularity 是唯一可用的质量信号。 设 0 表示不过滤，会把同日上映的冷门片也订进来（观众级大片 100+、 院线片 10~50、冷门片 <5）。")
            ], -1)),
            _createVNode(_component_VSwitch, {
              modelValue: form.value.filter_original_language,
              "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.value.filter_original_language) = $event)),
              label: "只保留指定原始语言的条目",
              density: "compact",
              "hide-details": "",
              class: "mt-3"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_VTextField, {
              modelValue: form.value.tmdb_original_languages,
              "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.value.tmdb_original_languages) = $event)),
              label: "允许的原始语言（逗号分隔）",
              density: "compact",
              "hide-details": "",
              disabled: !form.value.filter_original_language,
              placeholder: "zh,ja,ko,en",
              class: "mt-2"
            }, null, 8, ["modelValue", "disabled"]),
            _cache[24] || (_cache[24] = _createElementVNode("div", { class: "sc-hint mt-1" }, " 语种码：zh 华语 / ja 日语 / ko 韩语 / en 英语。小语种片（印度、土耳其、 荷兰等）通常不会被下载，进订阅只会白占每日额度。 ", -1))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VCard, {
      variant: "outlined",
      class: "mb-3"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
          default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
            _createTextVNode("写入与调度", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VCardText, null, {
          default: _withCtx(() => [
            _createVNode(_component_VRow, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_VCol, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: form.value.daily_limit,
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.value.daily_limit) = $event)),
                      modelModifiers: { number: true },
                      label: "每日写入上限",
                      type: "number",
                      min: "1",
                      max: "50",
                      density: "compact",
                      "hide-details": "",
                      class: "mb-2"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: form.value.cron,
                      "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.value.cron) = $event)),
                      label: "执行时间（5 段式 cron）",
                      error: !cronValid(),
                      "error-messages": cronValid() ? [] : ['需要 5 段，例如 0 3 * * *'],
                      density: "compact",
                      "hide-details": "",
                      class: "mb-2"
                    }, null, 8, ["modelValue", "error", "error-messages"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: form.value.timezone,
                      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.value.timezone) = $event)),
                      label: "时区",
                      density: "compact",
                      "hide-details": "",
                      class: "mb-2"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _cache[26] || (_cache[26] = _createElementVNode("div", { class: "sc-hint" }, "修改 cron 后需要重新保存配置才会重建定时任务。", -1))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createElementVNode("div", _hoisted_4, [
      _createVNode(_component_VBtn, {
        color: "primary",
        loading: busy.value === 'save',
        disabled: loading.value,
        "prepend-icon": "mdi-content-save",
        onClick: save
      }, {
        default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
          _createTextVNode(" 保存配置 ", -1)
        ]))]),
        _: 1
      }, 8, ["loading", "disabled"]),
      _createVNode(_component_VBtn, {
        variant: "tonal",
        loading: busy.value === 'run',
        disabled: loading.value,
        "prepend-icon": "mdi-radar",
        onClick: runOnce
      }, {
        default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
          _createTextVNode(" 立即运行一次 ", -1)
        ]))]),
        _: 1
      }, 8, ["loading", "disabled"]),
      _createVNode(_component_VBtn, {
        variant: "text",
        "prepend-icon": "mdi-close",
        onClick: _cache[13] || (_cache[13] = $event => (emit('close')))
      }, {
        default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
          _createTextVNode("关闭", -1)
        ]))]),
        _: 1
      })
    ]),
    _cache[30] || (_cache[30] = _createElementVNode("div", { class: "sc-hint mt-3" }, " 「立即运行一次」会真实触发一次发现流程；首次仍会强制 dry-run，不会写入订阅。 ", -1))
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-5629096e"]]);

export { Config as default };
