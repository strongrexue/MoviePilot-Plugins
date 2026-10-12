import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, u as unwrap, g as getPluginApi, p as postPluginApi, a as getPluginConfig } from './_plugin-vue_export-helper-CF63hxE1.js';

/**
 * 前端构建版本。
 *
 * 用途：与后端 `/status` 返回的 `plugin_version` 比对。
 * 联邦组件的入口文件名固定（`remoteEntry.js`，无哈希）、加载器也不加缓存参数，
 * 因此「插件已更新但浏览器仍用旧组件」是常态。界面上一旦发现两边版本不一致，
 * 就直接提示用户硬刷新，避免对着旧界面排查新问题。
 *
 * ⚠️ 发版时必须与本插件 `plugin_version` 同步（有单测校验，见 tests/v3/tgmediacenter）。
 */
const FRONTEND_VERSION = '1.1.7';

const {resolveComponent:_resolveComponent$3,createVNode:_createVNode$3,withCtx:_withCtx$3,openBlock:_openBlock$3,createBlock:_createBlock$3} = await importShared('vue');


const {ref: ref$4} = await importShared('vue');


/**
 * 默认打码、点眼睛可查看的凭据输入框。
 *
 * 说明：打码只改 `type`（显示层），`v-model` 里的值始终是真实内容——
 * 因此"看着是圆点直接保存"不会把星号写进配置。
 * 供后续 115 Cookie / 豆瓣 Cookie / Bot Token 等字段复用。
 */

const _sfc_main$3 = {
  __name: 'SecretField',
  props: {
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  /** 底层输入类型（如 number）；查看时统一按 text 渲染 */
  inputType: { type: String, default: 'text' },
  /** 初始是否明文显示 */
  startRevealed: { type: Boolean, default: false },
},
  emits: ['update:modelValue'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;
const revealed = ref$4(props.startRevealed);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$3("VIcon");
  const _component_VTextField = _resolveComponent$3("VTextField");

  return (_openBlock$3(), _createBlock$3(_component_VTextField, {
    "model-value": __props.modelValue,
    label: __props.label,
    placeholder: __props.placeholder,
    type: revealed.value ? __props.inputType : 'password',
    density: "compact",
    variant: "outlined",
    "hide-details": "",
    autocomplete: "off",
    autocorrect: "off",
    autocapitalize: "off",
    spellcheck: "false",
    "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => (emit('update:modelValue', $event)))
  }, {
    "append-inner": _withCtx$3(() => [
      _createVNode$3(_component_VIcon, {
        icon: revealed.value ? 'mdi-eye-off-outline' : 'mdi-eye-outline',
        size: "18",
        class: "tg-secret-eye",
        title: revealed.value ? '隐藏' : '显示',
        onClick: _cache[0] || (_cache[0] = $event => (revealed.value = !revealed.value))
      }, null, 8, ["icon", "title"])
    ]),
    _: 1
  }, 8, ["model-value", "label", "placeholder", "type"]))
}
}

};
const SecretField = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-f57a31cd"]]);

/** 复制文本到剪贴板：优先 Clipboard API，失败回退到临时 textarea。 */
async function copyText(text) {
  const value = String(text ?? '');
  if (!value) return false

  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true
    }
  } catch {
    // 非安全上下文（http）下 Clipboard API 不可用，走回退
  }

  try {
    const area = document.createElement('textarea');
    area.value = value;
    area.setAttribute('readonly', 'readonly');
    area.style.position = 'fixed';
    area.style.top = '-1000px';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(area);
    return ok
  } catch {
    return false
  }
}

const {createElementVNode:_createElementVNode$2,toDisplayString:_toDisplayString$2,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,openBlock:_openBlock$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2,createVNode:_createVNode$2,renderList:_renderList$2,Fragment:_Fragment$2,createElementBlock:_createElementBlock$2} = await importShared('vue');


const _hoisted_1$2 = { class: "tg-filters" };
const _hoisted_2$2 = {
  key: 0,
  class: "tg-type-summary"
};
const _hoisted_3$2 = {
  key: 0,
  class: "tg-updated"
};
const _hoisted_4$2 = {
  key: 2,
  class: "tg-empty"
};
const _hoisted_5$1 = {
  key: 3,
  class: "tg-empty"
};
const _hoisted_6$1 = { key: 0 };
const _hoisted_7$1 = {
  key: 5,
  class: "tg-more"
};
const _hoisted_8$1 = {
  key: 6,
  class: "tg-more"
};

const {computed: computed$2,ref: ref$3} = await importShared('vue');

/**
 * 对话（群组 / 频道 / 机器人 / 用户）列表。
 *
 * 参照 MA 的「群组/联系人列表」：可搜索、按类型筛选、显示 ID 并可一键复制，
 * 便于配置资源监控与转发规则时挑选频道。
 */

const _sfc_main$2 = {
  __name: 'TgDialogList',
  props: {
  dialogs: { type: Array, default: () => [] },
  updatedAt: { type: String, default: '' },
  // 每屏最多渲染条数，避免上千条一次全渲染
  pageSize: { type: Number, default: 60 },
},
  setup(__props) {

const props = __props;

const keyword = ref$3('');
const typeFilter = ref$3('全部');
const limit = ref$3(props.pageSize);
const toast = ref$3('');

const TYPE_ORDER = ['频道', '群组', '机器人', '用户', '其他'];

const TYPE_COLOR = {
  频道: 'primary',
  群组: 'success',
  机器人: 'info',
  用户: 'warning',
  其他: 'default',
};

const typeOptions = computed$2(() => {
  const present = new Set((props.dialogs || []).map(item => item?.type).filter(Boolean));
  const ordered = TYPE_ORDER.filter(type => present.has(type));
  // 出现未知类型时也列出来，避免"看不见就是没有"
  for (const type of present) {
    if (!ordered.includes(type)) ordered.push(type);
  }
  return ['全部', ...ordered]
});

const counts = computed$2(() => {
  const result = {};
  for (const item of props.dialogs || []) {
    const type = item?.type || '其他';
    result[type] = (result[type] || 0) + 1;
  }
  return result
});

const filtered = computed$2(() => {
  const key = keyword.value.trim().toLowerCase();
  return (props.dialogs || []).filter(item => {
    if (typeFilter.value !== '全部' && (item?.type || '') !== typeFilter.value) return false
    if (!key) return true
    return (
      String(item?.name || '').toLowerCase().includes(key)
      || String(item?.username || '').toLowerCase().includes(key)
      || String(item?.id ?? '').includes(key)
    )
  })
});

const visible = computed$2(() => filtered.value.slice(0, limit.value));
const hasMore = computed$2(() => filtered.value.length > visible.value.length);

function typeColor(type) {
  return TYPE_COLOR[type] || 'default'
}

async function revealId(item) {
  const text = String(item?.id ?? '');
  const ok = await copyText(text);
  toast.value = ok ? `已复制 ID：${text}` : `复制失败，请手动选择：${text}`;
  window.setTimeout(() => {
    if (toast.value.startsWith('已复制')) toast.value = '';
  }, 2000);
}

function resetLimit() {
  limit.value = props.pageSize;
}

function more() {
  limit.value += props.pageSize;
}

function onFilterChange() {
  resetLimit();
}

function clearFilters() {
  keyword.value = '';
  typeFilter.value = '全部';
  resetLimit();
}

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$2("VChip");
  const _component_VCardTitle = _resolveComponent$2("VCardTitle");
  const _component_VTextField = _resolveComponent$2("VTextField");
  const _component_VSelect = _resolveComponent$2("VSelect");
  const _component_VAlert = _resolveComponent$2("VAlert");
  const _component_VListItemTitle = _resolveComponent$2("VListItemTitle");
  const _component_VListItemSubtitle = _resolveComponent$2("VListItemSubtitle");
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VListItem = _resolveComponent$2("VListItem");
  const _component_VList = _resolveComponent$2("VList");
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VCardText = _resolveComponent$2("VCardText");
  const _component_VCard = _resolveComponent$2("VCard");

  return (_openBlock$2(), _createBlock$2(_component_VCard, {
    flat: "",
    class: "tg-card"
  }, {
    default: _withCtx$2(() => [
      _createVNode$2(_component_VCardTitle, { class: "tg-list-title" }, {
        default: _withCtx$2(() => [
          _cache[2] || (_cache[2] = _createElementVNode$2("span", { class: "text-subtitle-2" }, "群组 / 联系人列表", -1)),
          (__props.dialogs.length)
            ? (_openBlock$2(), _createBlock$2(_component_VChip, {
                key: 0,
                size: "x-small",
                variant: "tonal",
                color: "primary",
                label: ""
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(" 共 " + _toDisplayString$2(__props.dialogs.length) + " 个 ", 1)
                ]),
                _: 1
              }))
            : _createCommentVNode$2("", true)
        ]),
        _: 1
      }),
      _createVNode$2(_component_VCardText, null, {
        default: _withCtx$2(() => [
          _createElementVNode$2("div", _hoisted_1$2, [
            _createVNode$2(_component_VTextField, {
              modelValue: keyword.value,
              "onUpdate:modelValue": [
                _cache[0] || (_cache[0] = $event => ((keyword).value = $event)),
                onFilterChange
              ],
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              clearable: "",
              "prepend-inner-icon": "mdi-magnify",
              placeholder: "按名称 / 用户名 / ID 搜索",
              class: "tg-filter-key"
            }, null, 8, ["modelValue"]),
            _createVNode$2(_component_VSelect, {
              modelValue: typeFilter.value,
              "onUpdate:modelValue": [
                _cache[1] || (_cache[1] = $event => ((typeFilter).value = $event)),
                onFilterChange
              ],
              items: typeOptions.value,
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              class: "tg-filter-type"
            }, null, 8, ["modelValue", "items"])
          ]),
          (__props.dialogs.length)
            ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_2$2, [
                (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(counts.value, (count, type) => {
                  return (_openBlock$2(), _createBlock$2(_component_VChip, {
                    key: type,
                    size: "x-small",
                    variant: "tonal",
                    color: typeColor(type),
                    label: ""
                  }, {
                    default: _withCtx$2(() => [
                      _createTextVNode$2(_toDisplayString$2(type) + " " + _toDisplayString$2(count), 1)
                    ]),
                    _: 2
                  }, 1032, ["color"]))
                }), 128)),
                (__props.updatedAt)
                  ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_3$2, "更新于 " + _toDisplayString$2(__props.updatedAt), 1))
                  : _createCommentVNode$2("", true)
              ]))
            : _createCommentVNode$2("", true),
          (toast.value)
            ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
                key: 1,
                type: toast.value.startsWith('已复制') ? 'success' : 'warning',
                variant: "tonal",
                density: "compact",
                class: "mt-3"
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(_toDisplayString$2(toast.value), 1)
                ]),
                _: 1
              }, 8, ["type"]))
            : _createCommentVNode$2("", true),
          (!__props.dialogs.length)
            ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_4$2, " 暂无缓存。登录成功后点「刷新对话列表」拉取（首次可能较慢）。 "))
            : (!filtered.value.length)
              ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_5$1, " 没有匹配的对话，试试其它关键词。 "))
              : (_openBlock$2(), _createBlock$2(_component_VList, {
                  key: 4,
                  density: "compact",
                  class: "tg-dialog-list"
                }, {
                  default: _withCtx$2(() => [
                    (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(visible.value, (item) => {
                      return (_openBlock$2(), _createBlock$2(_component_VListItem, {
                        key: `${item.type}-${item.id}`,
                        class: "tg-dialog-item",
                        onClick: $event => (revealId(item))
                      }, {
                        prepend: _withCtx$2(() => [
                          _createVNode$2(_component_VChip, {
                            size: "x-small",
                            variant: "tonal",
                            color: typeColor(item.type),
                            label: "",
                            class: "tg-type-chip"
                          }, {
                            default: _withCtx$2(() => [
                              _createTextVNode$2(_toDisplayString$2(item.type), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        append: _withCtx$2(() => [
                          _createVNode$2(_component_VIcon, {
                            icon: "mdi-content-copy",
                            size: "16",
                            class: "tg-copy",
                            title: "复制 ID"
                          })
                        ]),
                        default: _withCtx$2(() => [
                          _createVNode$2(_component_VListItemTitle, { class: "tg-dialog-name" }, {
                            default: _withCtx$2(() => [
                              _createTextVNode$2(_toDisplayString$2(item.name), 1)
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode$2(_component_VListItemSubtitle, { class: "tg-dialog-sub" }, {
                            default: _withCtx$2(() => [
                              (item.username)
                                ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_6$1, "@" + _toDisplayString$2(item.username) + " · ", 1))
                                : _createCommentVNode$2("", true),
                              _createTextVNode$2(_toDisplayString$2(item.id), 1)
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _: 2
                      }, 1032, ["onClick"]))
                    }), 128))
                  ]),
                  _: 1
                })),
          (hasMore.value)
            ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_7$1, [
                _createVNode$2(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  onClick: more
                }, {
                  default: _withCtx$2(() => [
                    _createTextVNode$2(" 显示更多（还有 " + _toDisplayString$2(filtered.value.length - visible.value.length) + " 个） ", 1)
                  ]),
                  _: 1
                })
              ]))
            : (filtered.value.length > __props.pageSize)
              ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_8$1, [
                  _createVNode$2(_component_VBtn, {
                    size: "small",
                    variant: "text",
                    onClick: clearFilters
                  }, {
                    default: _withCtx$2(() => [...(_cache[3] || (_cache[3] = [
                      _createTextVNode$2("重置筛选", -1)
                    ]))]),
                    _: 1
                  })
                ]))
              : _createCommentVNode$2("", true),
          _cache[4] || (_cache[4] = _createElementVNode$2("div", { class: "tg-hint" }, "点击任意条目可复制其 ID（配置监控/转发规则时会用到）。", -1))
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const TgDialogList = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-72a76285"]]);

const {renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,createBlock:_createBlock$1,createElementVNode:_createElementVNode$1,createVNode:_createVNode$1,createCommentVNode:_createCommentVNode$1} = await importShared('vue');


const _hoisted_1$1 = { class: "tg-pane" };
const _hoisted_2$1 = { class: "tg-status-head" };
const _hoisted_3$1 = { class: "tg-status-chips" };
const _hoisted_4$1 = { class: "tg-status-actions" };
const _hoisted_5 = { key: 0 };
const _hoisted_6 = ["title"];
const _hoisted_7 = { key: 2 };
const _hoisted_8 = { class: "tg-authorized" };
const _hoisted_9 = {
  key: 0,
  class: "tg-authorized-name"
};
const _hoisted_10 = { key: 0 };
const _hoisted_11 = { class: "tg-wizard-actions" };
const _hoisted_12 = { class: "tg-hint" };
const _hoisted_13 = { key: 0 };
const _hoisted_14 = { key: 1 };
const _hoisted_15 = { class: "tg-wizard" };
const _hoisted_16 = {
  key: 2,
  class: "tg-wizard tg-wizard-password"
};
const _hoisted_17 = { class: "tg-wizard-actions" };

const {computed: computed$1,onMounted: onMounted$1,onUnmounted,ref: ref$2} = await importShared('vue');


const _sfc_main$1 = {
  __name: 'ConfigTgPane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
},
  setup(__props) {

const props = __props;

const status = ref$2(null);
const statusLoading = ref$2(false);
const busy = ref$2('');
const message = ref$2('');
const messageOk = ref$2(true);
const loginStage = ref$2('idle'); // idle | code_sent | need_password
const code = ref$2('');
const password = ref$2('');
const dialogs = ref$2([]);
const dialogsUpdatedAt = ref$2('');
// 当前待验证码的上下文：投递渠道 + 手机号掩码 + 发码时间
const sent = ref$2(null);
// 距离允许重新发送验证码的剩余秒数
const resendIn = ref$2(0);
// 账号手机号是否明文显示（凭据输入框由 SecretField 各自管理）
const reveal = ref$2({ phone: false });
let countdownId = null;

const form = computed$1(() => props.config.form);

/**
 * 前端构建版本与后端插件版本是否一致。
 *
 * 联邦组件入口无哈希、宿主加载器也不加缓存参数，因此"插件更新了但浏览器还在用旧
 * 组件"是常态。版本不一致时直接提示，避免对着旧界面排查新问题。
 */
const versionMismatch = computed$1(() => {
  const backend = String(status.value?.plugin_version || '');
  if (!backend) return ''
  return backend === FRONTEND_VERSION ? '' : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backend}`
});

const sendLabel = computed$1(() => {
  if (resendIn.value > 0) return `重新发送（${resendIn.value}s）`
  return loginStage.value === 'code_sent' ? '重新发送验证码' : '发送验证码'
});

const sendDisabled = computed$1(() => Boolean(busy.value) || resendIn.value > 0);

function setMessage(text, ok = true) {
  message.value = text || '';
  messageOk.value = ok;
}

/** 打码敏感值：保留首尾片段便于核对。 */
function maskValue(value, keep = 4) {
  const text = String(value || '');
  if (!text) return ''
  if (text.length <= keep * 2) return '*'.repeat(text.length)
  return `${text.slice(0, keep)}${'*'.repeat(6)}${text.slice(-keep)}`
}

function startCountdown(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  if (countdownId) {
    clearInterval(countdownId);
    countdownId = null;
  }
  resendIn.value = total;
  if (total <= 0) return
  countdownId = setInterval(() => {
    resendIn.value = Math.max(0, resendIn.value - 1);
    if (resendIn.value <= 0 && countdownId) {
      clearInterval(countdownId);
      countdownId = null;
    }
  }, 1000);
}

function applyPending(pending) {
  if (!pending) return
  sent.value = pending;
  loginStage.value = loginStage.value === 'need_password' ? 'need_password' : 'code_sent';
  // 仅在未倒计时时同步，避免覆盖刚发码后的本地计时
  if (!countdownId && resendIn.value <= 0) startCountdown(pending.resend_in);
}

async function loadStatus() {
  statusLoading.value = true;
  try {
    const info = unwrap(await getPluginApi(props.api, props.pluginId, 'status', { timeoutMs: 15000 }));
    status.value = info;
    // 硬刷新后从后端恢复登录向导，避免用户误以为需要重新发码
    if (info?.authorized) {
      loginStage.value = 'idle';
      sent.value = null;
      startCountdown(0);
    } else {
      applyPending(info?.pending_login);
    }
  } catch (err) {
    setMessage(err?.message || '状态读取失败', false);
  } finally {
    statusLoading.value = false;
  }
}

async function loadDialogs() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'telegram/dialogs', { timeoutMs: 15000 }));
    dialogs.value = data?.dialogs || [];
    dialogsUpdatedAt.value = data?.updated_at || '';
  } catch {
    dialogs.value = [];
    dialogsUpdatedAt.value = '';
  }
}

/**
 * 实际拉取对话列表。
 *
 * 注意：这里**不做 busy 重入判断**。登录成功后紧接着调用它时，外层 busy 仍为 'sign_in'，
 * 若在此处 return 会让请求被静默丢弃（界面永远停在"正在拉取…"）。
 * 重入保护放在按钮处理器 refreshDialogs 里。
 */
async function fetchDialogs() {
  const data = unwrap(await postPluginApi(
    props.api,
    props.pluginId,
    'telegram/refresh_dialogs',
    {},
    { timeoutMs: 58000 },
  ));
  dialogs.value = data?.dialogs || [];
  dialogsUpdatedAt.value = data?.updated_at || '';
  return dialogs.value.length
}

/** 网关中断（502 等）时后端可能仍在跑，回头同步一次状态以拿到真实结果。 */
async function resyncAfterTransportError(err) {
  if (err?.code !== 'GATEWAY_TIMEOUT' && err?.status !== 502 && err?.status !== 504) return
  await loadStatus();
  await loadDialogs();
}

async function sendCode() {
  if (busy.value) return
  if (resendIn.value > 0) {
    setMessage(`请先使用已收到的验证码，${resendIn.value} 秒后可重新发送`, false);
    return
  }
  busy.value = 'send_code';
  setMessage('');
  try {
    const phone = String(form.value.tg_phone || '').trim();
    if (!phone) throw new Error('请先填写手机号（包含国家码）')
    if (!form.value.tg_api_id || !form.value.tg_api_hash) {
      throw new Error('请先填写 API ID 与 API Hash')
    }
    // 后端读取的是已保存的配置，未保存时直接给出可操作提示
    if (status.value && status.value.api_configured === false) {
      throw new Error('凭证尚未保存：请先点击底部「保存配置」，再发送验证码')
    }
    const result = unwrap(await postPluginApi(
      props.api,
      props.pluginId,
      'telegram/send_code',
      { phone },
      { timeoutMs: 58000 },
    ));
    loginStage.value = 'code_sent';
    sent.value = {
      delivery: result?.delivery || 'unknown',
      delivery_text: result?.delivery_text || '已发送，请查看 Telegram',
      phone_masked: result?.phone_masked || '',
      sent_at: new Date().toLocaleTimeString(),
    };
    startCountdown(result?.resend_in);
    setMessage(result?.message || '验证码已发送');
  } catch (err) {
    setMessage(err?.message || '发送验证码失败', false);
    await resyncAfterTransportError(err);
  } finally {
    busy.value = '';
  }
}

async function signIn() {
  if (busy.value) return
  busy.value = 'sign_in';
  setMessage('');
  try {
    const result = unwrap(await postPluginApi(props.api, props.pluginId, 'telegram/sign_in', {
      phone: String(form.value.tg_phone || '').trim(),
      code: String(code.value || '').trim(),
      password: String(password.value || '').trim(),
    }, { timeoutMs: 62000 }));
    if (result?.need_password) {
      loginStage.value = 'need_password';
      setMessage(result?.message || '请输入两步验证密码', false);
    } else if (result?.authorized) {
      loginStage.value = 'idle';
      code.value = '';
      password.value = '';
      sent.value = null;
      startCountdown(0);
      await loadStatus();
      // 首次登录**不再自动拉取**对话列表：改由用户手动点「刷新对话列表」。
      // 拉取要遍历账号全部对话，放在登录流程里会让人以为"登录卡住了"，
      // 而且登录本身已经成功，不该被后续动作拖住。
      setMessage(
        dialogs.value.length
          ? `登录成功，已复用本地缓存的 ${dialogs.value.length} 个对话；如需更新请点「刷新对话列表」`
          : '登录成功。请点「刷新对话列表」拉取群组 / 频道（后续配置监控与转发规则会用到）',
      );
    } else {
      setMessage(result?.message || '登录未完成', false);
    }
  } catch (err) {
    setMessage(err?.message || '登录失败', false);
    await resyncAfterTransportError(err);
  } finally {
    busy.value = '';
  }
}

async function logout() {
  if (busy.value) return
  busy.value = 'logout';
  setMessage('');
  try {
    const result = unwrap(await postPluginApi(props.api, props.pluginId, 'telegram/logout', {}, { timeoutMs: 40000 }));
    loginStage.value = 'idle';
    dialogs.value = [];
    dialogsUpdatedAt.value = '';
    sent.value = null;
    startCountdown(0);
    setMessage(result?.message || '已退出登录');
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '退出登录失败', false);
  } finally {
    busy.value = '';
  }
}

async function refreshDialogs() {
  if (busy.value) return
  busy.value = 'refresh';
  setMessage('正在拉取对话列表（首次可能较慢，请稍候）…');
  try {
    const count = await fetchDialogs();
    setMessage(count > 0 ? `对话列表已刷新，共 ${count} 条` : '拉取完成，但该账号没有可取用的对话', count > 0);
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '刷新对话列表失败', false);
    await resyncAfterTransportError(err);
  } finally {
    busy.value = '';
  }
}

async function reconnect() {
  if (busy.value) return
  busy.value = 'connect';
  setMessage('正在连接 Telegram（可能需要十几秒）…');
  try {
    const info = unwrap(await postPluginApi(props.api, props.pluginId, 'telegram/connect', {}, { timeoutMs: 32000 }));
    status.value = info;
    if (info?.authorized) {
      loginStage.value = 'idle';
      sent.value = null;
      setMessage('已连接并处于登录状态');
    } else {
      setMessage('已连接，但当前未登录：请发送验证码登录', false);
    }
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '连接 Telegram 失败', false);
  } finally {
    busy.value = '';
  }
}

const chips = computed$1(() => {
  const info = status.value || {};
  const connection = info.connected
    ? { text: 'TG 已连接', color: 'success' }
    : info.running
      ? { text: 'TG 连接断开', color: 'error' }
      : { text: 'TG 未启动', color: 'default' };
  return [
    { text: info.telethon_available ? 'telethon 已安装' : 'telethon 未安装', color: info.telethon_available ? 'success' : 'error' },
    { text: info.api_configured ? 'API 凭证已填' : 'API 凭证未填', color: info.api_configured ? 'success' : 'warning' },
    { text: info.session_present ? '会话已保存' : '无会话', color: info.session_present ? 'success' : 'default' },
    connection,
    { text: info.authorized ? '已登录' : '未登录', color: info.authorized ? 'success' : 'warning' },
  ]
});

/** 会话已保存但客户端没连上：提示自愈路径，避免误以为"登录丢了"。 */
const needsReconnect = computed$1(() => {
  const info = status.value || {};
  return Boolean(info.api_configured && info.session_present && !info.connected && !statusLoading.value)
});

onMounted$1(async () => {
  await loadStatus();
  await loadDialogs();
});

onUnmounted(() => {
  if (countdownId) clearInterval(countdownId);
  countdownId = null;
});

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VCardTitle = _resolveComponent$1("VCardTitle");
  const _component_VCol = _resolveComponent$1("VCol");
  const _component_VTextField = _resolveComponent$1("VTextField");
  const _component_VRow = _resolveComponent$1("VRow");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VCard = _resolveComponent$1("VCard");

  return (_openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
    _createElementVNode$1("div", _hoisted_2$1, [
      _createElementVNode$1("div", _hoisted_3$1, [
        (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(chips.value, (chip) => {
          return (_openBlock$1(), _createBlock$1(_component_VChip, {
            key: chip.text,
            color: chip.color,
            size: "small",
            variant: "tonal",
            label: ""
          }, {
            default: _withCtx$1(() => [
              _createTextVNode$1(_toDisplayString$1(chip.text), 1)
            ]),
            _: 2
          }, 1032, ["color"]))
        }), 128))
      ]),
      _createElementVNode$1("div", _hoisted_4$1, [
        _createVNode$1(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-connection",
          loading: busy.value === 'connect',
          onClick: reconnect
        }, {
          default: _withCtx$1(() => [...(_cache[9] || (_cache[9] = [
            _createTextVNode$1(" 重连 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode$1(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-refresh",
          loading: statusLoading.value,
          onClick: loadStatus
        }, {
          default: _withCtx$1(() => [...(_cache[10] || (_cache[10] = [
            _createTextVNode$1(" 刷新状态 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading"])
      ])
    ]),
    (versionMismatch.value)
      ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "comfortable",
          class: "tg-message"
        }, {
          default: _withCtx$1(() => [
            _createTextVNode$1(_toDisplayString$1(versionMismatch.value) + " —— 浏览器仍在用缓存的旧联邦组件。请按 Ctrl+Shift+R 硬刷新页面（必要时清缓存）后再操作，否则会对着旧界面排查新问题。 ", 1)
          ]),
          _: 1
        }))
      : _createCommentVNode$1("", true),
    (status.value?.me)
      ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
          key: 1,
          type: "success",
          variant: "tonal",
          density: "comfortable",
          class: "tg-account"
        }, {
          default: _withCtx$1(() => [
            _createTextVNode$1(" 已登录：" + _toDisplayString$1(status.value.me.name || status.value.me.username) + " ", 1),
            (status.value.me.username)
              ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_5, "（@" + _toDisplayString$1(status.value.me.username) + "）", 1))
              : _createCommentVNode$1("", true),
            (status.value.me.phone)
              ? (_openBlock$1(), _createElementBlock$1("span", {
                  key: 1,
                  class: "tg-secret",
                  title: reveal.value.phone ? '点击隐藏' : '点击显示',
                  onClick: _cache[0] || (_cache[0] = $event => (reveal.value.phone = !reveal.value.phone))
                }, [
                  _createTextVNode$1(" · " + _toDisplayString$1(reveal.value.phone ? status.value.me.phone : maskValue(status.value.me.phone)) + " ", 1),
                  _createVNode$1(_component_VIcon, {
                    icon: reveal.value.phone ? 'mdi-eye-off-outline' : 'mdi-eye-outline',
                    size: "14"
                  }, null, 8, ["icon"])
                ], 8, _hoisted_6))
              : _createCommentVNode$1("", true),
            _createElementVNode$1("span", null, " · 对话缓存 " + _toDisplayString$1(status.value.dialog_count) + " 条", 1),
            (status.value.dialogs_updated_at)
              ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_7, " · 更新于 " + _toDisplayString$1(status.value.dialogs_updated_at), 1))
              : _createCommentVNode$1("", true)
          ]),
          _: 1
        }))
      : _createCommentVNode$1("", true),
    (message.value)
      ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
          key: 2,
          type: messageOk.value ? 'info' : 'warning',
          variant: "tonal",
          density: "comfortable",
          class: "tg-message"
        }, {
          default: _withCtx$1(() => [
            _createTextVNode$1(_toDisplayString$1(message.value), 1)
          ]),
          _: 1
        }, 8, ["type"]))
      : _createCommentVNode$1("", true),
    _createVNode$1(_component_VCard, {
      flat: "",
      class: "tg-card"
    }, {
      default: _withCtx$1(() => [
        _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$1(() => [...(_cache[11] || (_cache[11] = [
            _createTextVNode$1("API 凭证", -1)
          ]))]),
          _: 1
        }),
        _createVNode$1(_component_VCardText, null, {
          default: _withCtx$1(() => [
            _createVNode$1(_component_VRow, { dense: "" }, {
              default: _withCtx$1(() => [
                _createVNode$1(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$1(() => [
                    _createVNode$1(SecretField, {
                      modelValue: form.value.tg_api_id,
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.value.tg_api_id) = $event)),
                      label: "API ID"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$1(() => [
                    _createVNode$1(SecretField, {
                      modelValue: form.value.tg_api_hash,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.value.tg_api_hash) = $event)),
                      label: "API Hash"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$1(() => [
                    _createVNode$1(SecretField, {
                      modelValue: form.value.tg_phone,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.value.tg_phone) = $event)),
                      label: "手机号（含国家码）",
                      placeholder: "+8613800000000"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_VTextField, {
                      modelValue: form.value.tg_user_cooldown_seconds,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.value.tg_user_cooldown_seconds) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      label: "个人账号转发冷却（秒）",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_VTextField, {
                      modelValue: form.value.tg_keep_alive_seconds,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.value.tg_keep_alive_seconds) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      label: "保活间隔（秒）",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_VTextField, {
                      modelValue: form.value.tg_aggregation_window_seconds,
                      "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.value.tg_aggregation_window_seconds) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      step: "0.5",
                      label: "消息聚合窗口（秒）",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _cache[12] || (_cache[12] = _createElementVNode$1("div", { class: "tg-hint" }, " API ID / Hash 需在 my.telegram.org 申请；代理自动继承 MoviePilot 的系统代理设置。 API ID、API Hash、手机号默认打码，点右侧眼睛可查看（打码只影响显示，保存的仍是真实值）。 ", -1))
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
        _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$1(() => [...(_cache[13] || (_cache[13] = [
            _createTextVNode$1("登录向导", -1)
          ]))]),
          _: 1
        }),
        _createVNode$1(_component_VCardText, null, {
          default: _withCtx$1(() => [
            (status.value?.authorized)
              ? (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 0 }, [
                  _createElementVNode$1("div", _hoisted_8, [
                    _createVNode$1(_component_VChip, {
                      color: "success",
                      variant: "tonal",
                      "prepend-icon": "mdi-account-check-outline",
                      label: ""
                    }, {
                      default: _withCtx$1(() => [...(_cache[14] || (_cache[14] = [
                        _createTextVNode$1(" Telegram 客户端 已授权 ", -1)
                      ]))]),
                      _: 1
                    }),
                    (status.value?.me)
                      ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_9, [
                          _createTextVNode$1(_toDisplayString$1(status.value.me.name || status.value.me.username) + " ", 1),
                          (status.value.me.username)
                            ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_10, "（@" + _toDisplayString$1(status.value.me.username) + "）", 1))
                            : _createCommentVNode$1("", true)
                        ]))
                      : _createCommentVNode$1("", true)
                  ]),
                  _createElementVNode$1("div", _hoisted_11, [
                    _createVNode$1(_component_VBtn, {
                      variant: "tonal",
                      loading: busy.value === 'refresh',
                      disabled: Boolean(busy.value) && busy.value !== 'refresh',
                      "prepend-icon": "mdi-account-multiple-outline",
                      onClick: refreshDialogs
                    }, {
                      default: _withCtx$1(() => [...(_cache[15] || (_cache[15] = [
                        _createTextVNode$1(" 刷新对话列表 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"]),
                    _createVNode$1(_component_VBtn, {
                      variant: "text",
                      color: "error",
                      loading: busy.value === 'logout',
                      "prepend-icon": "mdi-logout",
                      onClick: logout
                    }, {
                      default: _withCtx$1(() => [...(_cache[16] || (_cache[16] = [
                        _createTextVNode$1(" 退出登录 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _createElementVNode$1("div", _hoisted_12, [
                    _cache[17] || (_cache[17] = _createTextVNode$1(" 已登录状态下不需要验证码。如需更换账号，请先「退出登录」。 ", -1)),
                    (!dialogs.value.length)
                      ? (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 0 }, [
                          _createTextVNode$1(" 尚未拉取对话列表：请点一次「刷新对话列表」（登录后不会自动拉取）。 ")
                        ], 64))
                      : _createCommentVNode$1("", true)
                  ])
                ], 64))
              : (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 1 }, [
                  (needsReconnect.value)
                    ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                        key: 0,
                        type: "warning",
                        variant: "tonal",
                        density: "comfortable",
                        class: "tg-message"
                      }, {
                        default: _withCtx$1(() => [...(_cache[18] || (_cache[18] = [
                          _createTextVNode$1(" 会话已保存，但 TG 客户端当前未连接：插件已在后台自动重连，约 10 秒后点「刷新状态」； 也可点右上角「重连」立即重试。 ", -1)
                        ]))]),
                        _: 1
                      }))
                    : _createCommentVNode$1("", true),
                  (sent.value && loginStage.value !== 'idle')
                    ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                        key: 1,
                        type: "info",
                        variant: "tonal",
                        density: "comfortable",
                        class: "tg-message"
                      }, {
                        default: _withCtx$1(() => [
                          _createTextVNode$1(" 验证码" + _toDisplayString$1(sent.value.delivery_text) + " ", 1),
                          (sent.value.phone_masked)
                            ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_13, " · " + _toDisplayString$1(sent.value.phone_masked), 1))
                            : _createCommentVNode$1("", true),
                          (resendIn.value > 0)
                            ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_14, " · " + _toDisplayString$1(resendIn.value) + " 秒后可重新发送", 1))
                            : _createCommentVNode$1("", true)
                        ]),
                        _: 1
                      }))
                    : _createCommentVNode$1("", true),
                  _createElementVNode$1("div", _hoisted_15, [
                    _createVNode$1(_component_VBtn, {
                      color: "primary",
                      variant: "flat",
                      loading: busy.value === 'send_code',
                      disabled: sendDisabled.value,
                      "prepend-icon": "mdi-send-outline",
                      onClick: sendCode
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(sendLabel.value), 1)
                      ]),
                      _: 1
                    }, 8, ["loading", "disabled"]),
                    _createVNode$1(_component_VTextField, {
                      modelValue: code.value,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((code).value = $event)),
                      label: "验证码",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      class: "tg-wizard-input",
                      disabled: loginStage.value === 'need_password'
                    }, null, 8, ["modelValue", "disabled"]),
                    _createVNode$1(_component_VBtn, {
                      color: "success",
                      variant: "flat",
                      loading: busy.value === 'sign_in',
                      "prepend-icon": "mdi-login-variant",
                      onClick: signIn
                    }, {
                      default: _withCtx$1(() => [...(_cache[19] || (_cache[19] = [
                        _createTextVNode$1(" 登录 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  (loginStage.value === 'need_password')
                    ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_16, [
                        _createVNode$1(_component_VTextField, {
                          modelValue: password.value,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((password).value = $event)),
                          type: "password",
                          label: "两步验证密码",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          class: "tg-wizard-input"
                        }, null, 8, ["modelValue"]),
                        _createVNode$1(_component_VBtn, {
                          color: "warning",
                          variant: "flat",
                          loading: busy.value === 'sign_in',
                          "prepend-icon": "mdi-shield-key-outline",
                          onClick: signIn
                        }, {
                          default: _withCtx$1(() => [...(_cache[20] || (_cache[20] = [
                            _createTextVNode$1(" 提交两步验证 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["loading"])
                      ]))
                    : _createCommentVNode$1("", true),
                  _createElementVNode$1("div", _hoisted_17, [
                    _createVNode$1(_component_VBtn, {
                      variant: "tonal",
                      loading: busy.value === 'refresh',
                      disabled: Boolean(busy.value) && busy.value !== 'refresh',
                      "prepend-icon": "mdi-account-multiple-outline",
                      onClick: refreshDialogs
                    }, {
                      default: _withCtx$1(() => [...(_cache[21] || (_cache[21] = [
                        _createTextVNode$1(" 刷新对话列表 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"])
                  ]),
                  _cache[22] || (_cache[22] = _createElementVNode$1("div", { class: "tg-hint" }, " 凭证需先点底部「保存配置」再发码。若未收到验证码，等倒计时结束后可重新发送； 刷新页面不会丢失已发出的验证码，直接输入即可。 ", -1))
                ], 64))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$1(TgDialogList, {
      dialogs: dialogs.value,
      "updated-at": dialogsUpdatedAt.value
    }, null, 8, ["dialogs", "updated-at"])
  ]))
}
}

};
const ConfigTgPane = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-8ddbb2a0"]]);

const {reactive,ref: ref$1} = await importShared('vue');

/**
 * 插件配置表单逻辑。
 *
 * 约定：
 * - 默认值在这里维护一份，与后端 `default_config()` 对齐（后端是权威，此处仅用于首屏渲染）；
 * - 保存时整体提交，交由宿主 `update_config()` **覆盖**写入；
 * - 后端自己维护的状态（如 TG 会话串、对话缓存）一律**不放进表单**，否则一次保存就会把它
 *   连同表单一起覆盖掉。宿主注入的 `initialConfig` 是"打开配置页那一刻"的快照，
 *   因此**优先重新拉取**，拉取失败才退回快照。
 */
const configDefaults = {
  enabled: false,
  // ① TG 核心凭证
  tg_api_id: '',
  tg_api_hash: '',
  tg_phone: '',
  tg_user_cooldown_seconds: 5,
  tg_keep_alive_seconds: 60,
  tg_aggregation_window_seconds: 3.0,
};

function useConfigForm({ api, pluginId, initialConfig, emit }) {
  const form = reactive({ ...configDefaults });
  const loading = ref$1(false);
  const saving = ref$1(false);
  const error = ref$1('');

  function applyConfig(value) {
    const source = value && typeof value === 'object' ? value : {};
    for (const [key, fallback] of Object.entries(configDefaults)) {
      const next = source[key];
      form[key] = next === undefined || next === null ? fallback : next;
    }
  }

  function snapshot() {
    try {
      const value = typeof initialConfig === 'function' ? initialConfig() : initialConfig;
      return value && typeof value === 'object' ? value : {}
    } catch {
      return {}
    }
  }

  async function loadConfig() {
    loading.value = true;
    error.value = '';
    try {
      // 快照可能早于后端写入（例如登录成功后保存的会话），因此以实时读取为准
      let value = null;
      try {
        value = await getPluginConfig(api(), pluginId());
      } catch (err) {
        value = null;
        error.value = err?.message || '';
      }
      applyConfig(value && Object.keys(value).length ? value : snapshot());
    } catch (err) {
      error.value = err?.message || '配置读取失败';
      applyConfig(snapshot());
    } finally {
      loading.value = false;
    }
  }

  function buildPayload() {
    return { ...form }
  }

  async function saveConfig() {
    if (saving.value) return
    saving.value = true;
    error.value = '';
    try {
      emit('save', buildPayload());
    } finally {
      saving.value = false;
    }
  }

  return reactive({
    form,
    loading,
    saving,
    error,
    loadConfig,
    saveConfig,
    applyConfig,
  })
}

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
  { key: 'pan115', title: '115 网盘', icon: 'mdi-cloud-outline', desc: '登录态、目标目录、批量提交' },
  { key: 'douban', title: '豆瓣源', icon: 'mdi-rss', desc: '想看 RSS 与自定义榜单规则' },
  { key: 'monitor', title: '资源监控', icon: 'mdi-radar', desc: '监听频道、推送目标、仅缺集' },
  { key: 'cache', title: '消息缓存', icon: 'mdi-database-outline', desc: '缓存频道、同步与检索' },
  { key: 'forward', title: '通用转发', icon: 'mdi-share-outline', desc: '两级匹配、置顶与内容转换' },
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
            }, null, 8, ["modelValue", "label"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-h6" }, {
              default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
                _createTextVNode("TG媒体中心", -1)
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
              : (_openBlock(), _createBlock(_component_VAlert, {
                  key: 3,
                  type: "info",
                  variant: "tonal",
                  density: "comfortable"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 「" + _toDisplayString(current.value.title) + "」配置面板待实现（见设计文档对应模块）。 ", 1)
                  ]),
                  _: 1
                }))
          ])
        ]),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, null, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[3] || (_cache[3] = [
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
              default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-cf3bb0bd"]]);

export { Config as default };
