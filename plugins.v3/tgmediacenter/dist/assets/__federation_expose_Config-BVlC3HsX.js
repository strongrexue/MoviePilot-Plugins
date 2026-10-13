import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, u as unwrap, g as getPluginApi, p as postPluginApi, d as decisionLabel, a as decisionColor, b as putPluginApi, c as getPluginConfig } from './decision-Bi_MVYgQ.js';

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
const FRONTEND_VERSION = '1.6.8';

const {resolveComponent:_resolveComponent$7,createVNode:_createVNode$7,withCtx:_withCtx$7,openBlock:_openBlock$7,createBlock:_createBlock$7} = await importShared('vue');


const {ref: ref$8} = await importShared('vue');


/**
 * 默认打码、点眼睛可查看的凭据输入框。
 *
 * 说明：打码只改 `type`（显示层），`v-model` 里的值始终是真实内容——
 * 因此"看着是圆点直接保存"不会把星号写进配置。
 * 供后续 115 Cookie / 豆瓣 Cookie / Bot Token 等字段复用。
 */

const _sfc_main$7 = {
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
const revealed = ref$8(props.startRevealed);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$7("VIcon");
  const _component_VTextField = _resolveComponent$7("VTextField");

  return (_openBlock$7(), _createBlock$7(_component_VTextField, {
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
    "append-inner": _withCtx$7(() => [
      _createVNode$7(_component_VIcon, {
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
const SecretField = /*#__PURE__*/_export_sfc(_sfc_main$7, [['__scopeId',"data-v-f57a31cd"]]);

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

const {createElementVNode:_createElementVNode$6,toDisplayString:_toDisplayString$6,createTextVNode:_createTextVNode$6,resolveComponent:_resolveComponent$6,withCtx:_withCtx$6,openBlock:_openBlock$6,createBlock:_createBlock$6,createCommentVNode:_createCommentVNode$6,createVNode:_createVNode$6,renderList:_renderList$6,Fragment:_Fragment$6,createElementBlock:_createElementBlock$6} = await importShared('vue');


const _hoisted_1$6 = { class: "tg-filters" };
const _hoisted_2$6 = {
  key: 0,
  class: "tg-type-summary"
};
const _hoisted_3$6 = {
  key: 0,
  class: "tg-updated"
};
const _hoisted_4$6 = {
  key: 2,
  class: "tg-empty"
};
const _hoisted_5$5 = {
  key: 3,
  class: "tg-empty"
};
const _hoisted_6$5 = { key: 0 };
const _hoisted_7$5 = {
  key: 5,
  class: "tg-more"
};
const _hoisted_8$5 = {
  key: 6,
  class: "tg-more"
};

const {computed: computed$6,ref: ref$7} = await importShared('vue');

/**
 * 对话（群组 / 频道 / 机器人 / 用户）列表。
 *
 * 参照 MA 的「群组/联系人列表」：可搜索、按类型筛选、显示 ID 并可一键复制，
 * 便于配置资源监控与转发规则时挑选频道。
 */

const _sfc_main$6 = {
  __name: 'TgDialogList',
  props: {
  dialogs: { type: Array, default: () => [] },
  updatedAt: { type: String, default: '' },
  // 每屏最多渲染条数，避免上千条一次全渲染
  pageSize: { type: Number, default: 60 },
},
  setup(__props) {

const props = __props;

const keyword = ref$7('');
const typeFilter = ref$7('全部');
const limit = ref$7(props.pageSize);
const toast = ref$7('');

const TYPE_ORDER = ['频道', '群组', '机器人', '用户', '其他'];

const TYPE_COLOR = {
  频道: 'primary',
  群组: 'success',
  机器人: 'info',
  用户: 'warning',
  其他: 'default',
};

const typeOptions = computed$6(() => {
  const present = new Set((props.dialogs || []).map(item => item?.type).filter(Boolean));
  const ordered = TYPE_ORDER.filter(type => present.has(type));
  // 出现未知类型时也列出来，避免"看不见就是没有"
  for (const type of present) {
    if (!ordered.includes(type)) ordered.push(type);
  }
  return ['全部', ...ordered]
});

const counts = computed$6(() => {
  const result = {};
  for (const item of props.dialogs || []) {
    const type = item?.type || '其他';
    result[type] = (result[type] || 0) + 1;
  }
  return result
});

const filtered = computed$6(() => {
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

const visible = computed$6(() => filtered.value.slice(0, limit.value));
const hasMore = computed$6(() => filtered.value.length > visible.value.length);

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
  const _component_VChip = _resolveComponent$6("VChip");
  const _component_VCardTitle = _resolveComponent$6("VCardTitle");
  const _component_VTextField = _resolveComponent$6("VTextField");
  const _component_VSelect = _resolveComponent$6("VSelect");
  const _component_VAlert = _resolveComponent$6("VAlert");
  const _component_VListItemTitle = _resolveComponent$6("VListItemTitle");
  const _component_VListItemSubtitle = _resolveComponent$6("VListItemSubtitle");
  const _component_VIcon = _resolveComponent$6("VIcon");
  const _component_VListItem = _resolveComponent$6("VListItem");
  const _component_VList = _resolveComponent$6("VList");
  const _component_VBtn = _resolveComponent$6("VBtn");
  const _component_VCardText = _resolveComponent$6("VCardText");
  const _component_VCard = _resolveComponent$6("VCard");

  return (_openBlock$6(), _createBlock$6(_component_VCard, {
    flat: "",
    class: "tg-card"
  }, {
    default: _withCtx$6(() => [
      _createVNode$6(_component_VCardTitle, { class: "tg-list-title" }, {
        default: _withCtx$6(() => [
          _cache[2] || (_cache[2] = _createElementVNode$6("span", { class: "text-subtitle-2" }, "群组 / 联系人列表", -1)),
          (__props.dialogs.length)
            ? (_openBlock$6(), _createBlock$6(_component_VChip, {
                key: 0,
                size: "x-small",
                variant: "tonal",
                color: "primary",
                label: ""
              }, {
                default: _withCtx$6(() => [
                  _createTextVNode$6(" 共 " + _toDisplayString$6(__props.dialogs.length) + " 个 ", 1)
                ]),
                _: 1
              }))
            : _createCommentVNode$6("", true)
        ]),
        _: 1
      }),
      _createVNode$6(_component_VCardText, null, {
        default: _withCtx$6(() => [
          _createElementVNode$6("div", _hoisted_1$6, [
            _createVNode$6(_component_VTextField, {
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
            _createVNode$6(_component_VSelect, {
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
            ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_2$6, [
                (_openBlock$6(true), _createElementBlock$6(_Fragment$6, null, _renderList$6(counts.value, (count, type) => {
                  return (_openBlock$6(), _createBlock$6(_component_VChip, {
                    key: type,
                    size: "x-small",
                    variant: "tonal",
                    color: typeColor(type),
                    label: ""
                  }, {
                    default: _withCtx$6(() => [
                      _createTextVNode$6(_toDisplayString$6(type) + " " + _toDisplayString$6(count), 1)
                    ]),
                    _: 2
                  }, 1032, ["color"]))
                }), 128)),
                (__props.updatedAt)
                  ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_3$6, "更新于 " + _toDisplayString$6(__props.updatedAt), 1))
                  : _createCommentVNode$6("", true)
              ]))
            : _createCommentVNode$6("", true),
          (toast.value)
            ? (_openBlock$6(), _createBlock$6(_component_VAlert, {
                key: 1,
                type: toast.value.startsWith('已复制') ? 'success' : 'warning',
                variant: "tonal",
                density: "compact",
                class: "mt-3"
              }, {
                default: _withCtx$6(() => [
                  _createTextVNode$6(_toDisplayString$6(toast.value), 1)
                ]),
                _: 1
              }, 8, ["type"]))
            : _createCommentVNode$6("", true),
          (!__props.dialogs.length)
            ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_4$6, " 暂无缓存。登录成功后点「刷新对话列表」拉取（首次可能较慢）。 "))
            : (!filtered.value.length)
              ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_5$5, " 没有匹配的对话，试试其它关键词。 "))
              : (_openBlock$6(), _createBlock$6(_component_VList, {
                  key: 4,
                  density: "compact",
                  class: "tg-dialog-list"
                }, {
                  default: _withCtx$6(() => [
                    (_openBlock$6(true), _createElementBlock$6(_Fragment$6, null, _renderList$6(visible.value, (item) => {
                      return (_openBlock$6(), _createBlock$6(_component_VListItem, {
                        key: `${item.type}-${item.id}`,
                        class: "tg-dialog-item",
                        onClick: $event => (revealId(item))
                      }, {
                        prepend: _withCtx$6(() => [
                          _createVNode$6(_component_VChip, {
                            size: "x-small",
                            variant: "tonal",
                            color: typeColor(item.type),
                            label: "",
                            class: "tg-type-chip"
                          }, {
                            default: _withCtx$6(() => [
                              _createTextVNode$6(_toDisplayString$6(item.type), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        append: _withCtx$6(() => [
                          _createVNode$6(_component_VIcon, {
                            icon: "mdi-content-copy",
                            size: "16",
                            class: "tg-copy",
                            title: "复制 ID"
                          })
                        ]),
                        default: _withCtx$6(() => [
                          _createVNode$6(_component_VListItemTitle, { class: "tg-dialog-name" }, {
                            default: _withCtx$6(() => [
                              _createTextVNode$6(_toDisplayString$6(item.name), 1)
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode$6(_component_VListItemSubtitle, { class: "tg-dialog-sub" }, {
                            default: _withCtx$6(() => [
                              (item.username)
                                ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_6$5, "@" + _toDisplayString$6(item.username) + " · ", 1))
                                : _createCommentVNode$6("", true),
                              _createTextVNode$6(_toDisplayString$6(item.id), 1)
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
            ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_7$5, [
                _createVNode$6(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  onClick: more
                }, {
                  default: _withCtx$6(() => [
                    _createTextVNode$6(" 显示更多（还有 " + _toDisplayString$6(filtered.value.length - visible.value.length) + " 个） ", 1)
                  ]),
                  _: 1
                })
              ]))
            : (filtered.value.length > __props.pageSize)
              ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_8$5, [
                  _createVNode$6(_component_VBtn, {
                    size: "small",
                    variant: "text",
                    onClick: clearFilters
                  }, {
                    default: _withCtx$6(() => [...(_cache[3] || (_cache[3] = [
                      _createTextVNode$6("重置筛选", -1)
                    ]))]),
                    _: 1
                  })
                ]))
              : _createCommentVNode$6("", true),
          _cache[4] || (_cache[4] = _createElementVNode$6("div", { class: "tg-hint" }, "点击任意条目可复制其 ID（配置监控/转发规则时会用到）。", -1))
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const TgDialogList = /*#__PURE__*/_export_sfc(_sfc_main$6, [['__scopeId',"data-v-72a76285"]]);

const {renderList:_renderList$5,Fragment:_Fragment$5,openBlock:_openBlock$5,createElementBlock:_createElementBlock$5,toDisplayString:_toDisplayString$5,createTextVNode:_createTextVNode$5,resolveComponent:_resolveComponent$5,withCtx:_withCtx$5,createBlock:_createBlock$5,createElementVNode:_createElementVNode$5,createVNode:_createVNode$5,createCommentVNode:_createCommentVNode$5} = await importShared('vue');


const _hoisted_1$5 = { class: "tg-pane" };
const _hoisted_2$5 = { class: "tg-status-head" };
const _hoisted_3$5 = { class: "tg-status-chips" };
const _hoisted_4$5 = { class: "tg-status-actions" };
const _hoisted_5$4 = { key: 0 };
const _hoisted_6$4 = ["title"];
const _hoisted_7$4 = { key: 2 };
const _hoisted_8$4 = { class: "tg-authorized" };
const _hoisted_9$4 = {
  key: 0,
  class: "tg-authorized-name"
};
const _hoisted_10$4 = { key: 0 };
const _hoisted_11$4 = { class: "tg-wizard-actions" };
const _hoisted_12$4 = { class: "tg-hint" };
const _hoisted_13$4 = { key: 0 };
const _hoisted_14$4 = { key: 1 };
const _hoisted_15$4 = { class: "tg-wizard" };
const _hoisted_16$4 = {
  key: 2,
  class: "tg-wizard tg-wizard-password"
};
const _hoisted_17$4 = { class: "tg-wizard-actions" };

const {computed: computed$5,onMounted: onMounted$5,onUnmounted: onUnmounted$4,ref: ref$6} = await importShared('vue');


const _sfc_main$5 = {
  __name: 'ConfigTgPane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
},
  setup(__props) {

const props = __props;

const status = ref$6(null);
const statusLoading = ref$6(false);
const busy = ref$6('');
const message = ref$6('');
const messageOk = ref$6(true);
const loginStage = ref$6('idle'); // idle | code_sent | need_password
const code = ref$6('');
const password = ref$6('');
const dialogs = ref$6([]);
const dialogsUpdatedAt = ref$6('');
// 当前待验证码的上下文：投递渠道 + 手机号掩码 + 发码时间
const sent = ref$6(null);
// 距离允许重新发送验证码的剩余秒数
const resendIn = ref$6(0);
// 账号手机号是否明文显示（凭据输入框由 SecretField 各自管理）
const reveal = ref$6({ phone: false });
let countdownId = null;

const form = computed$5(() => props.config.form);

/**
 * 前端构建版本与后端插件版本是否一致。
 *
 * 联邦组件入口无哈希、宿主加载器也不加缓存参数，因此"插件更新了但浏览器还在用旧
 * 组件"是常态。版本不一致时直接提示，避免对着旧界面排查新问题。
 */
const versionMismatch = computed$5(() => {
  const backend = String(status.value?.plugin_version || '');
  if (!backend) return ''
  return backend === FRONTEND_VERSION ? '' : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backend}`
});

const sendLabel = computed$5(() => {
  if (resendIn.value > 0) return `重新发送（${resendIn.value}s）`
  return loginStage.value === 'code_sent' ? '重新发送验证码' : '发送验证码'
});

const sendDisabled = computed$5(() => Boolean(busy.value) || resendIn.value > 0);

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

const chips = computed$5(() => {
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
const needsReconnect = computed$5(() => {
  const info = status.value || {};
  return Boolean(info.api_configured && info.session_present && !info.connected && !statusLoading.value)
});

onMounted$5(async () => {
  await loadStatus();
  await loadDialogs();
});

onUnmounted$4(() => {
  if (countdownId) clearInterval(countdownId);
  countdownId = null;
});

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$5("VChip");
  const _component_VBtn = _resolveComponent$5("VBtn");
  const _component_VAlert = _resolveComponent$5("VAlert");
  const _component_VIcon = _resolveComponent$5("VIcon");
  const _component_VCardTitle = _resolveComponent$5("VCardTitle");
  const _component_VCol = _resolveComponent$5("VCol");
  const _component_VTextField = _resolveComponent$5("VTextField");
  const _component_VRow = _resolveComponent$5("VRow");
  const _component_VCardText = _resolveComponent$5("VCardText");
  const _component_VCard = _resolveComponent$5("VCard");

  return (_openBlock$5(), _createElementBlock$5("div", _hoisted_1$5, [
    _createElementVNode$5("div", _hoisted_2$5, [
      _createElementVNode$5("div", _hoisted_3$5, [
        (_openBlock$5(true), _createElementBlock$5(_Fragment$5, null, _renderList$5(chips.value, (chip) => {
          return (_openBlock$5(), _createBlock$5(_component_VChip, {
            key: chip.text,
            color: chip.color,
            size: "small",
            variant: "tonal",
            label: ""
          }, {
            default: _withCtx$5(() => [
              _createTextVNode$5(_toDisplayString$5(chip.text), 1)
            ]),
            _: 2
          }, 1032, ["color"]))
        }), 128))
      ]),
      _createElementVNode$5("div", _hoisted_4$5, [
        _createVNode$5(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-connection",
          loading: busy.value === 'connect',
          onClick: reconnect
        }, {
          default: _withCtx$5(() => [...(_cache[9] || (_cache[9] = [
            _createTextVNode$5(" 重连 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode$5(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-refresh",
          loading: statusLoading.value,
          onClick: loadStatus
        }, {
          default: _withCtx$5(() => [...(_cache[10] || (_cache[10] = [
            _createTextVNode$5(" 刷新状态 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading"])
      ])
    ]),
    (versionMismatch.value)
      ? (_openBlock$5(), _createBlock$5(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "comfortable",
          class: "tg-message"
        }, {
          default: _withCtx$5(() => [
            _createTextVNode$5(_toDisplayString$5(versionMismatch.value) + " —— 浏览器仍在用缓存的旧联邦组件。请按 Ctrl+Shift+R 硬刷新页面（必要时清缓存）后再操作，否则会对着旧界面排查新问题。 ", 1)
          ]),
          _: 1
        }))
      : _createCommentVNode$5("", true),
    (status.value?.me)
      ? (_openBlock$5(), _createBlock$5(_component_VAlert, {
          key: 1,
          type: "success",
          variant: "tonal",
          density: "comfortable",
          class: "tg-account"
        }, {
          default: _withCtx$5(() => [
            _createTextVNode$5(" 已登录：" + _toDisplayString$5(status.value.me.name || status.value.me.username) + " ", 1),
            (status.value.me.username)
              ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_5$4, "（@" + _toDisplayString$5(status.value.me.username) + "）", 1))
              : _createCommentVNode$5("", true),
            (status.value.me.phone)
              ? (_openBlock$5(), _createElementBlock$5("span", {
                  key: 1,
                  class: "tg-secret",
                  title: reveal.value.phone ? '点击隐藏' : '点击显示',
                  onClick: _cache[0] || (_cache[0] = $event => (reveal.value.phone = !reveal.value.phone))
                }, [
                  _createTextVNode$5(" · " + _toDisplayString$5(reveal.value.phone ? status.value.me.phone : maskValue(status.value.me.phone)) + " ", 1),
                  _createVNode$5(_component_VIcon, {
                    icon: reveal.value.phone ? 'mdi-eye-off-outline' : 'mdi-eye-outline',
                    size: "14"
                  }, null, 8, ["icon"])
                ], 8, _hoisted_6$4))
              : _createCommentVNode$5("", true),
            _createElementVNode$5("span", null, " · 对话缓存 " + _toDisplayString$5(status.value.dialog_count) + " 条", 1),
            (status.value.dialogs_updated_at)
              ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_7$4, " · 更新于 " + _toDisplayString$5(status.value.dialogs_updated_at), 1))
              : _createCommentVNode$5("", true)
          ]),
          _: 1
        }))
      : _createCommentVNode$5("", true),
    (message.value)
      ? (_openBlock$5(), _createBlock$5(_component_VAlert, {
          key: 2,
          type: messageOk.value ? 'info' : 'warning',
          variant: "tonal",
          density: "comfortable",
          class: "tg-message"
        }, {
          default: _withCtx$5(() => [
            _createTextVNode$5(_toDisplayString$5(message.value), 1)
          ]),
          _: 1
        }, 8, ["type"]))
      : _createCommentVNode$5("", true),
    _createVNode$5(_component_VCard, {
      flat: "",
      class: "tg-card"
    }, {
      default: _withCtx$5(() => [
        _createVNode$5(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$5(() => [...(_cache[11] || (_cache[11] = [
            _createTextVNode$5("API 凭证", -1)
          ]))]),
          _: 1
        }),
        _createVNode$5(_component_VCardText, null, {
          default: _withCtx$5(() => [
            _createVNode$5(_component_VRow, { dense: "" }, {
              default: _withCtx$5(() => [
                _createVNode$5(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$5(() => [
                    _createVNode$5(SecretField, {
                      modelValue: form.value.tg_api_id,
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.value.tg_api_id) = $event)),
                      label: "API ID"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode$5(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$5(() => [
                    _createVNode$5(SecretField, {
                      modelValue: form.value.tg_api_hash,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.value.tg_api_hash) = $event)),
                      label: "API Hash"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode$5(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$5(() => [
                    _createVNode$5(SecretField, {
                      modelValue: form.value.tg_phone,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.value.tg_phone) = $event)),
                      label: "手机号（含国家码）",
                      placeholder: "+8613800000000"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode$5(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$5(() => [
                    _createVNode$5(_component_VTextField, {
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
                _createVNode$5(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$5(() => [
                    _createVNode$5(_component_VTextField, {
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
                _createVNode$5(_component_VCol, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx$5(() => [
                    _createVNode$5(_component_VTextField, {
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
            _cache[12] || (_cache[12] = _createElementVNode$5("div", { class: "tg-hint" }, " API ID / Hash 需在 my.telegram.org 申请；代理自动继承 MoviePilot 的系统代理设置。 API ID、API Hash、手机号默认打码，点右侧眼睛可查看（打码只影响显示，保存的仍是真实值）。 ", -1))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$5(_component_VCard, {
      flat: "",
      class: "tg-card"
    }, {
      default: _withCtx$5(() => [
        _createVNode$5(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$5(() => [...(_cache[13] || (_cache[13] = [
            _createTextVNode$5("登录向导", -1)
          ]))]),
          _: 1
        }),
        _createVNode$5(_component_VCardText, null, {
          default: _withCtx$5(() => [
            (status.value?.authorized)
              ? (_openBlock$5(), _createElementBlock$5(_Fragment$5, { key: 0 }, [
                  _createElementVNode$5("div", _hoisted_8$4, [
                    _createVNode$5(_component_VChip, {
                      color: "success",
                      variant: "tonal",
                      "prepend-icon": "mdi-account-check-outline",
                      label: ""
                    }, {
                      default: _withCtx$5(() => [...(_cache[14] || (_cache[14] = [
                        _createTextVNode$5(" Telegram 客户端 已授权 ", -1)
                      ]))]),
                      _: 1
                    }),
                    (status.value?.me)
                      ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_9$4, [
                          _createTextVNode$5(_toDisplayString$5(status.value.me.name || status.value.me.username) + " ", 1),
                          (status.value.me.username)
                            ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_10$4, "（@" + _toDisplayString$5(status.value.me.username) + "）", 1))
                            : _createCommentVNode$5("", true)
                        ]))
                      : _createCommentVNode$5("", true)
                  ]),
                  _createElementVNode$5("div", _hoisted_11$4, [
                    _createVNode$5(_component_VBtn, {
                      variant: "tonal",
                      loading: busy.value === 'refresh',
                      disabled: Boolean(busy.value) && busy.value !== 'refresh',
                      "prepend-icon": "mdi-account-multiple-outline",
                      onClick: refreshDialogs
                    }, {
                      default: _withCtx$5(() => [...(_cache[15] || (_cache[15] = [
                        _createTextVNode$5(" 刷新对话列表 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"]),
                    _createVNode$5(_component_VBtn, {
                      variant: "text",
                      color: "error",
                      loading: busy.value === 'logout',
                      "prepend-icon": "mdi-logout",
                      onClick: logout
                    }, {
                      default: _withCtx$5(() => [...(_cache[16] || (_cache[16] = [
                        _createTextVNode$5(" 退出登录 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _createElementVNode$5("div", _hoisted_12$4, [
                    _cache[17] || (_cache[17] = _createTextVNode$5(" 已登录状态下不需要验证码。如需更换账号，请先「退出登录」。 ", -1)),
                    (!dialogs.value.length)
                      ? (_openBlock$5(), _createElementBlock$5(_Fragment$5, { key: 0 }, [
                          _createTextVNode$5(" 尚未拉取对话列表：请点一次「刷新对话列表」（登录后不会自动拉取）。 ")
                        ], 64))
                      : _createCommentVNode$5("", true)
                  ])
                ], 64))
              : (_openBlock$5(), _createElementBlock$5(_Fragment$5, { key: 1 }, [
                  (needsReconnect.value)
                    ? (_openBlock$5(), _createBlock$5(_component_VAlert, {
                        key: 0,
                        type: "warning",
                        variant: "tonal",
                        density: "comfortable",
                        class: "tg-message"
                      }, {
                        default: _withCtx$5(() => [...(_cache[18] || (_cache[18] = [
                          _createTextVNode$5(" 会话已保存，但 TG 客户端当前未连接：插件已在后台自动重连，约 10 秒后点「刷新状态」； 也可点右上角「重连」立即重试。 ", -1)
                        ]))]),
                        _: 1
                      }))
                    : _createCommentVNode$5("", true),
                  (sent.value && loginStage.value !== 'idle')
                    ? (_openBlock$5(), _createBlock$5(_component_VAlert, {
                        key: 1,
                        type: "info",
                        variant: "tonal",
                        density: "comfortable",
                        class: "tg-message"
                      }, {
                        default: _withCtx$5(() => [
                          _createTextVNode$5(" 验证码" + _toDisplayString$5(sent.value.delivery_text) + " ", 1),
                          (sent.value.phone_masked)
                            ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_13$4, " · " + _toDisplayString$5(sent.value.phone_masked), 1))
                            : _createCommentVNode$5("", true),
                          (resendIn.value > 0)
                            ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_14$4, " · " + _toDisplayString$5(resendIn.value) + " 秒后可重新发送", 1))
                            : _createCommentVNode$5("", true)
                        ]),
                        _: 1
                      }))
                    : _createCommentVNode$5("", true),
                  _createElementVNode$5("div", _hoisted_15$4, [
                    _createVNode$5(_component_VBtn, {
                      color: "primary",
                      variant: "flat",
                      loading: busy.value === 'send_code',
                      disabled: sendDisabled.value,
                      "prepend-icon": "mdi-send-outline",
                      onClick: sendCode
                    }, {
                      default: _withCtx$5(() => [
                        _createTextVNode$5(_toDisplayString$5(sendLabel.value), 1)
                      ]),
                      _: 1
                    }, 8, ["loading", "disabled"]),
                    _createVNode$5(_component_VTextField, {
                      modelValue: code.value,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((code).value = $event)),
                      label: "验证码",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      class: "tg-wizard-input",
                      disabled: loginStage.value === 'need_password'
                    }, null, 8, ["modelValue", "disabled"]),
                    _createVNode$5(_component_VBtn, {
                      color: "success",
                      variant: "flat",
                      loading: busy.value === 'sign_in',
                      "prepend-icon": "mdi-login-variant",
                      onClick: signIn
                    }, {
                      default: _withCtx$5(() => [...(_cache[19] || (_cache[19] = [
                        _createTextVNode$5(" 登录 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  (loginStage.value === 'need_password')
                    ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_16$4, [
                        _createVNode$5(_component_VTextField, {
                          modelValue: password.value,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((password).value = $event)),
                          type: "password",
                          label: "两步验证密码",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          class: "tg-wizard-input"
                        }, null, 8, ["modelValue"]),
                        _createVNode$5(_component_VBtn, {
                          color: "warning",
                          variant: "flat",
                          loading: busy.value === 'sign_in',
                          "prepend-icon": "mdi-shield-key-outline",
                          onClick: signIn
                        }, {
                          default: _withCtx$5(() => [...(_cache[20] || (_cache[20] = [
                            _createTextVNode$5(" 提交两步验证 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["loading"])
                      ]))
                    : _createCommentVNode$5("", true),
                  _createElementVNode$5("div", _hoisted_17$4, [
                    _createVNode$5(_component_VBtn, {
                      variant: "tonal",
                      loading: busy.value === 'refresh',
                      disabled: Boolean(busy.value) && busy.value !== 'refresh',
                      "prepend-icon": "mdi-account-multiple-outline",
                      onClick: refreshDialogs
                    }, {
                      default: _withCtx$5(() => [...(_cache[21] || (_cache[21] = [
                        _createTextVNode$5(" 刷新对话列表 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"])
                  ]),
                  _cache[22] || (_cache[22] = _createElementVNode$5("div", { class: "tg-hint" }, " 凭证需先点底部「保存配置」再发码。若未收到验证码，等倒计时结束后可重新发送； 刷新页面不会丢失已发出的验证码，直接输入即可。 ", -1))
                ], 64))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$5(TgDialogList, {
      dialogs: dialogs.value,
      "updated-at": dialogsUpdatedAt.value
    }, null, 8, ["dialogs", "updated-at"])
  ]))
}
}

};
const ConfigTgPane = /*#__PURE__*/_export_sfc(_sfc_main$5, [['__scopeId',"data-v-8ddbb2a0"]]);

const {resolveComponent:_resolveComponent$4,createVNode:_createVNode$4,createTextVNode:_createTextVNode$4,withCtx:_withCtx$4,toDisplayString:_toDisplayString$4,openBlock:_openBlock$4,createBlock:_createBlock$4,createCommentVNode:_createCommentVNode$4,createElementVNode:_createElementVNode$4,createElementBlock:_createElementBlock$4,renderList:_renderList$4,Fragment:_Fragment$4} = await importShared('vue');


const _hoisted_1$4 = { class: "p115-pane" };
const _hoisted_2$4 = { class: "p115-status" };
const _hoisted_3$4 = { class: "p115-account" };
const _hoisted_4$4 = {
  key: 0,
  class: "p115-updated"
};
const _hoisted_5$3 = { class: "p115-qr" };
const _hoisted_6$3 = { class: "p115-qr-form" };
const _hoisted_7$3 = {
  key: 0,
  class: "p115-qr-body"
};
const _hoisted_8$3 = ["src"];
const _hoisted_9$3 = { class: "p115-qr-meta" };
const _hoisted_10$3 = { class: "p115-qr-state" };
const _hoisted_11$3 = { class: "p115-qr-tip" };
const _hoisted_12$3 = {
  key: 0,
  class: "p115-qr-tip"
};
const _hoisted_13$3 = { class: "p115-actions" };
const _hoisted_14$3 = { class: "p115-notify" };
const _hoisted_15$3 = { class: "p115-actions" };
const _hoisted_16$3 = {
  key: 0,
  class: "p115-result"
};
const _hoisted_17$3 = { class: "p115-result-head" };

const {computed: computed$4,onMounted: onMounted$4,onUnmounted: onUnmounted$3,ref: ref$5} = await importShared('vue');

/**
 * ② 115 网盘面板。
 *
 * 结构对齐 MA 的「115 网盘」设置：账号与授权 / 任务设置。
 * 登录方式只保留**扫码登录**（App 通道，不触发安全密钥）；
 * Cookie 由扫码换取后保存在插件数据内部，界面上不展示、不可粘贴。
 */

const _sfc_main$4 = {
  __name: 'ConfigPan115Pane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
},
  setup(__props) {

const props = __props;

const status = ref$5(null);
const loading = ref$5(false);
const busy = ref$5('');
const message = ref$5('');
const messageOk = ref$5(true);
const pushText = ref$5('');
const pushResult = ref$5(null);

const form = computed$4(() => props.config.form);

const accountLine = computed$4(() => {
  const info = status.value || {};
  if (!info.cookie_configured) return '未登录（请扫码）'
  if (!info.authorized) return '已取得登录态，尚未验证（点「测试连接」）'
  const device = info.login_device ? `（登录设备：${info.login_device}）` : '';
  return `${info.account ? `当前登录账号：${info.account}` : '已连接'}${device}`
});

const spaceLine = computed$4(() => {
  const space = status.value?.space || {};
  if (!space.total) return '空间：未知'
  return `空间：${space.used || '?'} / ${space.total}`
});

function setMessage(text, ok = true) {
  message.value = text || '';
  messageOk.value = ok;
}

async function loadStatus() {
  loading.value = true;
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'pan115/status', { timeoutMs: 15000 }));
  } catch (err) {
    setMessage(err?.message || '读取 115 状态失败', false);
  } finally {
    loading.value = false;
  }
}

async function check() {
  if (busy.value) return
  busy.value = 'check';
  setMessage('正在测试 115 连接…');
  try {
    const info = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/check', {}, { timeoutMs: 40000 }));
    status.value = info;
    setMessage(info?.account ? `115 连接正常：${info.account}` : '115 连接正常');
  } catch (err) {
    setMessage(err?.message || '测试 115 连接失败', false);
    await loadStatus();
  } finally {
    busy.value = '';
  }
}

async function clearCookie() {
  if (busy.value) return
  busy.value = 'logout';
  try {
    const info = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/logout', {}, { timeoutMs: 20000 }));
    status.value = info;
    setMessage('已清除 115 登录态');
  } catch (err) {
    setMessage(err?.message || '清除失败', false);
  } finally {
    busy.value = '';
  }
}

async function verifyDir() {
  if (busy.value) return
  busy.value = 'dir';
  setMessage('正在校验目标目录…');
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/verify_dir', {
      cid: String(form.value.pan115_target_cid || '').trim(),
    }, { timeoutMs: 30000 }));
    setMessage(data?.message || `目录可用：${data?.cid || ''}`);
  } catch (err) {
    setMessage(err?.message || '目录校验失败', false);
  } finally {
    busy.value = '';
  }
}

async function push(dryRun) {
  if (busy.value) return
  busy.value = dryRun ? 'parse' : 'push';
  setMessage(dryRun ? '正在解析链接…' : '正在推送到 115（按批次提交，可能需要一点时间）…');
  pushResult.value = null;
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/push', {
      text: String(pushText.value || ''),
      cid: String(form.value.pan115_target_cid || '').trim(),
      batch_size: Number(form.value.pan115_batch_max_size) || 0,
      dry_run: Boolean(dryRun),
    }, { timeoutMs: 58000 }));
    pushResult.value = data;
    setMessage(data?.message || (dryRun ? '解析完成' : '推送完成'), !(data?.failed > 0));
  } catch (err) {
    setMessage(err?.message || '推送失败', false);
  } finally {
    busy.value = '';
  }
}

// ------------------------------------------------------------------ 扫码登录
const qr = ref$5(null);
const qrApp = ref$5('alipaymini');
const qrBusy = ref$5(false);
let qrTimer = null;

const qrApps = computed$4(() => status.value?.qr_apps || []);

async function qrStart() {
  if (qrBusy.value) return
  qrBusy.value = true;
  setMessage('正在获取二维码…');
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'pan115/qr_start', { app: qrApp.value }, { timeoutMs: 30000 },
    ));
    qr.value = data;
    setMessage(data?.message || '请用 115 App 扫描二维码');
    startQrPolling();
  } catch (err) {
    setMessage(err?.message || '获取二维码失败', false);
  } finally {
    qrBusy.value = false;
  }
}

async function qrPollOnce() {
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/qr_poll', {}, { timeoutMs: 30000 }));
    qr.value = data;
    const state = data?.status;
    if (state === 'success') {
      qrStopPolling();
      if (data?.status_data) status.value = data.status_data;
      setMessage(data?.message || '扫码登录成功');
      await loadStatus();
    } else if (state === 'expired' || state === 'canceled') {
      qrStopPolling();
      setMessage(data?.message || '二维码已失效，请重新获取', false);
    } else {
      setMessage(data?.status_text || '等待扫码');
    }
  } catch (err) {
    qrStopPolling();
    setMessage(err?.message || '查询扫码状态失败', false);
  }
}

function startQrPolling() {
  qrStopPolling();
  qrTimer = window.setInterval(qrPollOnce, 2000);
}

function qrStopPolling() {
  if (qrTimer) {
    window.clearInterval(qrTimer);
    qrTimer = null;
  }
}

async function qrCancel() {
  qrStopPolling();
  try {
    await postPluginApi(props.api, props.pluginId, 'pan115/qr_cancel', {}, { timeoutMs: 20000 });
  } catch {
    // 取消失败不影响本地状态清理
  }
  qr.value = null;
  setMessage('已取消扫码登录');
}

onMounted$4(async () => {
  await loadStatus();
  // 刷新页面后若仍有进行中的扫码会话，恢复二维码并继续轮询
  const pending = status.value?.qr_pending;
  if (pending?.image) {
    qr.value = {
      app: pending.app,
      image: pending.image,
      status: 'waiting',
      status_text: '等待扫码',
      message: '继续等待扫码…',
      expires_in: pending.expires_in,
    };
    startQrPolling();
  }
});

onUnmounted$3(qrStopPolling);

return (_ctx, _cache) => {
  const _component_VSwitch = _resolveComponent$4("VSwitch");
  const _component_VCardTitle = _resolveComponent$4("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$4("VCardSubtitle");
  const _component_VCardItem = _resolveComponent$4("VCardItem");
  const _component_VCard = _resolveComponent$4("VCard");
  const _component_VAlert = _resolveComponent$4("VAlert");
  const _component_VSelect = _resolveComponent$4("VSelect");
  const _component_VBtn = _resolveComponent$4("VBtn");
  const _component_VSpacer = _resolveComponent$4("VSpacer");
  const _component_VCardText = _resolveComponent$4("VCardText");
  const _component_VTextField = _resolveComponent$4("VTextField");
  const _component_VCol = _resolveComponent$4("VCol");
  const _component_VRow = _resolveComponent$4("VRow");
  const _component_VTextarea = _resolveComponent$4("VTextarea");
  const _component_VIcon = _resolveComponent$4("VIcon");
  const _component_VListItemTitle = _resolveComponent$4("VListItemTitle");
  const _component_VListItemSubtitle = _resolveComponent$4("VListItemSubtitle");
  const _component_VListItem = _resolveComponent$4("VListItem");
  const _component_VList = _resolveComponent$4("VList");

  return (_openBlock$4(), _createElementBlock$4("div", _hoisted_1$4, [
    _createVNode$4(_component_VCard, {
      flat: "",
      class: "p115-card"
    }, {
      default: _withCtx$4(() => [
        _createVNode$4(_component_VCardItem, null, {
          prepend: _withCtx$4(() => [
            _createVNode$4(_component_VSwitch, {
              modelValue: form.value.pan115_enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.value.pan115_enabled) = $event)),
              color: "primary",
              "hide-details": "",
              inset: ""
            }, null, 8, ["modelValue"])
          ]),
          default: _withCtx$4(() => [
            _createVNode$4(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$4(() => [...(_cache[10] || (_cache[10] = [
                _createTextVNode$4("启用 115 网盘作为推送目标", -1)
              ]))]),
              _: 1
            }),
            _createVNode$4(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx$4(() => [...(_cache[11] || (_cache[11] = [
                _createTextVNode$4(" 资源监控 / 通用转发命中后，可把分享链接与磁力/ed2k 推送到 115（转存或离线下载）。 ", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    (message.value)
      ? (_openBlock$4(), _createBlock$4(_component_VAlert, {
          key: 0,
          type: messageOk.value ? 'info' : 'warning',
          variant: "tonal",
          density: "comfortable",
          class: "p115-message"
        }, {
          default: _withCtx$4(() => [
            _createTextVNode$4(_toDisplayString$4(message.value), 1)
          ]),
          _: 1
        }, 8, ["type"]))
      : _createCommentVNode$4("", true),
    _createVNode$4(_component_VCard, {
      flat: "",
      class: "p115-card"
    }, {
      default: _withCtx$4(() => [
        _createVNode$4(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$4(() => [...(_cache[12] || (_cache[12] = [
            _createTextVNode$4("账号与授权", -1)
          ]))]),
          _: 1
        }),
        _createVNode$4(_component_VCardText, null, {
          default: _withCtx$4(() => [
            _createElementVNode$4("div", _hoisted_2$4, [
              _createElementVNode$4("span", _hoisted_3$4, _toDisplayString$4(accountLine.value), 1),
              _cache[13] || (_cache[13] = _createElementVNode$4("span", { class: "p115-sep" }, "|", -1)),
              _createElementVNode$4("span", null, _toDisplayString$4(spaceLine.value), 1),
              (status.value?.last_check)
                ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_4$4, "检测于 " + _toDisplayString$4(status.value.last_check), 1))
                : _createCommentVNode$4("", true)
            ]),
            _createElementVNode$4("div", _hoisted_5$3, [
              _createElementVNode$4("div", _hoisted_6$3, [
                _createVNode$4(_component_VSelect, {
                  modelValue: qrApp.value,
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((qrApp).value = $event)),
                  items: qrApps.value,
                  "item-title": "title",
                  "item-value": "value",
                  label: "登录设备",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  class: "p115-qr-app",
                  disabled: Boolean(qr.value)
                }, null, 8, ["modelValue", "items", "disabled"]),
                _createVNode$4(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  loading: qrBusy.value,
                  "prepend-icon": "mdi-qrcode-scan",
                  onClick: qrStart
                }, {
                  default: _withCtx$4(() => [
                    _createTextVNode$4(_toDisplayString$4(qr.value ? '重新获取二维码' : '扫码登录'), 1)
                  ]),
                  _: 1
                }, 8, ["loading"]),
                (qr.value)
                  ? (_openBlock$4(), _createBlock$4(_component_VBtn, {
                      key: 0,
                      variant: "text",
                      color: "error",
                      "prepend-icon": "mdi-close",
                      onClick: qrCancel
                    }, {
                      default: _withCtx$4(() => [...(_cache[14] || (_cache[14] = [
                        _createTextVNode$4("取消", -1)
                      ]))]),
                      _: 1
                    }))
                  : _createCommentVNode$4("", true)
              ]),
              (qr.value?.image)
                ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_7$3, [
                    _createElementVNode$4("img", {
                      src: qr.value.image,
                      alt: "115 登录二维码",
                      class: "p115-qr-img"
                    }, null, 8, _hoisted_8$3),
                    _createElementVNode$4("div", _hoisted_9$3, [
                      _createElementVNode$4("div", _hoisted_10$3, _toDisplayString$4(qr.value.status_text || '等待扫码'), 1),
                      _cache[15] || (_cache[15] = _createElementVNode$4("div", { class: "p115-qr-tip" }, "用 115 App 扫描二维码，并在手机上点击确认", -1)),
                      _createElementVNode$4("div", _hoisted_11$3, "会话绑定设备：" + _toDisplayString$4(qr.value.app), 1),
                      (qr.value.expires_in)
                        ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_12$3, " 二维码有效期约 " + _toDisplayString$4(Math.max(1, Math.ceil(qr.value.expires_in / 60))) + " 分钟 ", 1))
                        : _createCommentVNode$4("", true)
                    ])
                  ]))
                : _createCommentVNode$4("", true)
            ]),
            _createElementVNode$4("div", _hoisted_13$3, [
              _createVNode$4(_component_VBtn, {
                color: "primary",
                variant: "flat",
                loading: busy.value === 'check',
                "prepend-icon": "mdi-connection",
                onClick: check
              }, {
                default: _withCtx$4(() => [...(_cache[16] || (_cache[16] = [
                  _createTextVNode$4(" 测试连接 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading"]),
              _createVNode$4(_component_VBtn, {
                variant: "text",
                color: "error",
                loading: busy.value === 'logout',
                "prepend-icon": "mdi-logout",
                onClick: clearCookie
              }, {
                default: _withCtx$4(() => [...(_cache[17] || (_cache[17] = [
                  _createTextVNode$4(" 清除登录态 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading"]),
              _createVNode$4(_component_VSpacer),
              _createVNode$4(_component_VBtn, {
                size: "small",
                variant: "text",
                "prepend-icon": "mdi-refresh",
                loading: loading.value,
                onClick: loadStatus
              }, {
                default: _withCtx$4(() => [...(_cache[18] || (_cache[18] = [
                  _createTextVNode$4(" 刷新状态 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading"])
            ]),
            _cache[19] || (_cache[19] = _createElementVNode$4("div", { class: "p115-hint" }, [
              _createTextVNode$4(" 登录只用"),
              _createElementVNode$4("strong", null, "扫码"),
              _createTextVNode$4("（App 通道）：115 对网页 Cookie 有设备风控，文件接口会要求「安全密钥」验证， 扫码绑定的 App 设备不会触发该验证，所以设备列表只保留 App 端。 扫码成功后 Cookie 自动保存在插件内部（不显示在界面上），也不会被「保存配置」清空； Cookie 失效时重新扫码即可。 ")
            ], -1))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$4(_component_VCard, {
      flat: "",
      class: "p115-card"
    }, {
      default: _withCtx$4(() => [
        _createVNode$4(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$4(() => [...(_cache[20] || (_cache[20] = [
            _createTextVNode$4("任务设置", -1)
          ]))]),
          _: 1
        }),
        _createVNode$4(_component_VCardText, null, {
          default: _withCtx$4(() => [
            _createVNode$4(_component_VRow, { dense: "" }, {
              default: _withCtx$4(() => [
                _createVNode$4(_component_VCol, {
                  cols: "12",
                  md: "8"
                }, {
                  default: _withCtx$4(() => [
                    _createVNode$4(_component_VTextField, {
                      modelValue: form.value.pan115_target_cid,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.value.pan115_target_cid) = $event)),
                      label: "转存文件夹 CID",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode$4(_component_VCol, {
                  cols: "12",
                  md: "4",
                  class: "d-flex align-center"
                }, {
                  default: _withCtx$4(() => [
                    _createVNode$4(_component_VBtn, {
                      size: "small",
                      variant: "tonal",
                      loading: busy.value === 'dir',
                      "prepend-icon": "mdi-folder-check-outline",
                      onClick: verifyDir
                    }, {
                      default: _withCtx$4(() => [...(_cache[21] || (_cache[21] = [
                        _createTextVNode$4(" 校验目录 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _: 1
                }),
                _createVNode$4(_component_VCol, {
                  cols: "12",
                  md: "4"
                }, {
                  default: _withCtx$4(() => [
                    _createVNode$4(_component_VTextField, {
                      modelValue: form.value.pan115_batch_max_size,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.value.pan115_batch_max_size) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      label: "单批最大链接数",
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
            _cache[22] || (_cache[22] = _createElementVNode$4("div", { class: "p115-hint" }, [
              _createTextVNode$4(" 转存与离线下载都保存到该 CID（在 115 里打开目标文件夹，地址栏 "),
              _createElementVNode$4("code", null, "cid="),
              _createTextVNode$4(" 后面就是）。 单批上限用于分批提交，避免一次提交过多被 115 拒绝。 ")
            ], -1))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$4(_component_VCard, {
      flat: "",
      class: "p115-card"
    }, {
      default: _withCtx$4(() => [
        _createVNode$4(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$4(() => [...(_cache[23] || (_cache[23] = [
            _createTextVNode$4("通知", -1)
          ]))]),
          _: 1
        }),
        _createVNode$4(_component_VCardText, null, {
          default: _withCtx$4(() => [
            _createElementVNode$4("div", _hoisted_14$3, [
              _createVNode$4(_component_VSwitch, {
                modelValue: form.value.notify_on_hit,
                "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.value.notify_on_hit) = $event)),
                color: "primary",
                "hide-details": "",
                inset: ""
              }, {
                label: _withCtx$4(() => [...(_cache[24] || (_cache[24] = [
                  _createElementVNode$4("span", { class: "p115-switch-label" }, "转存成功后通知我", -1)
                ]))]),
                _: 1
              }, 8, ["modelValue"]),
              _createVNode$4(_component_VSwitch, {
                modelValue: form.value.notify_on_error,
                "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.value.notify_on_error) = $event)),
                color: "primary",
                "hide-details": "",
                inset: ""
              }, {
                label: _withCtx$4(() => [...(_cache[25] || (_cache[25] = [
                  _createElementVNode$4("span", { class: "p115-switch-label" }, "转存失败后通知我", -1)
                ]))]),
                _: 1
              }, 8, ["modelValue"]),
              _createVNode$4(_component_VSwitch, {
                modelValue: form.value.notify_on_search,
                "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.value.notify_on_search) = $event)),
                color: "primary",
                "hide-details": "",
                inset: ""
              }, {
                label: _withCtx$4(() => [...(_cache[26] || (_cache[26] = [
                  _createElementVNode$4("span", { class: "p115-switch-label" }, "回搜到资源后通知我", -1)
                ]))]),
                _: 1
              }, 8, ["modelValue"])
            ]),
            _cache[27] || (_cache[27] = _createElementVNode$4("div", { class: "p115-hint" }, [
              _createTextVNode$4(" 这三个开关分别管一类通知，关闭哪类就收不到哪类（都走 MoviePilot 通知渠道， 用哪个渠道、发给谁跟宿主的「通知」设置一致）： "),
              _createElementVNode$4("br"),
              _createTextVNode$4("· "),
              _createElementVNode$4("strong", null, "转存成功"),
              _createTextVNode$4("：监控 / 转发命中后往 115 转存（或离线）成功，按批汇总一条（如「已转存 3 条」）； "),
              _createElementVNode$4("br"),
              _createTextVNode$4("· "),
              _createElementVNode$4("strong", null, "转存失败"),
              _createTextVNode$4("：汇总失败条数与原因，115 登录态失效会附上重新扫码的引导（同一故障 6 小时内只提醒一次）； "),
              _createElementVNode$4("br"),
              _createTextVNode$4("· "),
              _createElementVNode$4("strong", null, "回搜到资源"),
              _createTextVNode$4("：订阅回搜在缓存里找到缺失资源并推送后的结果汇总。 "),
              _createElementVNode$4("br"),
              _createTextVNode$4("通用转发本身不发送通知（转发结果在「通用转发」面板的流水里看）。 ")
            ], -1))
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$4(_component_VCard, {
      flat: "",
      class: "p115-card"
    }, {
      default: _withCtx$4(() => [
        _createVNode$4(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$4(() => [...(_cache[28] || (_cache[28] = [
            _createTextVNode$4("推送测试", -1)
          ]))]),
          _: 1
        }),
        _createVNode$4(_component_VCardText, null, {
          default: _withCtx$4(() => [
            _createVNode$4(_component_VTextarea, {
              modelValue: pushText.value,
              "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((pushText).value = $event)),
              label: "粘贴链接（115 分享链接 / 磁力 / ed2k，可多行多条）",
              placeholder: "https://115.com/s/xxxxx?password=abcd\nmagnet:?xt=urn:btih:...\ned2k://|file|...",
              rows: "3",
              density: "compact",
              variant: "outlined",
              "hide-details": ""
            }, null, 8, ["modelValue"]),
            _createElementVNode$4("div", _hoisted_15$3, [
              _createVNode$4(_component_VBtn, {
                variant: "tonal",
                loading: busy.value === 'parse',
                disabled: Boolean(busy.value) && busy.value !== 'parse',
                "prepend-icon": "mdi-text-search",
                onClick: _cache[8] || (_cache[8] = $event => (push(true)))
              }, {
                default: _withCtx$4(() => [...(_cache[29] || (_cache[29] = [
                  _createTextVNode$4(" 解析测试（不提交） ", -1)
                ]))]),
                _: 1
              }, 8, ["loading", "disabled"]),
              _createVNode$4(_component_VBtn, {
                color: "success",
                variant: "flat",
                loading: busy.value === 'push',
                disabled: Boolean(busy.value) && busy.value !== 'push',
                "prepend-icon": "mdi-cloud-upload-outline",
                onClick: _cache[9] || (_cache[9] = $event => (push(false)))
              }, {
                default: _withCtx$4(() => [...(_cache[30] || (_cache[30] = [
                  _createTextVNode$4(" 推送到 115 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading", "disabled"])
            ]),
            (pushResult.value)
              ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_16$3, [
                  _createElementVNode$4("div", _hoisted_17$3, _toDisplayString$4(pushResult.value.message), 1),
                  _createVNode$4(_component_VList, {
                    density: "compact",
                    class: "p115-result-list"
                  }, {
                    default: _withCtx$4(() => [
                      (_openBlock$4(true), _createElementBlock$4(_Fragment$4, null, _renderList$4(pushResult.value.results, (item, index) => {
                        return (_openBlock$4(), _createBlock$4(_component_VListItem, { key: index }, {
                          prepend: _withCtx$4(() => [
                            _createVNode$4(_component_VIcon, {
                              icon: item.ok ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline',
                              size: "18",
                              color: item.ok ? 'success' : 'warning'
                            }, null, 8, ["icon", "color"])
                          ]),
                          default: _withCtx$4(() => [
                            _createVNode$4(_component_VListItemTitle, { class: "p115-result-name" }, {
                              default: _withCtx$4(() => [
                                _createTextVNode$4(_toDisplayString$4(item.target), 1)
                              ]),
                              _: 2
                            }, 1024),
                            _createVNode$4(_component_VListItemSubtitle, { class: "p115-result-msg" }, {
                              default: _withCtx$4(() => [
                                _createTextVNode$4(_toDisplayString$4(item.message), 1)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _: 2
                        }, 1024))
                      }), 128))
                    ]),
                    _: 1
                  })
                ]))
              : _createCommentVNode$4("", true),
            _cache[31] || (_cache[31] = _createElementVNode$4("div", { class: "p115-hint" }, " 解析测试不需要 Cookie，可先用它确认链接能被正确识别（含提取码）。 实际推送需要已保存的 Cookie 与目标目录 CID。 ", -1))
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
const ConfigPan115Pane = /*#__PURE__*/_export_sfc(_sfc_main$4, [['__scopeId',"data-v-e2d19d80"]]);

const {resolveComponent:_resolveComponent$3,createVNode:_createVNode$3,createTextVNode:_createTextVNode$3,withCtx:_withCtx$3,toDisplayString:_toDisplayString$3,openBlock:_openBlock$3,createBlock:_createBlock$3,createCommentVNode:_createCommentVNode$3,createElementVNode:_createElementVNode$3,createElementBlock:_createElementBlock$3,renderList:_renderList$3,Fragment:_Fragment$3,unref:_unref$2} = await importShared('vue');


const _hoisted_1$3 = { class: "mon-pane" };
const _hoisted_2$3 = { class: "mon-status" };
const _hoisted_3$3 = { class: "mon-status-sub" };
const _hoisted_4$3 = { key: 0 };
const _hoisted_5$2 = { key: 1 };
const _hoisted_6$2 = { key: 2 };
const _hoisted_7$2 = {
  key: 3,
  class: "mon-flood"
};
const _hoisted_8$2 = { class: "mon-events" };
const _hoisted_9$2 = {
  key: 0,
  class: "mon-events-last"
};
const _hoisted_10$2 = {
  key: 0,
  class: "mon-sources"
};
const _hoisted_11$2 = { class: "mon-id-purpose" };
const _hoisted_12$2 = {
  key: 1,
  class: "mon-sources"
};
const _hoisted_13$2 = { class: "mon-matcher" };
const _hoisted_14$2 = {
  key: 0,
  class: "mon-matcher-warn"
};
const _hoisted_15$2 = { class: "mon-actions" };
const _hoisted_16$2 = {
  key: 0,
  class: "mon-empty"
};
const _hoisted_17$2 = { class: "mon-rule-head" };
const _hoisted_18$2 = {
  class: "mon-rule-switch",
  title: "规则总开关：关闭后这条规则暂停监听（不识别、不推送、也就没有通知）；改动随底部「保存规则」生效。"
};
const _hoisted_19$2 = { class: "mon-rule-grid" };
const _hoisted_20$2 = { class: "mon-chats" };
const _hoisted_21$2 = { class: "mon-target" };
const _hoisted_22$2 = {
  key: 1,
  class: "mon-hint"
};
const _hoisted_23$2 = {
  key: 2,
  class: "mon-hint"
};
const _hoisted_24$2 = {
  key: 3,
  class: "mon-hint"
};
const _hoisted_25$2 = { class: "mon-match" };
const _hoisted_26$2 = {
  key: 1,
  class: "mon-actions"
};
const _hoisted_27$2 = { class: "mon-actions" };
const _hoisted_28$2 = {
  key: 0,
  class: "mon-test-result"
};
const _hoisted_29$2 = { class: "mon-test-line" };
const _hoisted_30$2 = { key: 0 };
const _hoisted_31$2 = { key: 0 };
const _hoisted_32$2 = { key: 1 };
const _hoisted_33$2 = { key: 2 };
const _hoisted_34$1 = {
  key: 1,
  class: "mon-test-none"
};
const _hoisted_35$1 = {
  key: 0,
  class: "mon-test-line"
};
const _hoisted_36$1 = { class: "mon-hits-tools" };
const _hoisted_37$1 = { class: "mon-hits-time" };
const _hoisted_38$1 = { class: "mon-nowrap" };
const _hoisted_39 = { class: "mon-hits-source" };
const _hoisted_40 = { key: 0 };
const _hoisted_41 = {
  key: 1,
  class: "mon-hits-none"
};
const _hoisted_42 = { class: "mon-nowrap" };
const _hoisted_43 = { class: "mon-hits-detail" };
const _hoisted_44 = { key: 0 };
const _hoisted_45 = { class: "mon-pager" };
const _hoisted_46 = { class: "mon-pager-info" };

const {computed: computed$3,onMounted: onMounted$3,onUnmounted: onUnmounted$2,ref: ref$4,watch: watch$1} = await importShared('vue');

/**
 * ④ TG 资源监控面板。
 *
 * 数据流：规则存放在插件配置 `monitor_rules`（随主表单保存），但读写走
 * `/monitor/rules` 专用接口——保存即归一（补规则 ID）、即时生效（ensure_started），
 * 不必等插件重载。命中流水与运行态只读。
 *
 * 纪律（沿用全项目约定）：
 * - 模板/脚本用到的变量全部在 script setup 声明 ref（P1 踩过未声明引用的坑）；
 * - 重入保护只留在按钮处理器，内部 fetch 函数无保护（避免 busy 期间静默丢请求）；
 * - 新增配置项必须同步进 useConfigForm.js 的 configDefaults（保存是整份覆盖）。
 */
const hitsPageSize$1 = 20;

const _sfc_main$3 = {
  __name: 'ConfigMonitorPane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
},
  setup(__props) {

const props = __props;

const form = computed$3(() => props.config.form);

const status = ref$4(null);
const loading = ref$4(false);
const busy = ref$4('');
const message = ref$4('');
const messageOk = ref$4(true);
const destinations = ref$4([
  { value: 'smart', title: '智能（115 可用则转存，否则仅记录）' },
  { value: 'pan115', title: '115 网盘（分享转存 / 磁力 eD2k 离线）' },
  { value: 'tg_forward', title: 'TG 转发（转发原消息到目标会话）' },
  { value: 'none', title: '仅记录（不推送）' },
]);
const decisions = ref$4([
  { value: 'hit', title: '已推送' },
  { value: 'skipped_not_missing', title: '不缺（已存在）' },
  { value: 'skipped_not_subscribed', title: '未订阅' },
  { value: 'skipped_unrecognized', title: '无法识别' },
  { value: 'skipped_keyword', title: '关键词未命中' },
  { value: 'skipped_no_link', title: '无链接' },
  { value: 'skipped_unknown', title: '无法判断缺失' },
  { value: 'failed', title: '处理失败' },
]);
const rules = ref$4([]);
const dialogs = ref$4([]);

const testText = ref$4('');
const testResult = ref$4(null);

const hits = ref$4([]);
const hitsTotal = ref$4(0);
const hitsPage = ref$4(1);
const decisionFilter = ref$4('');
// 关键词用可写 computed 包一层：Vuetify 的 clearable 清除按钮会把模型置为 null，
// 直接 ref('') 收 null 会让各处 .trim() 抛错（1.6.6 真机反馈：清空关键词后列表不刷新），
// 这里在入口统一归一成字符串，模板与脚本就都不用到处防 null。
const hitKeywordRaw = ref$4('');
const hitKeyword = computed$3({
  get: () => String(hitKeywordRaw.value ?? ''),
  set: (value) => { hitKeywordRaw.value = value == null ? '' : String(value); },
});
const clearDialog = ref$4(false);
const clearTarget = ref$4('filtered');
const clearing = ref$4(false);

let refreshTimer = null;
let keywordTimer = null;

function setMessage(text, ok = true) {
  message.value = text || '';
  messageOk.value = ok;
}

function newRuleId() {
  return 'r' + Math.random().toString(16).slice(2, 10)
}

function blankRule() {
  return {
    id: newRuleId(),
    name: '',
    source_ids: [],
    destination: 'smart',
    target_id: '',
    match_only_if_missing: true,
    match_custom_keywords: false,
    custom_keywords: [],
    rule_type: 'client',
    web_channel_usernames: [],
    enabled: true,
  }
}

// ------------------------------------------------------------------ 数据加载（无重入保护，供按钮与内部调用共用）

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'monitor/status', { timeoutMs: 15000 }));
  } catch (err) {
    setMessage(err?.message || '读取监控状态失败', false);
  }
}

async function loadRules() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'monitor/rules', { timeoutMs: 15000 }));
    if (data?.destinations?.length) destinations.value = data.destinations;
    if (data?.decisions?.length) decisions.value = data.decisions;
    const list = Array.isArray(data?.rules) ? data.rules : [];
    rules.value = list.map(rule => ({
      id: rule.id || newRuleId(),
      name: rule.name || '',
      source_ids: Array.isArray(rule.source_ids) ? rule.source_ids.map(Number) : [],
      destination: rule.destination || 'smart',
      target_id: rule.target_id || '',
      match_only_if_missing: rule.match_only_if_missing !== false,
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: Array.isArray(rule.custom_keywords) ? rule.custom_keywords : [],
      rule_type: rule.rule_type || 'client',
      web_channel_usernames: Array.isArray(rule.web_channel_usernames) ? rule.web_channel_usernames : [],
      enabled: rule.enabled !== false,
    }));
    syncRulesToForm();
  } catch (err) {
    setMessage(err?.message || '读取监控规则失败', false);
  }
}

async function loadDialogs() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'telegram/dialogs', { timeoutMs: 15000 }));
    dialogs.value = data?.dialogs || [];
  } catch {
    // 对话列表拉不到不影响规则编辑（下拉为空，可刷新后再选）
    dialogs.value = [];
  }
}

async function loadHits() {
  try {
    const params = new URLSearchParams();
    params.set('page', String(hitsPage.value));
    params.set('page_size', String(hitsPageSize$1));
    if (decisionFilter.value) params.set('decision', decisionFilter.value);
    if (hitKeyword.value.trim()) params.set('keyword', hitKeyword.value.trim());
    const data = unwrap(await getPluginApi(
      props.api, props.pluginId, `monitor/hits?${params.toString()}`, { timeoutMs: 15000 },
    ));
    hits.value = data?.items || [];
    hitsTotal.value = data?.total || 0;
  } catch (err) {
    setMessage(err?.message || '读取命中流水失败', false);
  }
}

// 关键词输入防抖 300ms：边打字边查会把后端打满（流水表可能上万行）
watch$1(hitKeyword, () => {
  clearTimeout(keywordTimer);
  keywordTimer = setTimeout(() => {
    hitsPage.value = 1;
    loadHits();
  }, 300);
});

// 当前是否有筛选条件（删除对话框据此说明"删多少"，与后端删除口径严格一致）
const hasFilter = computed$3(() => Boolean(decisionFilter.value || hitKeyword.value.trim()));
const filterText = computed$3(() => [
  decisionFilter.value ? `决策=${decisionLabel(decisionFilter.value)}` : '',
  hitKeyword.value.trim() ? `关键词=${hitKeyword.value.trim()}` : '',
].filter(Boolean).join(' / '));

function askClear(target) {
  if (!hitsTotal.value) {
    setMessage(target === 'all' ? '当前视图没有可清空的流水' : '当前筛选没有可删除的流水');
    return
  }
  clearTarget.value = target;
  clearDialog.value = true;
}

async function runClear() {
  if (clearing.value) return
  clearing.value = true;
  try {
    // 无论点哪个删除按钮，都只删「当前视图」：带上决策与关键词筛选，
    // 没有筛选才是清空本类全部（后端按 kind 隔离，不会碰到转发流水）。
    // 1.6.6 真机反馈：原来「清空本类流水」忽略筛选直接删整个 kind，对话框却
    // 显示筛选后的条数——用户确认「共 3 条」结果丢了全部流水。
    const payload = { decision: decisionFilter.value || '', keyword: hitKeyword.value.trim() };
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'monitor/hits/clear', payload, { timeoutMs: 30000 },
    ));
    setMessage(data?.message || '已清理流水');
    clearDialog.value = false;
    hitsPage.value = 1;
    await Promise.all([loadHits(), loadStatus()]);
  } catch (err) {
    setMessage(err?.message || '清理流水失败', false);
  } finally {
    clearing.value = false;
  }
}

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadStatus(), loadRules(), loadHits(), loadDialogs()]);
    setMessage('状态已刷新');
  } finally {
    loading.value = false;
  }
}

// ------------------------------------------------------------------ 规则编辑

function syncRulesToForm() {
  // 规则必须留在主表单里：宿主「保存配置」是整份覆盖，表单没有的字段会被清空
  form.value.monitor_rules = rules.value;
}

function addRule() {
  rules.value.push(blankRule());
  syncRulesToForm();
}

function removeRule(index) {
  rules.value.splice(index, 1);
  syncRulesToForm();
}

async function saveRules() {
  if (busy.value) return
  busy.value = 'save';
  setMessage('正在保存规则…');
  try {
    const payload = rules.value.map(rule => ({
      id: rule.id,
      name: String(rule.name || '').trim() || '未命名规则',
      source_ids: rule.source_ids,
      destination: rule.destination,
      target_id: String(rule.target_id || '').trim(),
      match_only_if_missing: Boolean(rule.match_only_if_missing),
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: (rule.custom_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      rule_type: rule.rule_type || 'client',
      web_channel_usernames: rule.web_channel_usernames || [],
      enabled: rule.enabled !== false,
    }));
    const data = unwrap(await putPluginApi(props.api, props.pluginId, 'monitor/rules', { rules: payload }, { timeoutMs: 30000 }));
    if (Array.isArray(data?.rules)) {
      rules.value = data.rules;
      syncRulesToForm();
    }
    setMessage(`已保存 ${payload.length} 条规则，监控已进入运行态`);
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '保存规则失败', false);
  } finally {
    busy.value = '';
  }
}

// ------------------------------------------------------------------ 规则测试

async function runTest() {
  if (busy.value) return
  busy.value = 'test';
  setMessage('正在测试…');
  testResult.value = null;
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'monitor/test', { text: testText.value }, { timeoutMs: 30000 },
    ));
    testResult.value = data;
    setMessage('测试完成（未落库、未推送）');
  } catch (err) {
    setMessage(err?.message || '测试失败', false);
  } finally {
    busy.value = '';
  }
}

// ------------------------------------------------------------------ 命中流水分页

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
  if (hitsPage.value * hitsPageSize$1 >= hitsTotal.value) return
  hitsPage.value += 1;
  loadHits();
}

// ------------------------------------------------------------------ 展示辅助

const dialogOptions = computed$3(() =>
  (dialogs.value || []).map(item => ({
    title: `${item.name}（${item.type}）`,
    value: Number(item.id),
  })),
);

// 下拉选项 = 对话列表 + 已保存但不在缓存里的 ID（老规则/缓存过期时保证 chips 仍能显示）
const selectItems = computed$3(() => {
  const items = dialogOptions.value.slice();
  const known = new Set(items.map(item => item.value));
  for (const rule of rules.value) {
    for (const raw of rule.source_ids || []) {
      const id = Number(raw);
      if (id && !known.has(id)) {
        items.push({ title: String(id), value: id });
        known.add(id);
      }
    }
  }
  return items
});

// 转发目标下拉（推送目标 = TG 转发时）：同一份对话缓存 + 已保存的目标值兜底
const targetItems = computed$3(() => {
  const items = dialogOptions.value.slice();
  const known = new Set(items.map(item => item.value));
  for (const rule of rules.value) {
    const id = Number(rule.target_id);
    if (id && !known.has(id)) {
      items.push({ title: String(id), value: id });
      known.add(id);
    }
  }
  return items
});

// 关心会话的用途标注（监控 / 缓存 / 两者）
function purposeLabel(purposes) {
  const list = Array.isArray(purposes) ? purposes : [];
  return list.length ? list.join('+') : '监控'
}

// 来源会话配色：监控优先，其次缓存
function sourceColor(source) {
  if (source?.watched && source?.cached) return 'primary'
  if (source?.watched) return 'success'
  if (source?.cached) return 'info'
  return 'default'
}

const matcherReady = computed$3(() => {
  const matcher = status.value?.matcher || {};
  return Boolean(matcher.mediaserver_available || (matcher.subscriptions ?? 0) > 0)
});

// 监听会话 ID → 反查标题（来自状态卡 watched_detail），命中流水「来源」列展示用
const chatTitleMap = computed$3(() => {
  const map = {};
  for (const w of (status.value?.pipeline?.watched_detail || [])) {
    if (w.resolved && w.title) map[w.chat_id] = w.title;
  }
  return map
});

// 媒体列完整名：片名（年份）+ 电视剧 SxxExx（如「青与碧 (2026) S01E02」；
// 多集区间拼 S01E05-E06）
function mediaName(item) {
  if (!item.title) return ''
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

// 流水时间去掉 ISO 的 T 分隔（2026-10-13T11:01:08 → 2026-10-13 11:01:08）
function fmtTime(value) {
  return String(value || '').replace('T', ' ')
}

onMounted$3(async () => {
  await refreshAll();
  // 轻量轮询：监控是长驻进程，状态卡保持新鲜（命中流水变化慢，不轮询）
  refreshTimer = window.setInterval(loadStatus, 15000);
});

onUnmounted$2(() => {
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
  const _component_VSwitch = _resolveComponent$3("VSwitch");
  const _component_VCardTitle = _resolveComponent$3("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$3("VCardSubtitle");
  const _component_VCardItem = _resolveComponent$3("VCardItem");
  const _component_VCard = _resolveComponent$3("VCard");
  const _component_VAlert = _resolveComponent$3("VAlert");
  const _component_VChip = _resolveComponent$3("VChip");
  const _component_VBtn = _resolveComponent$3("VBtn");
  const _component_VCardText = _resolveComponent$3("VCardText");
  const _component_VTextField = _resolveComponent$3("VTextField");
  const _component_VSelect = _resolveComponent$3("VSelect");
  const _component_VCombobox = _resolveComponent$3("VCombobox");
  const _component_VTextarea = _resolveComponent$3("VTextarea");
  const _component_VIcon = _resolveComponent$3("VIcon");
  const _component_VListItemTitle = _resolveComponent$3("VListItemTitle");
  const _component_VListItemSubtitle = _resolveComponent$3("VListItemSubtitle");
  const _component_VListItem = _resolveComponent$3("VListItem");
  const _component_VList = _resolveComponent$3("VList");
  const _component_VTable = _resolveComponent$3("VTable");
  const _component_VSpacer = _resolveComponent$3("VSpacer");
  const _component_VCardActions = _resolveComponent$3("VCardActions");
  const _component_VDialog = _resolveComponent$3("VDialog");

  return (_openBlock$3(), _createElementBlock$3("div", _hoisted_1$3, [
    _createVNode$3(_component_VCard, {
      flat: "",
      class: "mon-card"
    }, {
      default: _withCtx$3(() => [
        _createVNode$3(_component_VCardItem, null, {
          prepend: _withCtx$3(() => [
            _createVNode$3(_component_VSwitch, {
              modelValue: form.value.monitor_enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.value.monitor_enabled) = $event)),
              color: "primary",
              "hide-details": "",
              inset: ""
            }, null, 8, ["modelValue"])
          ]),
          default: _withCtx$3(() => [
            _createVNode$3(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$3(() => [...(_cache[8] || (_cache[8] = [
                _createTextVNode$3("启用 TG 资源监控", -1)
              ]))]),
              _: 1
            }),
            _createVNode$3(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx$3(() => [...(_cache[9] || (_cache[9] = [
                _createTextVNode$3(" 监听指定频道 / 群组的新消息，经净化与宿主识别后按规则决策，命中即入推送队列（开关随「保存配置」生效）。 ", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    (message.value)
      ? (_openBlock$3(), _createBlock$3(_component_VAlert, {
          key: 0,
          type: messageOk.value ? 'info' : 'warning',
          variant: "tonal",
          density: "comfortable",
          class: "mon-message"
        }, {
          default: _withCtx$3(() => [
            _createTextVNode$3(_toDisplayString$3(message.value), 1)
          ]),
          _: 1
        }, 8, ["type"]))
      : _createCommentVNode$3("", true),
    _createVNode$3(_component_VCard, {
      flat: "",
      class: "mon-card"
    }, {
      default: _withCtx$3(() => [
        _createVNode$3(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$3(() => [...(_cache[10] || (_cache[10] = [
            _createTextVNode$3("运行状态", -1)
          ]))]),
          _: 1
        }),
        _createVNode$3(_component_VCardText, null, {
          default: _withCtx$3(() => [
            _createElementVNode$3("div", _hoisted_2$3, [
              _createVNode$3(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: status.value?.enabled ? 'success' : 'default',
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 监控" + _toDisplayString$3(status.value?.enabled ? '已启用' : '未启用'), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode$3(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: status.value?.pipeline?.running ? 'success' : 'warning',
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 流水线" + _toDisplayString$3(status.value?.pipeline?.running ? '运行中' : '未运行'), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode$3(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: status.value?.pipeline?.handler_registered ? 'success' : 'warning',
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 消息监听" + _toDisplayString$3(status.value?.pipeline?.handler_registered ? '已注册' : '未注册'), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode$3(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: "info",
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 关心会话 " + _toDisplayString$3(status.value?.watched_chats ?? 0), 1)
                ]),
                _: 1
              }),
              _createVNode$3(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: "primary",
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 规则 " + _toDisplayString$3(status.value?.rules_count ?? 0), 1)
                ]),
                _: 1
              }),
              _createVNode$3(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: "primary",
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 队列待处理 " + _toDisplayString$3(status.value?.pipeline?.push_pending ?? 0), 1)
                ]),
                _: 1
              }),
              ((status.value?.pipeline?.push_done ?? 0) > 0)
                ? (_openBlock$3(), _createBlock$3(_component_VChip, {
                    key: 0,
                    size: "small",
                    variant: "tonal",
                    color: "success",
                    label: ""
                  }, {
                    default: _withCtx$3(() => [
                      _createTextVNode$3(" 推送完成 " + _toDisplayString$3(status.value.pipeline.push_done), 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$3("", true),
              ((status.value?.pipeline?.push_failed ?? 0) > 0)
                ? (_openBlock$3(), _createBlock$3(_component_VChip, {
                    key: 1,
                    size: "small",
                    variant: "tonal",
                    color: "error",
                    label: ""
                  }, {
                    default: _withCtx$3(() => [
                      _createTextVNode$3(" 失败 " + _toDisplayString$3(status.value.pipeline.push_failed), 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$3("", true)
            ]),
            _createElementVNode$3("div", _hoisted_3$3, [
              (status.value?.pipeline?.started_at)
                ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_4$3, "启动于 " + _toDisplayString$3(status.value.pipeline.started_at), 1))
                : _createCommentVNode$3("", true),
              (status.value?.pipeline?.buffered || status.value?.pipeline?.queued)
                ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_5$2, " 缓冲 " + _toDisplayString$3(status.value.pipeline.buffered) + " · 待处理 " + _toDisplayString$3(status.value.pipeline.queued), 1))
                : _createCommentVNode$3("", true),
              (status.value?.gate_interval)
                ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_6$2, "转发冷却 " + _toDisplayString$3(status.value.gate_interval) + " 秒", 1))
                : _createCommentVNode$3("", true),
              (status.value?.flood_remaining > 0)
                ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_7$2, " FloodWait 退避中（约 " + _toDisplayString$3(status.value.flood_remaining) + " 秒） ", 1))
                : _createCommentVNode$3("", true)
            ]),
            _createElementVNode$3("div", _hoisted_8$2, [
              _cache[11] || (_cache[11] = _createElementVNode$3("span", { class: "mon-events-title" }, "事件：", -1)),
              _createVNode$3(_component_VChip, {
                size: "x-small",
                variant: "tonal",
                color: "info",
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 收到 " + _toDisplayString$3(status.value?.pipeline?.events_received ?? 0), 1)
                ]),
                _: 1
              }),
              _createVNode$3(_component_VChip, {
                size: "x-small",
                variant: "tonal",
                color: (status.value?.pipeline?.events_watched ?? 0) > 0 ? 'success' : 'default',
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 命中监听 " + _toDisplayString$3(status.value?.pipeline?.events_watched ?? 0), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode$3(_component_VChip, {
                size: "x-small",
                variant: "tonal",
                color: "default",
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 非监听 " + _toDisplayString$3(status.value?.pipeline?.events_unwatched ?? 0), 1)
                ]),
                _: 1
              }),
              _createVNode$3(_component_VChip, {
                size: "x-small",
                variant: "tonal",
                color: "primary",
                label: ""
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 已入队 " + _toDisplayString$3(status.value?.pipeline?.messages_enqueued ?? 0), 1)
                ]),
                _: 1
              }),
              (status.value?.pipeline?.last_event_at)
                ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_9$2, " 最近事件 " + _toDisplayString$3(status.value.pipeline.last_event_at), 1))
                : _createCommentVNode$3("", true)
            ]),
            ((status.value?.watched_chat_ids?.length || 0) > 0)
              ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_10$2, [
                  _cache[12] || (_cache[12] = _createElementVNode$3("span", { class: "mon-events-title" }, "关心会话：", -1)),
                  ((status.value?.pipeline?.watched_detail?.length || 0) > 0)
                    ? (_openBlock$3(true), _createElementBlock$3(_Fragment$3, { key: 0 }, _renderList$3(status.value.pipeline.watched_detail, (item) => {
                        return (_openBlock$3(), _createBlock$3(_component_VChip, {
                          key: `watch-${item.chat_id}`,
                          size: "x-small",
                          variant: "tonal",
                          color: item.resolved ? 'success' : 'error',
                          label: "",
                          class: "mon-id-chip",
                          title: item.resolved ? `会话标题：${item.title}` : `反查失败：${item.error}`
                        }, {
                          default: _withCtx$3(() => [
                            _createTextVNode$3(_toDisplayString$3(item.chat_id), 1),
                            (item.resolved)
                              ? (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 0 }, [
                                  _createTextVNode$3(" ▸ " + _toDisplayString$3(item.title || '(无标题)'), 1)
                                ], 64))
                              : (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 1 }, [
                                  _createTextVNode$3(" ▸ 反查失败")
                                ], 64)),
                            _createElementVNode$3("span", _hoisted_11$2, "［" + _toDisplayString$3(purposeLabel(item.purposes)) + "］", 1)
                          ]),
                          _: 2
                        }, 1032, ["color", "title"]))
                      }), 128))
                    : (_openBlock$3(true), _createElementBlock$3(_Fragment$3, { key: 1 }, _renderList$3(status.value.watched_chat_ids, (chatId) => {
                        return (_openBlock$3(), _createBlock$3(_component_VChip, {
                          key: `watch-${chatId}`,
                          size: "x-small",
                          variant: "tonal",
                          color: "warning",
                          label: "",
                          class: "mon-id-chip"
                        }, {
                          default: _withCtx$3(() => [
                            _createTextVNode$3(_toDisplayString$3(chatId), 1)
                          ]),
                          _: 2
                        }, 1024))
                      }), 128))
                ]))
              : _createCommentVNode$3("", true),
            ((status.value?.pipeline?.recent_sources?.length || 0) > 0)
              ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_12$2, [
                  _cache[13] || (_cache[13] = _createElementVNode$3("span", { class: "mon-events-title" }, "来源 ID：", -1)),
                  (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(status.value.pipeline.recent_sources.slice(0, 12), (source) => {
                    return (_openBlock$3(), _createBlock$3(_component_VChip, {
                      key: `src-${source.chat_id}`,
                      size: "x-small",
                      variant: "tonal",
                      color: sourceColor(source),
                      label: "",
                      class: "mon-id-chip",
                      title: `监控：${source.watched ? '是' : '否'} · 缓存：${source.cached ? '是' : '否'}`
                    }, {
                      default: _withCtx$3(() => [
                        _createTextVNode$3(_toDisplayString$3(source.chat_id) + " ×" + _toDisplayString$3(source.count), 1)
                      ]),
                      _: 2
                    }, 1032, ["color", "title"]))
                  }), 128)),
                  _cache[14] || (_cache[14] = _createElementVNode$3("span", { class: "mon-events-last" }, "绿=监控，蓝=仅缓存，灰=无关", -1))
                ]))
              : _createCommentVNode$3("", true),
            (status.value?.enabled && (status.value?.pipeline?.events_received > 0) && !(status.value?.pipeline?.events_watched > 0))
              ? (_openBlock$3(), _createBlock$3(_component_VAlert, {
                  key: 2,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mon-events-hint"
                }, {
                  default: _withCtx$3(() => [
                    _createTextVNode$3(" 收到 " + _toDisplayString$3(status.value.pipeline.events_received) + " 条事件，但没有一条来自监听会话。 常见原因：①监听 ID「反查失败」＝账号看不到该会话（ID 失效或选错，到「TG 凭证」页刷新对话后重选并保存规则） ②规则里选错频道（名字相近的频道多选）③账号已退出该频道（重新加入后刷新对话列表重选）。 ", 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode$3("", true),
            (status.value?.enabled && !(status.value?.pipeline?.events_received > 0))
              ? (_openBlock$3(), _createBlock$3(_component_VAlert, {
                  key: 3,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mon-events-hint"
                }, {
                  default: _withCtx$3(() => [...(_cache[15] || (_cache[15] = [
                    _createTextVNode$3(" 还没收到任何 TG 事件：请确认 ①TG 凭证已登录且「已连接」 ②消息监听徽章为「已注册」 ③规则监听的频道 ID 正确（可在「TG 凭证」页刷新对话列表后点条目复制 ID，或点「保存规则」后重试）。 收到事件后这里会显示计数。 ", -1)
                  ]))]),
                  _: 1
                }))
              : _createCommentVNode$3("", true),
            _createElementVNode$3("div", _hoisted_13$2, [
              _cache[16] || (_cache[16] = _createTextVNode$3(" 缺失判断： ", -1)),
              _createVNode$3(_component_VChip, {
                size: "x-small",
                variant: "tonal",
                color: matcherReady.value ? 'success' : 'warning',
                label: "",
                class: "mon-matcher-chip"
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 媒体服务器" + _toDisplayString$3(status.value?.matcher?.mediaserver ? `（${status.value.matcher.mediaserver}）` : (status.value?.matcher?.mediaserver_available ? '已就绪' : '未配置')), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode$3(_component_VChip, {
                size: "x-small",
                variant: "tonal",
                color: "info",
                label: "",
                class: "mon-matcher-chip"
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(" 订阅 " + _toDisplayString$3(status.value?.matcher?.subscriptions ?? 0), 1)
                ]),
                _: 1
              }),
              (!matcherReady.value)
                ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_14$2, " 两项都不可用，「仅缺失」规则会因无法判断而全部跳过；请在 MoviePilot 配置媒体服务器或建立订阅。 "))
                : _createCommentVNode$3("", true)
            ]),
            _createElementVNode$3("div", _hoisted_15$2, [
              _createVNode$3(_component_VBtn, {
                size: "small",
                variant: "tonal",
                "prepend-icon": "mdi-refresh",
                loading: loading.value,
                onClick: refreshAll
              }, {
                default: _withCtx$3(() => [...(_cache[17] || (_cache[17] = [
                  _createTextVNode$3(" 刷新状态 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading"])
            ])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$3(_component_VCard, {
      flat: "",
      class: "mon-card"
    }, {
      default: _withCtx$3(() => [
        _createVNode$3(_component_VCardItem, null, {
          append: _withCtx$3(() => [
            _createVNode$3(_component_VBtn, {
              size: "small",
              variant: "tonal",
              "prepend-icon": "mdi-plus",
              onClick: addRule
            }, {
              default: _withCtx$3(() => [...(_cache[19] || (_cache[19] = [
                _createTextVNode$3("添加规则", -1)
              ]))]),
              _: 1
            })
          ]),
          default: _withCtx$3(() => [
            _createVNode$3(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$3(() => [...(_cache[18] || (_cache[18] = [
                _createTextVNode$3("监控规则", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$3(_component_VCardText, null, {
          default: _withCtx$3(() => [
            (!rules.value.length)
              ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_16$2, " 还没有规则。点「添加规则」创建第一条：选择监听频道、推送目标，保存后立即生效。 "))
              : _createCommentVNode$3("", true),
            (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(rules.value, (rule, index) => {
              return (_openBlock$3(), _createBlock$3(_component_VCard, {
                key: rule.id || index,
                flat: "",
                class: "mon-rule"
              }, {
                default: _withCtx$3(() => [
                  _createVNode$3(_component_VCardText, null, {
                    default: _withCtx$3(() => [
                      _createElementVNode$3("div", _hoisted_17$2, [
                        _createVNode$3(_component_VTextField, {
                          modelValue: rule.name,
                          "onUpdate:modelValue": $event => ((rule.name) = $event),
                          label: "规则名称",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          class: "mon-rule-name"
                        }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                        _createElementVNode$3("div", _hoisted_18$2, [
                          _createVNode$3(_component_VSwitch, {
                            modelValue: rule.enabled,
                            "onUpdate:modelValue": $event => ((rule.enabled) = $event),
                            color: "success",
                            "hide-details": "",
                            inset: "",
                            density: "compact"
                          }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                          _cache[20] || (_cache[20] = _createElementVNode$3("span", { class: "mon-switch-label" }, "启用规则", -1))
                        ]),
                        _createVNode$3(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          color: "error",
                          "prepend-icon": "mdi-delete-outline",
                          onClick: $event => (removeRule(index))
                        }, {
                          default: _withCtx$3(() => [...(_cache[21] || (_cache[21] = [
                            _createTextVNode$3(" 删除 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"])
                      ]),
                      _createElementVNode$3("div", _hoisted_19$2, [
                        _createElementVNode$3("div", _hoisted_20$2, [
                          _createVNode$3(_component_VSelect, {
                            modelValue: rule.source_ids,
                            "onUpdate:modelValue": $event => ((rule.source_ids) = $event),
                            items: selectItems.value,
                            "item-title": "title",
                            "item-value": "value",
                            label: "监听频道 / 群组",
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue", "items"]),
                          _cache[22] || (_cache[22] = _createElementVNode$3("div", { class: "mon-hint" }, " 下拉项来自「TG 凭证」页的对话列表缓存；看不到想要的会话，先到「TG 凭证」页刷新对话列表再点「刷新状态」。 ", -1))
                        ]),
                        _createElementVNode$3("div", _hoisted_21$2, [
                          _createVNode$3(_component_VSelect, {
                            modelValue: rule.destination,
                            "onUpdate:modelValue": $event => ((rule.destination) = $event),
                            items: destinations.value,
                            "item-title": "title",
                            "item-value": "value",
                            label: "推送目标",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue", "items"]),
                          (rule.destination === 'tg_forward')
                            ? (_openBlock$3(), _createBlock$3(_component_VSelect, {
                                key: 0,
                                modelValue: rule.target_id,
                                "onUpdate:modelValue": $event => ((rule.target_id) = $event),
                                items: targetItems.value,
                                "item-title": "title",
                                "item-value": "value",
                                label: "转发目标频道 / 群组",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": "",
                                class: "mon-target-id"
                              }, null, 8, ["modelValue", "onUpdate:modelValue", "items"]))
                            : _createCommentVNode$3("", true),
                          (rule.destination === 'smart')
                            ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_22$2, " 智能：115 已启用且已登录时转存到 115，否则仅记录。 "))
                            : _createCommentVNode$3("", true),
                          (rule.destination === 'pan115')
                            ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_23$2, " 推送到 115（分享转存 / 磁力 / eD2k 离线），需在「115 网盘」页完成扫码登录。 "))
                            : _createCommentVNode$3("", true),
                          (rule.destination === 'tg_forward')
                            ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_24$2, " 转发原消息到所选会话；目标必须是当前账号能看到的会话。 "))
                            : _createCommentVNode$3("", true)
                        ]),
                        _createElementVNode$3("div", _hoisted_25$2, [
                          _createVNode$3(_component_VSwitch, {
                            modelValue: rule.match_only_if_missing,
                            "onUpdate:modelValue": $event => ((rule.match_only_if_missing) = $event),
                            color: "primary",
                            "hide-details": "",
                            inset: ""
                          }, {
                            label: _withCtx$3(() => [...(_cache[23] || (_cache[23] = [
                              _createElementVNode$3("span", { class: "mon-switch-label" }, "仅缺失时推送", -1)
                            ]))]),
                            _: 1
                          }, 8, ["modelValue", "onUpdate:modelValue"]),
                          _cache[25] || (_cache[25] = _createElementVNode$3("div", { class: "mon-hint" }, "按 MP 媒体服务器与订阅状态判断；无法判断时命中会跳过。", -1)),
                          _createVNode$3(_component_VSwitch, {
                            modelValue: rule.match_custom_keywords,
                            "onUpdate:modelValue": $event => ((rule.match_custom_keywords) = $event),
                            color: "primary",
                            "hide-details": "",
                            inset: ""
                          }, {
                            label: _withCtx$3(() => [...(_cache[24] || (_cache[24] = [
                              _createElementVNode$3("span", { class: "mon-switch-label" }, "自定义关键词过滤", -1)
                            ]))]),
                            _: 1
                          }, 8, ["modelValue", "onUpdate:modelValue"]),
                          (rule.match_custom_keywords)
                            ? (_openBlock$3(), _createBlock$3(_component_VCombobox, {
                                key: 0,
                                modelValue: rule.custom_keywords,
                                "onUpdate:modelValue": $event => ((rule.custom_keywords) = $event),
                                multiple: "",
                                chips: "",
                                "closable-chips": "",
                                label: "关键词（任一命中即通过）",
                                density: "compact",
                                variant: "outlined",
                                "hide-details": "",
                                class: "mon-keywords"
                              }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                            : _createCommentVNode$3("", true)
                        ])
                      ])
                    ]),
                    _: 2
                  }, 1024)
                ]),
                _: 2
              }, 1024))
            }), 128)),
            (rules.value.length)
              ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_26$2, [
                  _createVNode$3(_component_VBtn, {
                    color: "primary",
                    variant: "flat",
                    "prepend-icon": "mdi-content-save-outline",
                    loading: busy.value === 'save',
                    onClick: saveRules
                  }, {
                    default: _withCtx$3(() => [...(_cache[26] || (_cache[26] = [
                      _createTextVNode$3(" 保存规则（即时生效） ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"]),
                  _cache[27] || (_cache[27] = _createElementVNode$3("span", { class: "mon-hint" }, " 「保存规则」把所有改动（含每条规则右上角的「启用规则」开关）立即写进配置并生效。 ", -1))
                ]))
              : _createCommentVNode$3("", true)
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$3(_component_VCard, {
      flat: "",
      class: "mon-card"
    }, {
      default: _withCtx$3(() => [
        _createVNode$3(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$3(() => [...(_cache[28] || (_cache[28] = [
            _createTextVNode$3("规则测试", -1)
          ]))]),
          _: 1
        }),
        _createVNode$3(_component_VCardText, null, {
          default: _withCtx$3(() => [
            _createVNode$3(_component_VTextarea, {
              modelValue: testText.value,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((testText).value = $event)),
              label: "粘贴一条频道消息原文",
              placeholder: "剧名.S01E02.2160p.WEB-DL\nhttps://115.com/s/xxxxx?password=abcd",
              rows: "3",
              density: "compact",
              variant: "outlined",
              "hide-details": ""
            }, null, 8, ["modelValue"]),
            _createElementVNode$3("div", _hoisted_27$2, [
              _createVNode$3(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-test-tube",
                loading: busy.value === 'test',
                onClick: runTest
              }, {
                default: _withCtx$3(() => [...(_cache[29] || (_cache[29] = [
                  _createTextVNode$3(" 测试（不落库、不推送） ", -1)
                ]))]),
                _: 1
              }, 8, ["loading"])
            ]),
            (testResult.value)
              ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_28$2, [
                  _createElementVNode$3("div", _hoisted_29$2, [
                    _cache[30] || (_cache[30] = _createElementVNode$3("strong", null, "识别结果：", -1)),
                    (testResult.value.recognized)
                      ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_30$2, [
                          _createTextVNode$3(" 《" + _toDisplayString$3(testResult.value.recognized.title) + "》 ", 1),
                          (testResult.value.recognized.year)
                            ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_31$2, "（" + _toDisplayString$3(testResult.value.recognized.year) + "）", 1))
                            : _createCommentVNode$3("", true),
                          (testResult.value.recognized.season)
                            ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_32$2, " S" + _toDisplayString$3(String(testResult.value.recognized.season).padStart(2, '0')), 1))
                            : _createCommentVNode$3("", true),
                          (testResult.value.recognized.episode)
                            ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_33$2, [
                                _createTextVNode$3("E" + _toDisplayString$3(String(testResult.value.recognized.episode).padStart(2, '0')), 1),
                                (testResult.value.recognized.episode_end && testResult.value.recognized.episode_end !== testResult.value.recognized.episode)
                                  ? (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 0 }, [
                                      _createTextVNode$3("-E" + _toDisplayString$3(String(testResult.value.recognized.episode_end).padStart(2, '0')), 1)
                                    ], 64))
                                  : _createCommentVNode$3("", true)
                              ]))
                            : _createCommentVNode$3("", true),
                          _createTextVNode$3(" · " + _toDisplayString$3(testResult.value.recognized.media_type === 'tv' ? '剧集' : '电影'), 1)
                        ]))
                      : (_openBlock$3(), _createElementBlock$3("span", _hoisted_34$1, "无法识别（标题格式特殊或宿主识别引擎不可用）"))
                  ]),
                  (testResult.value.links?.length)
                    ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_35$1, [
                        _createElementVNode$3("strong", null, "解析到 " + _toDisplayString$3(testResult.value.links.length) + " 个链接", 1)
                      ]))
                    : _createCommentVNode$3("", true),
                  _createVNode$3(_component_VList, {
                    density: "compact",
                    class: "mon-test-list"
                  }, {
                    default: _withCtx$3(() => [
                      (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(testResult.value.rules, (trace, index) => {
                        return (_openBlock$3(), _createBlock$3(_component_VListItem, { key: index }, {
                          prepend: _withCtx$3(() => [
                            _createVNode$3(_component_VIcon, {
                              icon: trace.decision === 'hit' ? 'mdi-check-circle-outline' : 'mdi-minus-circle-outline',
                              size: "18",
                              color: trace.decision === 'hit' ? 'success' : 'warning'
                            }, null, 8, ["icon", "color"])
                          ]),
                          default: _withCtx$3(() => [
                            _createVNode$3(_component_VListItemTitle, { class: "mon-test-name" }, {
                              default: _withCtx$3(() => [
                                _createTextVNode$3(_toDisplayString$3(trace.rule_name) + " ", 1),
                                (!trace.enabled)
                                  ? (_openBlock$3(), _createBlock$3(_component_VChip, {
                                      key: 0,
                                      size: "x-small",
                                      variant: "tonal",
                                      color: "default",
                                      label: "",
                                      class: "mon-test-off"
                                    }, {
                                      default: _withCtx$3(() => [...(_cache[31] || (_cache[31] = [
                                        _createTextVNode$3("已停用", -1)
                                      ]))]),
                                      _: 1
                                    }))
                                  : _createCommentVNode$3("", true)
                              ]),
                              _: 2
                            }, 1024),
                            _createVNode$3(_component_VListItemSubtitle, { class: "mon-test-msg" }, {
                              default: _withCtx$3(() => [
                                _createTextVNode$3(_toDisplayString$3(_unref$2(decisionLabel)(trace.decision)) + " · " + _toDisplayString$3(trace.reason), 1)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _: 2
                        }, 1024))
                      }), 128))
                    ]),
                    _: 1
                  })
                ]))
              : _createCommentVNode$3("", true)
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$3(_component_VCard, {
      flat: "",
      class: "mon-card"
    }, {
      default: _withCtx$3(() => [
        _createVNode$3(_component_VCardItem, null, {
          append: _withCtx$3(() => [
            _createVNode$3(_component_VSelect, {
              modelValue: decisionFilter.value,
              "onUpdate:modelValue": [
                _cache[2] || (_cache[2] = $event => ((decisionFilter).value = $event)),
                onDecisionFilter
              ],
              items: [{ value: '', title: '全部决策' }, ...decisions.value],
              "item-title": "title",
              "item-value": "value",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              class: "mon-filter"
            }, null, 8, ["modelValue", "items"])
          ]),
          default: _withCtx$3(() => [
            _createVNode$3(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$3(() => [...(_cache[32] || (_cache[32] = [
                _createTextVNode$3("命中流水", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$3(_component_VCardText, null, {
          default: _withCtx$3(() => [
            _createElementVNode$3("div", _hoisted_36$1, [
              _createVNode$3(_component_VTextField, {
                modelValue: hitKeyword.value,
                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((hitKeyword).value = $event)),
                placeholder: "按片名 / 规则 / 说明搜索",
                "prepend-inner-icon": "mdi-magnify",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                clearable: "",
                class: "mon-hits-search"
              }, null, 8, ["modelValue"]),
              _createVNode$3(_component_VBtn, {
                size: "small",
                variant: "tonal",
                color: "error",
                "prepend-icon": "mdi-delete-outline",
                disabled: !hitsTotal.value,
                onClick: _cache[4] || (_cache[4] = $event => (askClear('filtered')))
              }, {
                default: _withCtx$3(() => [...(_cache[33] || (_cache[33] = [
                  _createTextVNode$3(" 删除筛选结果 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"]),
              _createVNode$3(_component_VBtn, {
                size: "small",
                variant: "text",
                color: "error",
                disabled: !hitsTotal.value,
                onClick: _cache[5] || (_cache[5] = $event => (askClear('all')))
              }, {
                default: _withCtx$3(() => [...(_cache[34] || (_cache[34] = [
                  _createTextVNode$3(" 清空本类流水 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"])
            ]),
            _createVNode$3(_component_VTable, {
              density: "compact",
              class: "mon-hits"
            }, {
              default: _withCtx$3(() => [
                _cache[36] || (_cache[36] = _createElementVNode$3("thead", null, [
                  _createElementVNode$3("tr", null, [
                    _createElementVNode$3("th", { class: "mon-nowrap" }, "时间"),
                    _createElementVNode$3("th", { class: "mon-nowrap" }, "规则"),
                    _createElementVNode$3("th", { class: "mon-nowrap" }, "来源"),
                    _createElementVNode$3("th", null, "媒体"),
                    _createElementVNode$3("th", { class: "mon-nowrap" }, "决策"),
                    _createElementVNode$3("th", null, "说明")
                  ])
                ], -1)),
                _createElementVNode$3("tbody", null, [
                  (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(hits.value, (item) => {
                    return (_openBlock$3(), _createElementBlock$3("tr", {
                      key: item.id
                    }, [
                      _createElementVNode$3("td", _hoisted_37$1, _toDisplayString$3(fmtTime(item.created_at)), 1),
                      _createElementVNode$3("td", _hoisted_38$1, _toDisplayString$3(item.rule_name), 1),
                      _createElementVNode$3("td", _hoisted_39, _toDisplayString$3(chatTitleMap.value[item.chat_id] || item.chat_id), 1),
                      _createElementVNode$3("td", null, [
                        (item.title)
                          ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_40, _toDisplayString$3(mediaName(item)), 1))
                          : (_openBlock$3(), _createElementBlock$3("span", _hoisted_41, "—"))
                      ]),
                      _createElementVNode$3("td", _hoisted_42, [
                        _createVNode$3(_component_VChip, {
                          size: "x-small",
                          variant: "tonal",
                          color: _unref$2(decisionColor)(item.decision),
                          label: ""
                        }, {
                          default: _withCtx$3(() => [
                            _createTextVNode$3(_toDisplayString$3(_unref$2(decisionLabel)(item.decision)), 1)
                          ]),
                          _: 2
                        }, 1032, ["color"])
                      ]),
                      _createElementVNode$3("td", _hoisted_43, _toDisplayString$3(item.detail), 1)
                    ]))
                  }), 128)),
                  (!hits.value.length)
                    ? (_openBlock$3(), _createElementBlock$3("tr", _hoisted_44, [...(_cache[35] || (_cache[35] = [
                        _createElementVNode$3("td", {
                          colspan: "6",
                          class: "mon-hits-empty"
                        }, "暂无记录", -1)
                      ]))]))
                    : _createCommentVNode$3("", true)
                ])
              ]),
              _: 1
            }),
            _createElementVNode$3("div", _hoisted_45, [
              _createVNode$3(_component_VBtn, {
                size: "small",
                variant: "text",
                disabled: hitsPage.value <= 1,
                "prepend-icon": "mdi-chevron-left",
                onClick: prevHits
              }, {
                default: _withCtx$3(() => [...(_cache[37] || (_cache[37] = [
                  _createTextVNode$3(" 上一页 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"]),
              _createElementVNode$3("span", _hoisted_46, "第 " + _toDisplayString$3(hitsPage.value) + " 页 · 共 " + _toDisplayString$3(hitsTotal.value) + " 条", 1),
              _createVNode$3(_component_VBtn, {
                size: "small",
                variant: "text",
                disabled: hitsPage.value * hitsPageSize$1 >= hitsTotal.value,
                "append-icon": "mdi-chevron-right",
                onClick: nextHits
              }, {
                default: _withCtx$3(() => [...(_cache[38] || (_cache[38] = [
                  _createTextVNode$3(" 下一页 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"])
            ])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _cache[46] || (_cache[46] = _createElementVNode$3("div", { class: "mon-hint" }, " 风控提示：TG 个人号对外操作有频率限制，插件按「聚合窗口 + 全局冷却 + FloodWait 退避」克制发送； 长时间大流量监控请适当调大「TG 凭证」页的个人号冷却秒数。 ", -1)),
    _createVNode$3(_component_VDialog, {
      modelValue: clearDialog.value,
      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((clearDialog).value = $event)),
      "max-width": "460"
    }, {
      default: _withCtx$3(() => [
        _createVNode$3(_component_VCard, null, {
          default: _withCtx$3(() => [
            _createVNode$3(_component_VCardTitle, { class: "text-subtitle-1" }, {
              default: _withCtx$3(() => [
                _createTextVNode$3(_toDisplayString$3(clearTarget.value === 'all' ? '清空监控流水' : '删除筛选结果'), 1)
              ]),
              _: 1
            }),
            _createVNode$3(_component_VCardText, { class: "text-body-2" }, {
              default: _withCtx$3(() => [
                (hasFilter.value)
                  ? (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 0 }, [
                      _cache[39] || (_cache[39] = _createTextVNode$3(" 当前有筛选条件，将只删除筛选出的 ", -1)),
                      _createElementVNode$3("strong", null, _toDisplayString$3(hitsTotal.value), 1),
                      _cache[40] || (_cache[40] = _createTextVNode$3(" 条流水 ", -1)),
                      (filterText.value)
                        ? (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 0 }, [
                            _createTextVNode$3("（筛选：" + _toDisplayString$3(filterText.value) + "）", 1)
                          ], 64))
                        : _createCommentVNode$3("", true),
                      _cache[41] || (_cache[41] = _createTextVNode$3(" ，删除后不可恢复；未筛选部分不受影响。如需清空全部，请先清除筛选条件。 ", -1))
                    ], 64))
                  : (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 1 }, [
                      _cache[42] || (_cache[42] = _createTextVNode$3(" 将删除本面板的", -1)),
                      _cache[43] || (_cache[43] = _createElementVNode$3("strong", null, "全部监控流水", -1)),
                      _createTextVNode$3("（共 " + _toDisplayString$3(hitsTotal.value) + " 条），删除后不可恢复； 通用转发的流水不受影响。 ", 1)
                    ], 64))
              ]),
              _: 1
            }),
            _createVNode$3(_component_VCardActions, null, {
              default: _withCtx$3(() => [
                _createVNode$3(_component_VSpacer),
                _createVNode$3(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[6] || (_cache[6] = $event => (clearDialog.value = false))
                }, {
                  default: _withCtx$3(() => [...(_cache[44] || (_cache[44] = [
                    _createTextVNode$3("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode$3(_component_VBtn, {
                  color: "error",
                  loading: clearing.value,
                  onClick: runClear
                }, {
                  default: _withCtx$3(() => [...(_cache[45] || (_cache[45] = [
                    _createTextVNode$3("删除", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const ConfigMonitorPane = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-1dea115f"]]);

const {resolveComponent:_resolveComponent$2,createVNode:_createVNode$2,createTextVNode:_createTextVNode$2,withCtx:_withCtx$2,toDisplayString:_toDisplayString$2,openBlock:_openBlock$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2,createElementVNode:_createElementVNode$2,Fragment:_Fragment$2,createElementBlock:_createElementBlock$2,renderList:_renderList$2,withKeys:_withKeys} = await importShared('vue');


const _hoisted_1$2 = { class: "cache-pane" };
const _hoisted_2$2 = { class: "cache-status" };
const _hoisted_3$2 = { class: "cache-status-sub" };
const _hoisted_4$2 = { key: 0 };
const _hoisted_5$1 = { key: 1 };
const _hoisted_6$1 = { key: 2 };
const _hoisted_7$1 = { class: "cache-status-sub" };
const _hoisted_8$1 = { key: 0 };
const _hoisted_9$1 = { key: 1 };
const _hoisted_10$1 = { class: "cache-grid" };
const _hoisted_11$1 = { class: "cache-chats" };
const _hoisted_12$1 = { class: "cache-range" };
const _hoisted_13$1 = {
  key: 1,
  class: "cache-dates"
};
const _hoisted_14$1 = { class: "cache-options" };
const _hoisted_15$1 = { class: "cache-grid cache-grid-cron" };
const _hoisted_16$1 = { class: "cache-actions" };
const _hoisted_17$1 = { class: "cache-actions" };
const _hoisted_18$1 = { class: "cache-nowrap cache-mono" };
const _hoisted_19$1 = { class: "cache-nowrap" };
const _hoisted_20$1 = { class: "cache-nowrap cache-dim" };
const _hoisted_21$1 = { class: "cache-nowrap cache-dim" };
const _hoisted_22$1 = { key: 0 };
const _hoisted_23$1 = { class: "cache-search" };
const _hoisted_24$1 = { class: "cache-dim cache-text" };
const _hoisted_25$1 = { class: "cache-nowrap cache-dim" };
const _hoisted_26$1 = { class: "cache-nowrap" };
const _hoisted_27$1 = {
  key: 1,
  class: "cache-dim"
};
const _hoisted_28$1 = { class: "cache-nowrap cache-dim" };
const _hoisted_29$1 = {
  key: 1,
  class: "cache-empty"
};
const _hoisted_30$1 = { class: "cache-actions" };
const _hoisted_31$1 = { class: "cache-actions" };
const _hoisted_32$1 = {
  key: 0,
  class: "cache-hint"
};
const _hoisted_33$1 = {
  key: 0,
  class: "cache-details"
};

const {computed: computed$2,onMounted: onMounted$2,onUnmounted: onUnmounted$1,ref: ref$3} = await importShared('vue');

/**
 * ⑤ 历史消息缓存面板。
 *
 * 数据流：缓存设置（频道 / 目标 / 范围 / cron）走 `/cache/settings` 专用接口，
 * 保存即归一、即时生效；但与「资源监控」一致，这些键**同时写回主表单**
 * （宿主「保存配置」是整份覆盖，表单里没有的键会被清掉）。
 * 状态 / 统计 / 检索只读，回溯同步与订阅检查是触发型接口。
 *
 * 纪律（沿用全项目约定）：
 * - 模板/脚本用到的变量全部在 script setup 声明 ref（P1 踩过未声明引用的坑）；
 * - 重入保护只留在按钮处理器，内部 fetch 函数无保护（避免 busy 期间静默丢请求）；
 * - 新增配置项必须同步进 useConfigForm.js 的 configDefaults（保存是整份覆盖）。
 */

const _sfc_main$2 = {
  __name: 'ConfigCachePane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
},
  setup(__props) {

const props = __props;

const form = computed$2(() => props.config.form);

const status = ref$3(null);
const loading = ref$3(false);
const busy = ref$3('');
const message = ref$3('');
const messageOk = ref$3(true);
const dialogs = ref$3([]);

const settings = ref$3({
  chat_ids: [],
  destination: 'smart',
  sync_mode: 'relative',
  sync_days: 30,
  start_date: '',
  end_date: '',
  batch_size: 200,
  subscribe_enabled: true,
  cron: '0 */6 * * *',
  subscribe_cron: '*/5 * * * *',
});
const destinations = ref$3([
  { value: 'smart', title: '智能（115 可用则转存，否则仅记录）' },
  { value: 'pan115', title: '115 网盘（分享转存 / 磁力 eD2k 离线）' },
  { value: 'tg_forward', title: 'TG 转发（转发原消息到目标会话）' },
  { value: 'none', title: '仅记录（不推送）' },
]);
const syncModes = ref$3([
  { value: 'all', title: '所有消息（全量）' },
  { value: 'relative', title: '最近 N 天' },
  { value: 'absolute', title: '指定日期区间' },
]);

const keyword = ref$3('');
const searchItems = ref$3([]);
const searchDone = ref$3(false);

const clearDialog = ref$3(false);
const checkResult = ref$3('');
const checkDetails = ref$3([]);

let refreshTimer = null;

function setMessage(text, ok = true) {
  message.value = text || '';
  messageOk.value = ok;
}

// ------------------------------------------------------------------ 表单同步

function syncSettingsToForm() {
  // 这些键必须留在主表单里：宿主「保存配置」整份覆盖，表单没有的字段会被清空
  form.value.cache_chat_ids = (settings.value.chat_ids || []).map(Number).filter(Boolean);
  form.value.cache_destination = settings.value.destination;
  form.value.cache_sync_mode = settings.value.sync_mode;
  form.value.cache_sync_days = Number(settings.value.sync_days) || 30;
  form.value.cache_batch_size = Number(settings.value.batch_size) || 200;
  form.value.cache_subscribe_enabled = Boolean(settings.value.subscribe_enabled);
  form.value.cache_cron = settings.value.cron;
  form.value.cache_subscribe_cron = settings.value.subscribe_cron;
}

function applySettings(data) {
  const source = data && typeof data === 'object' ? data : {};
  settings.value = {
    chat_ids: Array.isArray(source.chat_ids) ? source.chat_ids.map(Number).filter(Boolean) : [],
    destination: source.destination || 'smart',
    sync_mode: source.sync_mode || 'relative',
    sync_days: Number(source.sync_days) || 30,
    start_date: '',
    end_date: '',
    batch_size: Number(source.batch_size) || 200,
    subscribe_enabled: source.subscribe_enabled !== false,
    cron: source.cron || '0 */6 * * *',
    subscribe_cron: source.subscribe_cron || '*/5 * * * *',
  };
  if (Array.isArray(source.destinations) && source.destinations.length) destinations.value = source.destinations;
  if (Array.isArray(source.sync_modes) && source.sync_modes.length) syncModes.value = source.sync_modes;
  syncSettingsToForm();
}

// ------------------------------------------------------------------ 数据加载（无重入保护，供按钮与内部调用共用）

async function loadSettings() {
  try {
    applySettings(unwrap(await getPluginApi(props.api, props.pluginId, 'cache/settings', { timeoutMs: 15000 })));
  } catch (err) {
    setMessage(err?.message || '读取缓存设置失败', false);
  }
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'cache/status', { timeoutMs: 20000 }));
  } catch (err) {
    setMessage(err?.message || '读取缓存状态失败', false);
  }
}

async function loadDialogs() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'telegram/dialogs', { timeoutMs: 15000 }));
    dialogs.value = data?.dialogs || [];
  } catch {
    // 对话列表拉不到不影响缓存设置（可手动输 ID）
    dialogs.value = [];
  }
}

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadSettings(), loadStatus(), loadDialogs()]);
    setMessage('状态已刷新');
  } finally {
    loading.value = false;
  }
}

// ------------------------------------------------------------------ 设置保存

async function saveSettings() {
  if (busy.value) return
  busy.value = 'save';
  setMessage('正在保存缓存设置…');
  try {
    const payload = {
      enabled: Boolean(form.value.cache_enabled),
      chat_ids: (settings.value.chat_ids || []).map(Number).filter(Boolean),
      destination: settings.value.destination,
      sync_mode: settings.value.sync_mode,
      sync_days: Number(settings.value.sync_days) || 30,
      batch_size: Number(settings.value.batch_size) || 200,
      subscribe_enabled: Boolean(settings.value.subscribe_enabled),
      cron: String(settings.value.cron || '').trim() || '0 */6 * * *',
      subscribe_cron: String(settings.value.subscribe_cron || '').trim() || '*/5 * * * *',
    };
    applySettings(unwrap(await putPluginApi(
      props.api, props.pluginId, 'cache/settings', payload, { timeoutMs: 30000 },
    )));
    setMessage('缓存设置已保存（即时生效）');
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '保存缓存设置失败', false);
  } finally {
    busy.value = '';
  }
}

// ------------------------------------------------------------------ 同步与清空

async function startSync() {
  if (busy.value) return
  busy.value = 'sync';
  setMessage('正在启动历史回溯同步…');
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'cache/sync', {
      chat_ids: [],
      mode: settings.value.sync_mode,
      days: Number(settings.value.sync_days) || 30,
      start: settings.value.start_date || '',
      end: settings.value.end_date || '',
    }, { timeoutMs: 30000 }));
    setMessage(data?.message || (data?.started ? '同步已启动' : '同步未启动'), Boolean(data?.started));
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '启动同步失败', false);
  } finally {
    busy.value = '';
  }
}

async function cancelSync() {
  if (busy.value) return
  busy.value = 'cancel';
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'cache/cancel', {}, { timeoutMs: 15000 }));
    setMessage(data?.message || '已请求停止同步', Boolean(data?.stopped));
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '停止同步失败', false);
  } finally {
    busy.value = '';
  }
}

async function doClear() {
  if (busy.value) return
  busy.value = 'clear';
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'cache/clear', { chat_ids: [] }, { timeoutMs: 30000 }));
    clearDialog.value = false;
    setMessage(data?.message || '缓存已清空');
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '清空缓存失败', false);
  } finally {
    busy.value = '';
  }
}

// ------------------------------------------------------------------ 检索与订阅检查

async function doSearch() {
  if (busy.value) return
  const word = String(keyword.value || '').trim();
  if (!word) {
    setMessage('请输入要检索的片名关键词', false);
    return
  }
  busy.value = 'search';
  searchDone.value = false;
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'cache/search', { keyword: word, limit: 50 }, { timeoutMs: 20000 },
    ));
    searchItems.value = data?.items || [];
    searchDone.value = true;
    setMessage(`检索完成：命中 ${data?.total ?? searchItems.value.length} 条`);
  } catch (err) {
    searchItems.value = [];
    searchDone.value = true;
    setMessage(err?.message || '检索失败', false);
  } finally {
    busy.value = '';
  }
}

async function checkSubscriptions() {
  if (busy.value) return
  busy.value = 'check';
  checkDetails.value = [];
  setMessage('正在检查新增订阅并回搜缓存…');
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'cache/check_subscriptions', {}, { timeoutMs: 60000 },
    ));
    checkResult.value = data?.message || '';
    checkDetails.value = data?.details || [];
    setMessage(data?.message || '订阅检查完成', data?.checked !== false);
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '订阅检查失败', false);
  } finally {
    busy.value = '';
  }
}

// ------------------------------------------------------------------ 展示辅助

const dialogOptions = computed$2(() =>
  (dialogs.value || []).map(item => ({
    title: `${item.name}（${item.type}）`,
    value: Number(item.id),
  })),
);

// 下拉选项 = 对话列表 + 已保存 / 状态里的 ID（缓存里没有的 ID 仍兜底显示，老配置不变空白）
const selectItems = computed$2(() => {
  const items = dialogOptions.value.slice();
  const known = new Set(items.map(item => item.value));
  const extra = [
    ...(settings.value.chat_ids || []),
    ...((status.value?.channels || []).map(item => item.chat_id)),
  ];
  for (const raw of extra) {
    const id = Number(raw);
    if (id && !known.has(id)) {
      const name = chatNameMap.value[id];
      items.push({ title: name ? `${name}（${id}）` : String(id), value: id });
      known.add(id);
    }
  }
  return items
});

const chatNameMap = computed$2(() => {
  const map = {};
  for (const item of (status.value?.channels || [])) {
    if (item.name) map[item.chat_id] = item.name;
  }
  for (const item of (dialogs.value || [])) {
    const id = Number(item.id);
    if (id && !map[id]) map[id] = item.name;
  }
  return map
});

function chatLabel(chatId) {
  const id = Number(chatId);
  if (!id) return '—'
  const name = chatNameMap.value[id];
  return name ? `${name}（${id}）` : String(id)
}

function syncModeLabel(mode) {
  const found = syncModes.value.find(item => item.value === mode);
  return found ? found.title : (mode || '')
}

// 媒体列：片名（年份）+ SxxExx
function searchName(item) {
  const year = item.year ? ` (${item.year})` : '';
  let name = `${item.title || '(未识别)'}${year}`;
  if (item.season || item.episode) {
    const s = String(item.season ?? 1).padStart(2, '0');
    const e = String(item.episode ?? 0).padStart(2, '0');
    name += ` S${s}E${e}`;
  }
  return name
}

function fmtTime(value) {
  return String(value || '').replace('T', ' ')
}

onMounted$2(async () => {
  await refreshAll();
  // 同步在后台线程跑，状态卡保持新鲜（统计查询很轻，10 秒一次）
  refreshTimer = window.setInterval(loadStatus, 10000);
});

onUnmounted$1(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
});

return (_ctx, _cache) => {
  const _component_VSwitch = _resolveComponent$2("VSwitch");
  const _component_VCardTitle = _resolveComponent$2("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$2("VCardSubtitle");
  const _component_VCardItem = _resolveComponent$2("VCardItem");
  const _component_VCard = _resolveComponent$2("VCard");
  const _component_VAlert = _resolveComponent$2("VAlert");
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VChip = _resolveComponent$2("VChip");
  const _component_VCardText = _resolveComponent$2("VCardText");
  const _component_VSelect = _resolveComponent$2("VSelect");
  const _component_VTextField = _resolveComponent$2("VTextField");
  const _component_VTable = _resolveComponent$2("VTable");
  const _component_VSpacer = _resolveComponent$2("VSpacer");
  const _component_VCardActions = _resolveComponent$2("VCardActions");
  const _component_VDialog = _resolveComponent$2("VDialog");

  return (_openBlock$2(), _createElementBlock$2("div", _hoisted_1$2, [
    _createVNode$2(_component_VCard, {
      flat: "",
      class: "cache-card"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCardItem, null, {
          prepend: _withCtx$2(() => [
            _createVNode$2(_component_VSwitch, {
              modelValue: form.value.cache_enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.value.cache_enabled) = $event)),
              color: "primary",
              "hide-details": "",
              inset: ""
            }, null, 8, ["modelValue"])
          ]),
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$2(() => [...(_cache[15] || (_cache[15] = [
                _createTextVNode$2("启用消息缓存", -1)
              ]))]),
              _: 1
            }),
            _createVNode$2(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx$2(() => [...(_cache[16] || (_cache[16] = [
                _createTextVNode$2(" 关心会话的新消息实时入库，历史消息按时间范围回溯补齐；新增订阅自动回搜缓存并推送缺失（随「保存配置」生效）。 ", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    (message.value)
      ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
          key: 0,
          type: messageOk.value ? 'info' : 'warning',
          variant: "tonal",
          density: "comfortable",
          class: "cache-message"
        }, {
          default: _withCtx$2(() => [
            _createTextVNode$2(_toDisplayString$2(message.value), 1)
          ]),
          _: 1
        }, 8, ["type"]))
      : _createCommentVNode$2("", true),
    _createVNode$2(_component_VCard, {
      flat: "",
      class: "cache-card"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCardItem, null, {
          append: _withCtx$2(() => [
            _createVNode$2(_component_VBtn, {
              size: "small",
              variant: "tonal",
              "prepend-icon": "mdi-refresh",
              loading: loading.value,
              onClick: refreshAll
            }, {
              default: _withCtx$2(() => [...(_cache[18] || (_cache[18] = [
                _createTextVNode$2(" 刷新状态 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading"])
          ]),
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$2(() => [...(_cache[17] || (_cache[17] = [
                _createTextVNode$2("运行状态", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$2(_component_VCardText, null, {
          default: _withCtx$2(() => [
            _createElementVNode$2("div", _hoisted_2$2, [
              _createVNode$2(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: status.value?.enabled ? 'success' : 'default',
                label: ""
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(" 缓存" + _toDisplayString$2(status.value?.enabled ? '已启用' : '未启用'), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode$2(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: "info",
                label: ""
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(" 缓存频道 " + _toDisplayString$2(status.value?.chats ?? 0), 1)
                ]),
                _: 1
              }),
              _createVNode$2(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: "primary",
                label: ""
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(" 已缓存 " + _toDisplayString$2(status.value?.total ?? 0) + " 条 ", 1)
                ]),
                _: 1
              }),
              _createVNode$2(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: status.value?.sync?.running ? 'warning' : 'success',
                label: ""
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(" 同步" + _toDisplayString$2(status.value?.sync?.running ? '进行中' : '空闲'), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode$2(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: status.value?.subscribe?.enabled ? 'success' : 'default',
                label: ""
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(" 订阅回搜" + _toDisplayString$2(status.value?.subscribe?.enabled ? '已开启' : '已关闭'), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              (status.value?.sync?.running)
                ? (_openBlock$2(), _createBlock$2(_component_VChip, {
                    key: 0,
                    size: "small",
                    variant: "tonal",
                    color: "info",
                    label: ""
                  }, {
                    default: _withCtx$2(() => [
                      _createTextVNode$2(" 已扫描 " + _toDisplayString$2(status.value.sync.processed ?? 0) + " · 新增 " + _toDisplayString$2(status.value.sync.inserted ?? 0), 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$2("", true)
            ]),
            _createElementVNode$2("div", _hoisted_3$2, [
              (status.value?.sync?.running)
                ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_4$2, [
                    _createTextVNode$2(" 正在同步频道 " + _toDisplayString$2(chatLabel(status.value.sync.chat_id)) + "（" + _toDisplayString$2(syncModeLabel(status.value.sync.mode)) + "） ", 1),
                    (status.value.sync.started_at)
                      ? (_openBlock$2(), _createElementBlock$2(_Fragment$2, { key: 0 }, [
                          _createTextVNode$2(" · 开始于 " + _toDisplayString$2(fmtTime(status.value.sync.started_at)), 1)
                        ], 64))
                      : _createCommentVNode$2("", true)
                  ]))
                : (status.value?.sync?.finished_at)
                  ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_5$1, " 上次同步结束 " + _toDisplayString$2(fmtTime(status.value.sync.finished_at)) + " · 新增 " + _toDisplayString$2(status.value.sync.inserted ?? 0) + " 条 ", 1))
                  : (_openBlock$2(), _createElementBlock$2("span", _hoisted_6$1, "尚未执行过历史回溯同步"))
            ]),
            _createElementVNode$2("div", _hoisted_7$1, [
              (status.value?.subscribe?.last_check_at)
                ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_8$1, " 订阅检查 " + _toDisplayString$2(fmtTime(status.value.subscribe.last_check_at)) + " · 新增订阅 " + _toDisplayString$2(status.value.subscribe.last_check_new ?? 0) + " · 推送 " + _toDisplayString$2(status.value.subscribe.last_check_pushed ?? 0) + " 条 ", 1))
                : (_openBlock$2(), _createElementBlock$2("span", _hoisted_9$1, "订阅回搜尚未运行（首次运行只建立订阅基线）")),
              _createVNode$2(_component_VChip, {
                size: "x-small",
                variant: "tonal",
                color: status.value?.subscribe?.event_listener ? 'success' : 'warning',
                label: "",
                class: "ml-2",
                title: status.value?.subscribe?.event_listener ? '已监听宿主新增订阅事件，新增订阅秒级回搜' : '宿主事件总线不可用，仅按定时检查（默认每 5 分钟）'
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(_toDisplayString$2(status.value?.subscribe?.event_listener ? '实时回搜已启用' : '仅定时检查'), 1)
                ]),
                _: 1
              }, 8, ["color", "title"])
            ]),
            (status.value?.sync?.last_error || status.value?.subscribe?.last_error)
              ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
                  key: 0,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "cache-hint"
                }, {
                  default: _withCtx$2(() => [
                    _createTextVNode$2(_toDisplayString$2(status.value?.sync?.last_error || status.value?.subscribe?.last_error), 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode$2("", true)
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$2(_component_VCard, {
      flat: "",
      class: "cache-card"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCardItem, null, {
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$2(() => [...(_cache[19] || (_cache[19] = [
                _createTextVNode$2("缓存频道与范围", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$2(_component_VCardText, null, {
          default: _withCtx$2(() => [
            _createElementVNode$2("div", _hoisted_10$1, [
              _createElementVNode$2("div", _hoisted_11$1, [
                _createVNode$2(_component_VSelect, {
                  modelValue: settings.value.chat_ids,
                  "onUpdate:modelValue": [
                    _cache[1] || (_cache[1] = $event => ((settings.value.chat_ids) = $event)),
                    syncSettingsToForm
                  ],
                  items: selectItems.value,
                  "item-title": "title",
                  "item-value": "value",
                  label: "缓存频道 / 群组",
                  multiple: "",
                  chips: "",
                  "closable-chips": "",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "items"]),
                _cache[20] || (_cache[20] = _createElementVNode$2("div", { class: "cache-hint" }, " 与「资源监控」的监听频道互相独立：只缓存不监控、或两者重叠都可以。 看不到想要的会话，先到「TG 凭证」页刷新对话列表再点「刷新状态」。 ", -1))
              ]),
              _createElementVNode$2("div", _hoisted_12$1, [
                _createVNode$2(_component_VSelect, {
                  modelValue: settings.value.sync_mode,
                  "onUpdate:modelValue": [
                    _cache[2] || (_cache[2] = $event => ((settings.value.sync_mode) = $event)),
                    syncSettingsToForm
                  ],
                  items: syncModes.value,
                  "item-title": "title",
                  "item-value": "value",
                  label: "历史回溯范围",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "items"]),
                (settings.value.sync_mode === 'relative')
                  ? (_openBlock$2(), _createBlock$2(_component_VTextField, {
                      key: 0,
                      modelValue: settings.value.sync_days,
                      "onUpdate:modelValue": [
                        _cache[3] || (_cache[3] = $event => ((settings.value.sync_days) = $event)),
                        syncSettingsToForm
                      ],
                      label: "回溯天数",
                      type: "number",
                      suffix: "天",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]))
                  : _createCommentVNode$2("", true),
                (settings.value.sync_mode === 'absolute')
                  ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_13$1, [
                      _createVNode$2(_component_VTextField, {
                        modelValue: settings.value.start_date,
                        "onUpdate:modelValue": [
                          _cache[4] || (_cache[4] = $event => ((settings.value.start_date) = $event)),
                          syncSettingsToForm
                        ],
                        label: "起始日期",
                        placeholder: "2026-01-01",
                        density: "compact",
                        variant: "outlined",
                        "hide-details": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode$2(_component_VTextField, {
                        modelValue: settings.value.end_date,
                        "onUpdate:modelValue": [
                          _cache[5] || (_cache[5] = $event => ((settings.value.end_date) = $event)),
                          syncSettingsToForm
                        ],
                        label: "结束日期",
                        placeholder: "2026-01-31",
                        density: "compact",
                        variant: "outlined",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]))
                  : _createCommentVNode$2("", true),
                _cache[21] || (_cache[21] = _createElementVNode$2("div", { class: "cache-hint" }, " 首次建议「最近 30 天」：全量拉几万条容易触发 TG 限流（FloodWait），插件会退避重试但耗时会拉长。 同步按消息位点推进，重复执行只补新消息。 ", -1))
              ]),
              _createElementVNode$2("div", _hoisted_14$1, [
                _createVNode$2(_component_VSelect, {
                  modelValue: settings.value.destination,
                  "onUpdate:modelValue": [
                    _cache[6] || (_cache[6] = $event => ((settings.value.destination) = $event)),
                    syncSettingsToForm
                  ],
                  items: destinations.value,
                  "item-title": "title",
                  "item-value": "value",
                  label: "命中推送目标",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "items"]),
                _createVNode$2(_component_VTextField, {
                  modelValue: settings.value.batch_size,
                  "onUpdate:modelValue": [
                    _cache[7] || (_cache[7] = $event => ((settings.value.batch_size) = $event)),
                    syncSettingsToForm
                  ],
                  label: "每批拉取条数",
                  type: "number",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode$2(_component_VSwitch, {
                  modelValue: settings.value.subscribe_enabled,
                  "onUpdate:modelValue": [
                    _cache[8] || (_cache[8] = $event => ((settings.value.subscribe_enabled) = $event)),
                    syncSettingsToForm
                  ],
                  color: "primary",
                  "hide-details": "",
                  inset: ""
                }, {
                  label: _withCtx$2(() => [...(_cache[22] || (_cache[22] = [
                    _createElementVNode$2("span", { class: "cache-switch-label" }, "订阅新增时回搜缓存", -1)
                  ]))]),
                  _: 1
                }, 8, ["modelValue"]),
                _cache[23] || (_cache[23] = _createElementVNode$2("div", { class: "cache-hint" }, " 推送目标决定「回搜命中」时怎么送：智能（115 可用则转存，否则仅记录）/ 115 / TG 转发 / 仅记录。 ", -1))
              ])
            ]),
            _createElementVNode$2("div", _hoisted_15$1, [
              _createVNode$2(_component_VTextField, {
                modelValue: settings.value.cron,
                "onUpdate:modelValue": [
                  _cache[9] || (_cache[9] = $event => ((settings.value.cron) = $event)),
                  syncSettingsToForm
                ],
                label: "增量同步定时（cron）",
                density: "compact",
                variant: "outlined",
                "hide-details": ""
              }, null, 8, ["modelValue"]),
              _createVNode$2(_component_VTextField, {
                modelValue: settings.value.subscribe_cron,
                "onUpdate:modelValue": [
                  _cache[10] || (_cache[10] = $event => ((settings.value.subscribe_cron) = $event)),
                  syncSettingsToForm
                ],
                label: "订阅兜底检查定时（cron）",
                density: "compact",
                variant: "outlined",
                "hide-details": ""
              }, null, 8, ["modelValue"]),
              _cache[24] || (_cache[24] = _createElementVNode$2("div", { class: "cache-hint" }, " 增量定时的作用不是「拉新消息」（实时通道已在写），而是补齐插件离线/掉线/限流期间漏掉的窗口， 并刷新同步位点。改完需重新启用插件生效。 ", -1))
            ]),
            _createElementVNode$2("div", _hoisted_16$1, [
              _createVNode$2(_component_VBtn, {
                color: "primary",
                variant: "flat",
                "prepend-icon": "mdi-content-save-outline",
                loading: busy.value === 'save',
                onClick: saveSettings
              }, {
                default: _withCtx$2(() => [...(_cache[25] || (_cache[25] = [
                  _createTextVNode$2(" 保存缓存设置（即时生效） ", -1)
                ]))]),
                _: 1
              }, 8, ["loading"]),
              _cache[26] || (_cache[26] = _createElementVNode$2("span", { class: "cache-hint" }, "设置直接写入插件配置；开关与其它模块设置随底部「保存配置」持久化。", -1))
            ])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$2(_component_VCard, {
      flat: "",
      class: "cache-card"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCardItem, null, {
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$2(() => [...(_cache[27] || (_cache[27] = [
                _createTextVNode$2("缓存管理", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$2(_component_VCardText, null, {
          default: _withCtx$2(() => [
            _createElementVNode$2("div", _hoisted_17$1, [
              _createVNode$2(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-database-arrow-down-outline",
                loading: busy.value === 'sync',
                disabled: !status.value?.enabled || Boolean(status.value?.sync?.running),
                onClick: startSync
              }, {
                default: _withCtx$2(() => [...(_cache[28] || (_cache[28] = [
                  _createTextVNode$2(" 开始回溯同步 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading", "disabled"]),
              _createVNode$2(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-stop-circle-outline",
                disabled: !status.value?.sync?.running,
                onClick: cancelSync
              }, {
                default: _withCtx$2(() => [...(_cache[29] || (_cache[29] = [
                  _createTextVNode$2(" 停止同步 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"]),
              _createVNode$2(_component_VBtn, {
                variant: "tonal",
                color: "error",
                "prepend-icon": "mdi-database-remove-outline",
                disabled: !status.value?.enabled || !(status.value?.chats > 0),
                onClick: _cache[11] || (_cache[11] = $event => (clearDialog.value = true))
              }, {
                default: _withCtx$2(() => [...(_cache[30] || (_cache[30] = [
                  _createTextVNode$2(" 清空缓存 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"])
            ]),
            _cache[33] || (_cache[33] = _createElementVNode$2("div", { class: "cache-hint" }, " 回溯同步在后台线程执行，界面可随时刷新查看进度；清空只删缓存与同步位点，下次回溯会重新拉取。 ", -1)),
            _createVNode$2(_component_VTable, {
              density: "compact",
              class: "cache-table"
            }, {
              default: _withCtx$2(() => [
                _cache[32] || (_cache[32] = _createElementVNode$2("thead", null, [
                  _createElementVNode$2("tr", null, [
                    _createElementVNode$2("th", null, "频道"),
                    _createElementVNode$2("th", { class: "cache-nowrap" }, "ID"),
                    _createElementVNode$2("th", { class: "cache-nowrap" }, "缓存条数"),
                    _createElementVNode$2("th", { class: "cache-nowrap" }, "最新消息"),
                    _createElementVNode$2("th", { class: "cache-nowrap" }, "同步位点")
                  ])
                ], -1)),
                _createElementVNode$2("tbody", null, [
                  (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(status.value?.channels || [], (item) => {
                    return (_openBlock$2(), _createElementBlock$2("tr", {
                      key: `ch-${item.chat_id}`
                    }, [
                      _createElementVNode$2("td", null, _toDisplayString$2(item.name || '(未知频道)'), 1),
                      _createElementVNode$2("td", _hoisted_18$1, _toDisplayString$2(item.chat_id), 1),
                      _createElementVNode$2("td", _hoisted_19$1, _toDisplayString$2(item.count), 1),
                      _createElementVNode$2("td", _hoisted_20$1, _toDisplayString$2(fmtTime(item.latest_date) || '—'), 1),
                      _createElementVNode$2("td", _hoisted_21$1, _toDisplayString$2(item.cursor || '—'), 1)
                    ]))
                  }), 128)),
                  (!(status.value?.channels || []).length)
                    ? (_openBlock$2(), _createElementBlock$2("tr", _hoisted_22$1, [...(_cache[31] || (_cache[31] = [
                        _createElementVNode$2("td", {
                          colspan: "5",
                          class: "cache-empty"
                        }, "还没有缓存频道，先在上方选择频道并保存设置", -1)
                      ]))]))
                    : _createCommentVNode$2("", true)
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$2(_component_VCard, {
      flat: "",
      class: "cache-card"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCardItem, null, {
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$2(() => [...(_cache[34] || (_cache[34] = [
                _createTextVNode$2("缓存检索", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$2(_component_VCardText, null, {
          default: _withCtx$2(() => [
            _createElementVNode$2("div", _hoisted_23$1, [
              _createVNode$2(_component_VTextField, {
                modelValue: keyword.value,
                "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((keyword).value = $event)),
                label: "片名关键词",
                placeholder: "青与碧",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                class: "cache-search-input",
                onKeyup: _withKeys(doSearch, ["enter"])
              }, null, 8, ["modelValue"]),
              _createVNode$2(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-magnify",
                loading: busy.value === 'search',
                onClick: doSearch
              }, {
                default: _withCtx$2(() => [...(_cache[35] || (_cache[35] = [
                  _createTextVNode$2(" 检索 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading"])
            ]),
            _cache[37] || (_cache[37] = _createElementVNode$2("div", { class: "cache-hint" }, " 检索本地缓存（不访问 TG）：先按归一标题匹配，再退回全文模糊；用于验证「订阅回搜能不能命中」。 ", -1)),
            (searchItems.value.length)
              ? (_openBlock$2(), _createBlock$2(_component_VTable, {
                  key: 0,
                  density: "compact",
                  class: "cache-table"
                }, {
                  default: _withCtx$2(() => [
                    _cache[36] || (_cache[36] = _createElementVNode$2("thead", null, [
                      _createElementVNode$2("tr", null, [
                        _createElementVNode$2("th", null, "媒体"),
                        _createElementVNode$2("th", { class: "cache-nowrap" }, "来源"),
                        _createElementVNode$2("th", { class: "cache-nowrap" }, "链接"),
                        _createElementVNode$2("th", { class: "cache-nowrap" }, "消息时间")
                      ])
                    ], -1)),
                    _createElementVNode$2("tbody", null, [
                      (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(searchItems.value, (item) => {
                        return (_openBlock$2(), _createElementBlock$2("tr", {
                          key: `s-${item.chat_id}-${item.message_id}`
                        }, [
                          _createElementVNode$2("td", null, [
                            _createElementVNode$2("div", null, _toDisplayString$2(searchName(item)), 1),
                            _createElementVNode$2("div", _hoisted_24$1, _toDisplayString$2(item.text), 1)
                          ]),
                          _createElementVNode$2("td", _hoisted_25$1, _toDisplayString$2(chatLabel(item.chat_id)), 1),
                          _createElementVNode$2("td", _hoisted_26$1, [
                            ((item.links || []).length)
                              ? (_openBlock$2(), _createBlock$2(_component_VChip, {
                                  key: 0,
                                  size: "x-small",
                                  variant: "tonal",
                                  color: "success",
                                  label: ""
                                }, {
                                  default: _withCtx$2(() => [
                                    _createTextVNode$2(_toDisplayString$2(item.links.length) + " 个 ", 1)
                                  ]),
                                  _: 2
                                }, 1024))
                              : (_openBlock$2(), _createElementBlock$2("span", _hoisted_27$1, "无"))
                          ]),
                          _createElementVNode$2("td", _hoisted_28$1, _toDisplayString$2(fmtTime(item.message_date) || '—'), 1)
                        ]))
                      }), 128))
                    ])
                  ]),
                  _: 1
                }))
              : (searchDone.value)
                ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_29$1, "没有命中缓存记录（换关键词，或先执行一次历史回溯同步）"))
                : _createCommentVNode$2("", true)
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$2(_component_VCard, {
      flat: "",
      class: "cache-card"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCardItem, null, {
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$2(() => [...(_cache[38] || (_cache[38] = [
                _createTextVNode$2("订阅回搜", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$2(_component_VCardText, null, {
          default: _withCtx$2(() => [
            _cache[42] || (_cache[42] = _createElementVNode$2("div", { class: "cache-hint" }, [
              _createTextVNode$2(" 实时路径：MoviePilot 新增订阅 → 插件收到订阅事件 → 防抖后"),
              _createElementVNode$2("strong", null, "按该订阅"),
              _createTextVNode$2("回搜缓存（删除后重新添加同样回搜， 已推过的由命中流水拦掉，不会重复推送）。兜底路径：定时对比订阅快照（默认每 30 分钟， 用于插件离线期间的新增订阅——事件不会补发）。命中后逐条判缺失（"),
              _createElementVNode$2("strong", null, "以媒体库逐集比对为准"),
              _createTextVNode$2("， 未订阅的按门禁跳过；媒体库不可用时才退回订阅缺集数）→ 过滤无链接 / 已推送 → 入推送队列（同一目标合并下发的链接数不超过 20 条）→ 通知结果（含跳过原因与媒体库未收录原因，一条没推也会说明原因）。 首次运行只建立基线。 "),
              _createElementVNode$2("br"),
              _createTextVNode$2(" 媒体库查询按"),
              _createElementVNode$2("strong", null, "片名+年份 → 仅片名 → 库内条目名索引"),
              _createTextVNode$2("逐层放宽： 宿主按「片名 + 年份」精确匹配，资源名里的年份/名称与媒体库刮削结果不一致时会被判成「库里没有」， 逐层放宽容忍这类偏差（放宽命中会复核库内年份，同名不同年的翻拍剧不会被误判「已有」）。 ")
            ], -1)),
            _createElementVNode$2("div", _hoisted_30$1, [
              _cache[39] || (_cache[39] = _createElementVNode$2("span", { class: "cache-hint" }, "缺失判断：", -1)),
              _createVNode$2(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: status.value?.matcher?.mediaserver_available ? 'success' : 'default',
                label: ""
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(" 媒体服务器" + _toDisplayString$2(status.value?.matcher?.mediaserver ? `（${status.value.matcher.mediaserver}）` : '未配置'), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode$2(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: status.value?.matcher?.queries_available ? 'info' : 'default',
                label: ""
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(" 订阅 " + _toDisplayString$2(status.value?.matcher?.subscriptions ?? 0), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _cache[40] || (_cache[40] = _createElementVNode$2("span", { class: "cache-hint" }, "徽章随状态每 10 秒自动刷新", -1))
            ]),
            _createElementVNode$2("div", _hoisted_31$1, [
              _createVNode$2(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-cloud-search-outline",
                loading: busy.value === 'check',
                disabled: !status.value?.enabled || !status.value?.subscribe?.enabled,
                onClick: checkSubscriptions
              }, {
                default: _withCtx$2(() => [...(_cache[41] || (_cache[41] = [
                  _createTextVNode$2(" 立即检查新增订阅 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading", "disabled"]),
              (checkResult.value)
                ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_32$1, _toDisplayString$2(checkResult.value), 1))
                : _createCommentVNode$2("", true)
            ]),
            _cache[43] || (_cache[43] = _createElementVNode$2("div", { class: "cache-hint" }, " 「立即检查」= 手动跑一次快照对比，用于升级后补跑、排查漏推送； 日常新增订阅走上面的实时事件路径，不需要手动点。 ", -1)),
            (checkDetails.value.length)
              ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_33$1, [
                  (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(checkDetails.value, (item, index) => {
                    return (_openBlock$2(), _createElementBlock$2("div", {
                      key: index,
                      class: "cache-detail"
                    }, [
                      _createTextVNode$2(_toDisplayString$2(item.name) + "：候选 " + _toDisplayString$2(item.candidates ?? 0) + " 条 · 推送 " + _toDisplayString$2(item.pushed ?? 0) + " 条 ", 1),
                      (item.skipped)
                        ? (_openBlock$2(), _createElementBlock$2(_Fragment$2, { key: 0 }, [
                            _createTextVNode$2(" · 跳过 " + _toDisplayString$2(item.skipped) + " 条", 1)
                          ], 64))
                        : _createCommentVNode$2("", true),
                      (item.error)
                        ? (_openBlock$2(), _createElementBlock$2(_Fragment$2, { key: 1 }, [
                            _createTextVNode$2(" · 失败：" + _toDisplayString$2(item.error), 1)
                          ], 64))
                        : _createCommentVNode$2("", true)
                    ]))
                  }), 128))
                ]))
              : _createCommentVNode$2("", true)
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _cache[47] || (_cache[47] = _createElementVNode$2("div", { class: "cache-hint" }, " 存储占用：缓存的是净化后的消息全文与识别字段（片名 / 年份 / 季集 / 链接），单条约 1~2 KB； 单频道万级消息约几十 MB，由 MoviePilot 的插件数据库承载，不会影响宿主业务数据。 ", -1)),
    _createVNode$2(_component_VDialog, {
      modelValue: clearDialog.value,
      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((clearDialog).value = $event)),
      "max-width": "420"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCard, null, {
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-subtitle-1" }, {
              default: _withCtx$2(() => [...(_cache[44] || (_cache[44] = [
                _createTextVNode$2("确认清空缓存？", -1)
              ]))]),
              _: 1
            }),
            _createVNode$2(_component_VCardText, { class: "cache-dialog-text" }, {
              default: _withCtx$2(() => [
                _createTextVNode$2(" 将删除全部缓存频道（" + _toDisplayString$2(status.value?.chats ?? 0) + " 个）已归档的消息与同步位点，共 " + _toDisplayString$2(status.value?.total ?? 0) + " 条。 此操作不可撤销，下次回溯会重新从 TG 拉取。 ", 1)
              ]),
              _: 1
            }),
            _createVNode$2(_component_VCardActions, null, {
              default: _withCtx$2(() => [
                _createVNode$2(_component_VSpacer),
                _createVNode$2(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[13] || (_cache[13] = $event => (clearDialog.value = false))
                }, {
                  default: _withCtx$2(() => [...(_cache[45] || (_cache[45] = [
                    _createTextVNode$2("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode$2(_component_VBtn, {
                  color: "error",
                  variant: "flat",
                  loading: busy.value === 'clear',
                  onClick: doClear
                }, {
                  default: _withCtx$2(() => [...(_cache[46] || (_cache[46] = [
                    _createTextVNode$2("确认清空", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const ConfigCachePane = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-ddbe6c73"]]);

const {resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,createTextVNode:_createTextVNode$1,withCtx:_withCtx$1,toDisplayString:_toDisplayString$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,createElementVNode:_createElementVNode$1,createElementBlock:_createElementBlock$1,renderList:_renderList$1,Fragment:_Fragment$1,unref:_unref$1} = await importShared('vue');


const _hoisted_1$1 = { class: "fwd-pane" };
const _hoisted_2$1 = { class: "fwd-status" };
const _hoisted_3$1 = { class: "fwd-actions" };
const _hoisted_4$1 = {
  key: 0,
  class: "fwd-empty"
};
const _hoisted_5 = { class: "fwd-rule-head" };
const _hoisted_6 = {
  class: "fwd-rule-switch",
  title: "规则总开关：关闭后这条转发规则不生效（不转发、也不会有通知）；改动随底部「保存配置」生效。"
};
const _hoisted_7 = { class: "fwd-rule-grid" };
const _hoisted_8 = { class: "fwd-chats" };
const _hoisted_9 = { class: "fwd-target" };
const _hoisted_10 = { class: "fwd-logic" };
const _hoisted_11 = { class: "fwd-logic-grid fwd-logic-grid-one" };
const _hoisted_12 = {
  key: 1,
  class: "fwd-hint"
};
const _hoisted_13 = { class: "fwd-logic" };
const _hoisted_14 = { class: "fwd-logic-grid" };
const _hoisted_15 = { class: "fwd-logic" };
const _hoisted_16 = { class: "fwd-logic-grid" };
const _hoisted_17 = {
  key: 1,
  class: "fwd-hint"
};
const _hoisted_18 = {
  key: 1,
  class: "fwd-actions"
};
const _hoisted_19 = { class: "fwd-actions" };
const _hoisted_20 = {
  key: 0,
  class: "fwd-test-result"
};
const _hoisted_21 = { class: "fwd-test-line" };
const _hoisted_22 = { key: 0 };
const _hoisted_23 = { key: 0 };
const _hoisted_24 = { key: 1 };
const _hoisted_25 = { key: 2 };
const _hoisted_26 = {
  key: 1,
  class: "fwd-test-none"
};
const _hoisted_27 = {
  key: 0,
  class: "fwd-test-line"
};
const _hoisted_28 = { class: "fwd-hits-tools" };
const _hoisted_29 = { class: "fwd-hits-time" };
const _hoisted_30 = { class: "fwd-nowrap" };
const _hoisted_31 = { class: "fwd-hits-source" };
const _hoisted_32 = { key: 0 };
const _hoisted_33 = {
  key: 1,
  class: "fwd-hits-none"
};
const _hoisted_34 = { class: "fwd-nowrap" };
const _hoisted_35 = { class: "fwd-hits-detail" };
const _hoisted_36 = { key: 0 };
const _hoisted_37 = { class: "fwd-pager" };
const _hoisted_38 = { class: "fwd-pager-info" };

const {computed: computed$1,onMounted: onMounted$1,onUnmounted,ref: ref$2,watch} = await importShared('vue');

/**
 * ⑥ TG 通用转发面板。
 *
 * 规则存放在插件配置 `forward_rules`（随主表单保存），读写走 `/forward/rules`
 * 专用接口——保存即校验（缺目标会话直接 400）+ 归一（补 f 前缀规则 ID）+ 即时生效。
 * 转发流水与运行态只读。
 *
 * 纪律（沿用全项目约定）：
 * - 模板/脚本用到的变量全部在 script setup 声明 ref；
 * - 重入保护只留在按钮处理器，内部 fetch 函数无保护；
 * - 新增配置项必须同步进 useConfigForm.js 的 configDefaults（保存是整份覆盖）。
 */
const hitsPageSize = 20;

const _sfc_main$1 = {
  __name: 'ConfigForwardPane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
},
  setup(__props) {

const props = __props;

const form = computed$1(() => props.config.form);

const status = ref$2(null);
// 会话 ID → 标题的映射来自监控状态（转发与监控共用同一条流水线的会话反查结果）
const watchedDetail = ref$2([]);
const loading = ref$2(false);
const busy = ref$2('');
const message = ref$2('');
const messageOk = ref$2(true);

const decisions = ref$2([
  { value: 'hit', title: '已转发' },
  { value: 'skipped_keyword', title: '关键词未命中' },
  { value: 'skipped_extension', title: '扩展名未命中' },
]);

const rules = ref$2([]);
const dialogs = ref$2([]);
// 转换规则用多行文本编辑（提交时拆行）；键与规则 id 对应
const transformText = ref$2({});

const testText = ref$2('');
const testResult = ref$2(null);

const hits = ref$2([]);
const hitsTotal = ref$2(0);
const hitsPage = ref$2(1);
const decisionFilter = ref$2('');
// 关键词用可写 computed 包一层：Vuetify 的 clearable 清除按钮会把模型置为 null，
// 直接 ref('') 收 null 会让各处 .trim() 抛错（1.6.6 真机反馈：清空关键词后列表不刷新），
// 这里在入口统一归一成字符串，模板与脚本就都不用到处防 null。
const hitKeywordRaw = ref$2('');
const hitKeyword = computed$1({
  get: () => String(hitKeywordRaw.value ?? ''),
  set: (value) => { hitKeywordRaw.value = value == null ? '' : String(value); },
});
const clearDialog = ref$2(false);
const clearTarget = ref$2('filtered');
const clearing = ref$2(false);

let refreshTimer = null;
let keywordTimer = null;

function setMessage(text, ok = true) {
  message.value = text || '';
  messageOk.value = ok;
}

function newRuleId() {
  return 'f' + Math.random().toString(16).slice(2, 10)
}

function blankRule() {
  return {
    id: newRuleId(),
    name: '',
    source_ids: [],
    target_id: '',
    match_custom_keywords: false,
    custom_keywords: [],
    pin_links_enabled: false,
    pin_link_keywords: [],
    match_file_extensions: false,
    file_extensions_to_match: [],
    enable_transform: false,
    transform_rules: [],
    enabled: true,
  }
}

// ------------------------------------------------------------------ 数据加载（无重入保护）

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'forward/status', { timeoutMs: 15000 }));
  } catch (err) {
    setMessage(err?.message || '读取转发状态失败', false);
  }
  // 会话标题映射：转发与监控共用同一条流水线的会话反查结果，取不到就显示 ID
  try {
    const monitor = unwrap(await getPluginApi(props.api, props.pluginId, 'monitor/status', { timeoutMs: 15000 }));
    watchedDetail.value = monitor?.pipeline?.watched_detail || [];
  } catch {
    watchedDetail.value = [];
  }
}

async function loadRules() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'forward/rules', { timeoutMs: 15000 }));
    if (data?.decisions?.length) decisions.value = data.decisions;
    const list = Array.isArray(data?.rules) ? data.rules : [];
    rules.value = list.map(rule => ({
      id: rule.id || newRuleId(),
      name: rule.name || '',
      source_ids: Array.isArray(rule.source_ids) ? rule.source_ids.map(Number) : [],
      target_id: rule.target_id ? String(rule.target_id) : '',
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: Array.isArray(rule.custom_keywords) ? rule.custom_keywords : [],
      pin_links_enabled: Boolean(rule.pin_links_enabled),
      pin_link_keywords: Array.isArray(rule.pin_link_keywords) ? rule.pin_link_keywords : [],
      match_file_extensions: Boolean(rule.match_file_extensions),
      file_extensions_to_match: Array.isArray(rule.file_extensions_to_match) ? rule.file_extensions_to_match : [],
      enable_transform: Boolean(rule.enable_transform),
      transform_rules: Array.isArray(rule.transform_rules) ? rule.transform_rules : [],
      enabled: rule.enabled !== false,
    }));
    syncTransformFromRules();
    syncRulesToForm();
  } catch (err) {
    setMessage(err?.message || '读取转发规则失败', false);
  }
}

async function loadDialogs() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'telegram/dialogs', { timeoutMs: 15000 }));
    dialogs.value = data?.dialogs || [];
  } catch {
    dialogs.value = [];
  }
}

async function loadHits() {
  try {
    const params = new URLSearchParams();
    params.set('page', String(hitsPage.value));
    params.set('page_size', String(hitsPageSize));
    if (decisionFilter.value) params.set('decision', decisionFilter.value);
    if (hitKeyword.value.trim()) params.set('keyword', hitKeyword.value.trim());
    const data = unwrap(await getPluginApi(
      props.api, props.pluginId, `forward/hits?${params.toString()}`, { timeoutMs: 15000 },
    ));
    hits.value = data?.items || [];
    hitsTotal.value = data?.total || 0;
  } catch (err) {
    setMessage(err?.message || '读取转发流水失败', false);
  }
}

// 关键词输入防抖 300ms：边打字边查会把后端打满
watch(hitKeyword, () => {
  clearTimeout(keywordTimer);
  keywordTimer = setTimeout(() => {
    hitsPage.value = 1;
    loadHits();
  }, 300);
});

// 当前是否有筛选条件（删除对话框据此说明"删多少"，与后端删除口径严格一致）
const hasFilter = computed$1(() => Boolean(decisionFilter.value || hitKeyword.value.trim()));
const filterText = computed$1(() => [
  decisionFilter.value ? `决策=${decisionLabel(decisionFilter.value)}` : '',
  hitKeyword.value.trim() ? `关键词=${hitKeyword.value.trim()}` : '',
].filter(Boolean).join(' / '));

function askClear(target) {
  if (!hitsTotal.value) {
    setMessage(target === 'all' ? '当前视图没有可清空的流水' : '当前筛选没有可删除的流水');
    return
  }
  clearTarget.value = target;
  clearDialog.value = true;
}

async function runClear() {
  if (clearing.value) return
  clearing.value = true;
  try {
    // 无论点哪个删除按钮，都只删「当前视图」：带上决策与关键词筛选，
    // 没有筛选才是清空本类全部（后端按 kind 隔离，不会碰到监控流水）。
    // 1.6.6 真机反馈：原来「清空本类流水」忽略筛选直接删整个 kind，对话框却
    // 显示筛选后的条数——用户确认「共 3 条」结果丢了全部流水。
    const payload = { decision: decisionFilter.value || '', keyword: hitKeyword.value.trim() };
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'forward/hits/clear', payload, { timeoutMs: 30000 },
    ));
    setMessage(data?.message || '已清理流水');
    clearDialog.value = false;
    hitsPage.value = 1;
    await Promise.all([loadHits(), loadStatus()]);
  } catch (err) {
    setMessage(err?.message || '清理流水失败', false);
  } finally {
    clearing.value = false;
  }
}

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadStatus(), loadRules(), loadHits(), loadDialogs()]);
    setMessage('状态已刷新');
  } finally {
    loading.value = false;
  }
}

// ------------------------------------------------------------------ 规则编辑

function syncRulesToForm() {
  // 规则必须留在主表单里：宿主「保存配置」是整份覆盖，表单没有的字段会被清空
  form.value.forward_rules = rules.value;
}

function syncTransformFromRules() {
  const next = {};
  for (const rule of rules.value) {
    next[rule.id] = (rule.transform_rules || []).join('\n');
  }
  transformText.value = next;
}

function syncTransform(rule, index) {
  const key = rule.id || index;
  const lines = String(transformText.value[key] || '')
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean);
  rule.transform_rules = lines;
  syncRulesToForm();
}

function addRule() {
  const rule = blankRule();
  rules.value.push(rule);
  transformText.value[rule.id] = '';
  syncRulesToForm();
}

function removeRule(index) {
  const rule = rules.value[index];
  if (rule) delete transformText.value[rule.id];
  rules.value.splice(index, 1);
  syncRulesToForm();
}

function isNumericId(value) {
  return /^-?\d+$/.test(String(value ?? '').trim())
}

async function saveRules() {
  if (busy.value) return
  const missing = rules.value.find(rule => !isNumericId(rule.target_id));
  if (missing) {
    setMessage(`规则「${missing.name || '未命名'}」还没选择转发目标`, false);
    return
  }
  busy.value = 'save';
  setMessage('正在保存规则…');
  try {
    const payload = rules.value.map(rule => ({
      id: rule.id,
      name: String(rule.name || '').trim() || '未命名规则',
      source_ids: rule.source_ids,
      target_id: Number(rule.target_id),
      match_custom_keywords: Boolean(rule.match_custom_keywords),
      custom_keywords: (rule.custom_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      pin_links_enabled: Boolean(rule.pin_links_enabled),
      pin_link_keywords: (rule.pin_link_keywords || []).map(kw => String(kw).trim()).filter(Boolean),
      match_file_extensions: Boolean(rule.match_file_extensions),
      file_extensions_to_match: (rule.file_extensions_to_match || []).map(ext => String(ext).trim().replace(/^\./, '')).filter(Boolean),
      enable_transform: Boolean(rule.enable_transform),
      transform_rules: (rule.transform_rules || []).map(line => String(line).trim()).filter(Boolean),
      // 转存 / 转发等既有规则行保留启用开关：关掉即暂停该规则（不生效、无通知）
      enabled: rule.enabled !== false,
    }));
    const data = unwrap(await putPluginApi(props.api, props.pluginId, 'forward/rules', { rules: payload }, { timeoutMs: 30000 }));
    if (Array.isArray(data?.rules)) {
      rules.value = data.rules.map(rule => ({
        ...rule,
        id: rule.id || newRuleId(),
        source_ids: Array.isArray(rule.source_ids) ? rule.source_ids.map(Number) : [],
        target_id: rule.target_id ? String(rule.target_id) : '',
        custom_keywords: rule.custom_keywords || [],
        pin_link_keywords: rule.pin_link_keywords || [],
        file_extensions_to_match: rule.file_extensions_to_match || [],
        transform_rules: rule.transform_rules || [],
      }));
      syncTransformFromRules();
      syncRulesToForm();
    }
    setMessage(`已保存 ${payload.length} 条转发规则，转发已进入运行态`);
    await loadStatus();
  } catch (err) {
    setMessage(err?.message || '保存规则失败', false);
  } finally {
    busy.value = '';
  }
}

// ------------------------------------------------------------------ 规则测试

async function runTest() {
  if (busy.value) return
  busy.value = 'test';
  setMessage('正在测试…');
  testResult.value = null;
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'forward/test', { text: testText.value }, { timeoutMs: 30000 },
    ));
    testResult.value = data;
    setMessage('测试完成（未转发、未入队）');
  } catch (err) {
    setMessage(err?.message || '测试失败', false);
  } finally {
    busy.value = '';
  }
}

// ------------------------------------------------------------------ 流水分页

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

// ------------------------------------------------------------------ 展示辅助

const dialogOptions = computed$1(() =>
  (dialogs.value || []).map(item => ({
    title: `${item.name}（${item.type}）`,
    value: Number(item.id),
  })),
);

// 下拉选项 = 对话列表 + 已保存但不在缓存里的 ID（老规则/缓存过期时保证 chips 仍能显示）
const selectItems = computed$1(() => {
  const items = dialogOptions.value.slice();
  const known = new Set(items.map(item => item.value));
  for (const rule of rules.value) {
    for (const raw of rule.source_ids || []) {
      const id = Number(raw);
      if (id && !known.has(id)) {
        items.push({ title: String(id), value: id });
        known.add(id);
      }
    }
  }
  return items
});

// 转发目标下拉：同一份对话缓存 + 已保存的目标值兜底
const targetItems = computed$1(() => {
  const items = dialogOptions.value.slice();
  const known = new Set(items.map(item => item.value));
  for (const rule of rules.value) {
    const id = Number(rule.target_id);
    if (id && !known.has(id)) {
      items.push({ title: String(id), value: id });
      known.add(id);
    }
  }
  return items
});

// 来源会话 ID → 标题（来自监控状态卡的会话反查结果，取不到就显示 ID）
const chatTitleMap = computed$1(() => {
  const map = {};
  for (const w of (watchedDetail.value || [])) {
    if (w.resolved && w.title) map[w.chat_id] = w.title;
  }
  return map
});

// 媒体列完整名：片名（年份）+ 电视剧 SxxExx
function mediaName(item) {
  if (!item.title) return ''
  const year = item.year ? ` (${item.year})` : '';
  let name = `${item.title}${year}`;
  if (item.season || item.episode) {
    const s = String(item.season ?? 1).padStart(2, '0');
    const e = String(item.episode ?? 0).padStart(2, '0');
    name += ` S${s}E${e}`;
  }
  return name
}

function fmtTime(value) {
  return String(value || '').replace('T', ' ')
}

onMounted$1(async () => {
  await refreshAll();
  refreshTimer = window.setInterval(loadStatus, 15000);
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
  const _component_VSwitch = _resolveComponent$1("VSwitch");
  const _component_VCardTitle = _resolveComponent$1("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$1("VCardSubtitle");
  const _component_VCardItem = _resolveComponent$1("VCardItem");
  const _component_VCard = _resolveComponent$1("VCard");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VTextField = _resolveComponent$1("VTextField");
  const _component_VSelect = _resolveComponent$1("VSelect");
  const _component_VCombobox = _resolveComponent$1("VCombobox");
  const _component_VTextarea = _resolveComponent$1("VTextarea");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VListItemTitle = _resolveComponent$1("VListItemTitle");
  const _component_VListItemSubtitle = _resolveComponent$1("VListItemSubtitle");
  const _component_VListItem = _resolveComponent$1("VListItem");
  const _component_VList = _resolveComponent$1("VList");
  const _component_VTable = _resolveComponent$1("VTable");
  const _component_VSpacer = _resolveComponent$1("VSpacer");
  const _component_VCardActions = _resolveComponent$1("VCardActions");
  const _component_VDialog = _resolveComponent$1("VDialog");

  return (_openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
    _createVNode$1(_component_VCard, {
      flat: "",
      class: "fwd-card"
    }, {
      default: _withCtx$1(() => [
        _createVNode$1(_component_VCardItem, null, {
          prepend: _withCtx$1(() => [
            _createVNode$1(_component_VSwitch, {
              modelValue: form.value.forward_enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((form.value.forward_enabled) = $event)),
              color: "primary",
              "hide-details": "",
              inset: ""
            }, null, 8, ["modelValue"])
          ]),
          default: _withCtx$1(() => [
            _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$1(() => [...(_cache[8] || (_cache[8] = [
                _createTextVNode$1("启用 TG 通用转发", -1)
              ]))]),
              _: 1
            }),
            _createVNode$1(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx$1(() => [...(_cache[9] || (_cache[9] = [
                _createTextVNode$1(" 监听来源频道的消息，按两级匹配命中后转发到目标会话——可选内容转换与置顶 （开关随「保存配置」生效）。 ", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    (message.value)
      ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
          key: 0,
          type: messageOk.value ? 'info' : 'warning',
          variant: "tonal",
          density: "comfortable",
          class: "fwd-message"
        }, {
          default: _withCtx$1(() => [
            _createTextVNode$1(_toDisplayString$1(message.value), 1)
          ]),
          _: 1
        }, 8, ["type"]))
      : _createCommentVNode$1("", true),
    _createVNode$1(_component_VCard, {
      flat: "",
      class: "fwd-card"
    }, {
      default: _withCtx$1(() => [
        _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$1(() => [...(_cache[10] || (_cache[10] = [
            _createTextVNode$1("运行状态", -1)
          ]))]),
          _: 1
        }),
        _createVNode$1(_component_VCardText, null, {
          default: _withCtx$1(() => [
            _createElementVNode$1("div", _hoisted_2$1, [
              _createVNode$1(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: status.value?.enabled ? 'success' : 'default',
                label: ""
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(" 转发" + _toDisplayString$1(status.value?.enabled ? '已启用' : '未启用'), 1)
                ]),
                _: 1
              }, 8, ["color"]),
              _createVNode$1(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: "primary",
                label: ""
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(" 规则 " + _toDisplayString$1(status.value?.rules_count ?? 0), 1)
                ]),
                _: 1
              }),
              _createVNode$1(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: "info",
                label: ""
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(" 关心会话 " + _toDisplayString$1(status.value?.watched_chats ?? 0), 1)
                ]),
                _: 1
              }),
              _createVNode$1(_component_VChip, {
                size: "small",
                variant: "tonal",
                color: "default",
                label: ""
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(" 转换条目 " + _toDisplayString$1(status.value?.transform_rules_count ?? 0), 1)
                ]),
                _: 1
              }),
              ((status.value?.gate_interval ?? 0) > 0)
                ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                    key: 0,
                    size: "small",
                    variant: "tonal",
                    color: "default",
                    label: ""
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(" 全局冷却 " + _toDisplayString$1(status.value.gate_interval) + " 秒 ", 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$1("", true),
              ((status.value?.flood_remaining ?? 0) > 0)
                ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                    key: 1,
                    size: "small",
                    variant: "tonal",
                    color: "warning",
                    label: ""
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(" FloodWait 退避中（约 " + _toDisplayString$1(status.value.flood_remaining) + " 秒） ", 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$1("", true)
            ]),
            _cache[12] || (_cache[12] = _createElementVNode$1("div", { class: "fwd-status-sub" }, [
              _createElementVNode$1("span", null, "转发只按关键词与扩展名匹配，与订阅无关；识别仅用于展示，识别不出也能转发。")
            ], -1)),
            _createElementVNode$1("div", _hoisted_3$1, [
              _createVNode$1(_component_VBtn, {
                size: "small",
                variant: "tonal",
                "prepend-icon": "mdi-refresh",
                loading: loading.value,
                onClick: refreshAll
              }, {
                default: _withCtx$1(() => [...(_cache[11] || (_cache[11] = [
                  _createTextVNode$1(" 刷新状态 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading"])
            ])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$1(_component_VCard, {
      flat: "",
      class: "fwd-card"
    }, {
      default: _withCtx$1(() => [
        _createVNode$1(_component_VCardItem, null, {
          append: _withCtx$1(() => [
            _createVNode$1(_component_VBtn, {
              size: "small",
              variant: "tonal",
              "prepend-icon": "mdi-plus",
              onClick: addRule
            }, {
              default: _withCtx$1(() => [...(_cache[14] || (_cache[14] = [
                _createTextVNode$1("添加规则", -1)
              ]))]),
              _: 1
            })
          ]),
          default: _withCtx$1(() => [
            _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$1(() => [...(_cache[13] || (_cache[13] = [
                _createTextVNode$1("转发规则", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$1(_component_VCardText, null, {
          default: _withCtx$1(() => [
            (!rules.value.length)
              ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_4$1, " 还没有规则。点「添加规则」创建第一条：选择来源频道与转发目标，保存后立即生效。 "))
              : _createCommentVNode$1("", true),
            (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(rules.value, (rule, index) => {
              return (_openBlock$1(), _createBlock$1(_component_VCard, {
                key: rule.id || index,
                flat: "",
                class: "fwd-rule"
              }, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VCardText, null, {
                    default: _withCtx$1(() => [
                      _createElementVNode$1("div", _hoisted_5, [
                        _createVNode$1(_component_VTextField, {
                          modelValue: rule.name,
                          "onUpdate:modelValue": $event => ((rule.name) = $event),
                          label: "规则名称",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          class: "fwd-rule-name"
                        }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                        _createElementVNode$1("div", _hoisted_6, [
                          _createVNode$1(_component_VSwitch, {
                            modelValue: rule.enabled,
                            "onUpdate:modelValue": $event => ((rule.enabled) = $event),
                            color: "success",
                            "hide-details": "",
                            inset: "",
                            density: "compact"
                          }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                          _cache[15] || (_cache[15] = _createElementVNode$1("span", { class: "fwd-switch-label" }, "启用规则", -1))
                        ]),
                        _createVNode$1(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          color: "error",
                          "prepend-icon": "mdi-delete-outline",
                          onClick: $event => (removeRule(index))
                        }, {
                          default: _withCtx$1(() => [...(_cache[16] || (_cache[16] = [
                            _createTextVNode$1(" 删除 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["onClick"])
                      ]),
                      _createElementVNode$1("div", _hoisted_7, [
                        _createElementVNode$1("div", _hoisted_8, [
                          _createVNode$1(_component_VSelect, {
                            modelValue: rule.source_ids,
                            "onUpdate:modelValue": $event => ((rule.source_ids) = $event),
                            items: selectItems.value,
                            "item-title": "title",
                            "item-value": "value",
                            label: "来源频道 / 群组",
                            multiple: "",
                            chips: "",
                            "closable-chips": "",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue", "items"]),
                          _cache[17] || (_cache[17] = _createElementVNode$1("div", { class: "fwd-hint" }, " 下拉项来自「TG 凭证」页的对话列表缓存；看不到想要的会话，先到「TG 凭证」页刷新对话列表再点「刷新状态」。 ", -1))
                        ]),
                        _createElementVNode$1("div", _hoisted_9, [
                          _createVNode$1(_component_VSelect, {
                            modelValue: rule.target_id,
                            "onUpdate:modelValue": $event => ((rule.target_id) = $event),
                            items: targetItems.value,
                            "item-title": "title",
                            "item-value": "value",
                            label: "转发目标频道 / 群组",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue", "items"]),
                          _cache[18] || (_cache[18] = _createElementVNode$1("div", { class: "fwd-hint" }, " 转发到该会话（受全局冷却与 FloodWait 退避约束）。目标必须是当前账号能看到的会话，否则转发会失败并重试。 ", -1))
                        ])
                      ]),
                      _createElementVNode$1("div", _hoisted_10, [
                        _cache[20] || (_cache[20] = _createElementVNode$1("div", { class: "fwd-logic-title" }, "逻辑一（关键词）", -1)),
                        _createElementVNode$1("div", _hoisted_11, [
                          _createElementVNode$1("div", null, [
                            _createVNode$1(_component_VSwitch, {
                              modelValue: rule.match_custom_keywords,
                              "onUpdate:modelValue": $event => ((rule.match_custom_keywords) = $event),
                              color: "primary",
                              "hide-details": "",
                              inset: ""
                            }, {
                              label: _withCtx$1(() => [...(_cache[19] || (_cache[19] = [
                                _createElementVNode$1("span", { class: "fwd-switch-label" }, "自定义关键词", -1)
                              ]))]),
                              _: 1
                            }, 8, ["modelValue", "onUpdate:modelValue"]),
                            (rule.match_custom_keywords)
                              ? (_openBlock$1(), _createBlock$1(_component_VCombobox, {
                                  key: 0,
                                  modelValue: rule.custom_keywords,
                                  "onUpdate:modelValue": $event => ((rule.custom_keywords) = $event),
                                  multiple: "",
                                  chips: "",
                                  "closable-chips": "",
                                  label: "关键词",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": "",
                                  class: "fwd-keywords"
                                }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                              : (_openBlock$1(), _createElementBlock$1("div", _hoisted_12, "启用后只有命中关键词的消息才转发；不启用 = 该级不设限。"))
                          ])
                        ])
                      ]),
                      _createElementVNode$1("div", _hoisted_13, [
                        _cache[24] || (_cache[24] = _createElementVNode$1("div", { class: "fwd-logic-title" }, "逻辑二（文件扩展名）", -1)),
                        _createElementVNode$1("div", _hoisted_14, [
                          _createElementVNode$1("div", null, [
                            _createVNode$1(_component_VSwitch, {
                              modelValue: rule.match_file_extensions,
                              "onUpdate:modelValue": $event => ((rule.match_file_extensions) = $event),
                              color: "primary",
                              "hide-details": "",
                              inset: ""
                            }, {
                              label: _withCtx$1(() => [...(_cache[21] || (_cache[21] = [
                                _createElementVNode$1("span", { class: "fwd-switch-label" }, "按扩展名过滤", -1)
                              ]))]),
                              _: 1
                            }, 8, ["modelValue", "onUpdate:modelValue"]),
                            _cache[22] || (_cache[22] = _createElementVNode$1("div", { class: "fwd-hint" }, "消息中出现指定扩展名（如 .mkv / [mp4]）才算命中。", -1))
                          ]),
                          _createElementVNode$1("div", null, [
                            (rule.match_file_extensions)
                              ? (_openBlock$1(), _createBlock$1(_component_VCombobox, {
                                  key: 0,
                                  modelValue: rule.file_extensions_to_match,
                                  "onUpdate:modelValue": $event => ((rule.file_extensions_to_match) = $event),
                                  multiple: "",
                                  chips: "",
                                  "closable-chips": "",
                                  label: "扩展名",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": "",
                                  class: "fwd-keywords"
                                }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                              : _createCommentVNode$1("", true)
                          ]),
                          _cache[23] || (_cache[23] = _createElementVNode$1("div", { class: "fwd-hint fwd-logic-note" }, [
                            _createTextVNode$1(" 逻辑一与逻辑二之间"),
                            _createElementVNode$1("strong", null, "恒为 AND"),
                            _createTextVNode$1("：两者都启用时必须同时满足。 ")
                          ], -1))
                        ])
                      ]),
                      _createElementVNode$1("div", _hoisted_15, [
                        _cache[28] || (_cache[28] = _createElementVNode$1("div", { class: "fwd-logic-title" }, "置顶与内容转换", -1)),
                        _createElementVNode$1("div", _hoisted_16, [
                          _createElementVNode$1("div", null, [
                            _createVNode$1(_component_VSwitch, {
                              modelValue: rule.pin_links_enabled,
                              "onUpdate:modelValue": $event => ((rule.pin_links_enabled) = $event),
                              color: "primary",
                              "hide-details": "",
                              inset: ""
                            }, {
                              label: _withCtx$1(() => [...(_cache[25] || (_cache[25] = [
                                _createElementVNode$1("span", { class: "fwd-switch-label" }, "转发后置顶", -1)
                              ]))]),
                              _: 1
                            }, 8, ["modelValue", "onUpdate:modelValue"]),
                            (rule.pin_links_enabled)
                              ? (_openBlock$1(), _createBlock$1(_component_VCombobox, {
                                  key: 0,
                                  modelValue: rule.pin_link_keywords,
                                  "onUpdate:modelValue": $event => ((rule.pin_link_keywords) = $event),
                                  multiple: "",
                                  chips: "",
                                  "closable-chips": "",
                                  label: "仅命中这些关键词时置顶（留空=有链接就置顶）",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": "",
                                  class: "fwd-keywords"
                                }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                              : (_openBlock$1(), _createElementBlock$1("div", _hoisted_17, "置顶以链接为对象：没有链接的消息不置顶。"))
                          ]),
                          _createElementVNode$1("div", null, [
                            _createVNode$1(_component_VSwitch, {
                              modelValue: rule.enable_transform,
                              "onUpdate:modelValue": $event => ((rule.enable_transform) = $event),
                              color: "primary",
                              "hide-details": "",
                              inset: ""
                            }, {
                              label: _withCtx$1(() => [...(_cache[26] || (_cache[26] = [
                                _createElementVNode$1("span", { class: "fwd-switch-label" }, "内容转换", -1)
                              ]))]),
                              _: 1
                            }, 8, ["modelValue", "onUpdate:modelValue"]),
                            _cache[27] || (_cache[27] = _createElementVNode$1("div", { class: "fwd-hint" }, "转换后以新内容发送（不改动原消息）。", -1))
                          ]),
                          _createElementVNode$1("div", null, [
                            (rule.enable_transform)
                              ? (_openBlock$1(), _createBlock$1(_component_VTextarea, {
                                  key: 0,
                                  modelValue: transformText.value[rule.id || index],
                                  "onUpdate:modelValue": [$event => ((transformText.value[rule.id || index]) = $event), $event => (syncTransform(rule, index))],
                                  label: "转换规则（每行一条：原文 -> 替换文，支持正则）",
                                  placeholder: "广告词.*-> \n@\\w+ -> ",
                                  rows: "3",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": "",
                                  class: "fwd-transform"
                                }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                              : _createCommentVNode$1("", true)
                          ])
                        ])
                      ])
                    ]),
                    _: 2
                  }, 1024)
                ]),
                _: 2
              }, 1024))
            }), 128)),
            (rules.value.length)
              ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_18, [
                  _createVNode$1(_component_VBtn, {
                    color: "primary",
                    variant: "flat",
                    "prepend-icon": "mdi-content-save-outline",
                    loading: busy.value === 'save',
                    onClick: saveRules
                  }, {
                    default: _withCtx$1(() => [...(_cache[29] || (_cache[29] = [
                      _createTextVNode$1(" 保存规则（即时生效） ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"]),
                  _cache[30] || (_cache[30] = _createElementVNode$1("span", { class: "fwd-hint" }, "规则保存在插件配置里；开关与其它模块设置随底部「保存配置」持久化。", -1))
                ]))
              : _createCommentVNode$1("", true)
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$1(_component_VCard, {
      flat: "",
      class: "fwd-card"
    }, {
      default: _withCtx$1(() => [
        _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
          default: _withCtx$1(() => [...(_cache[31] || (_cache[31] = [
            _createTextVNode$1("规则测试", -1)
          ]))]),
          _: 1
        }),
        _createVNode$1(_component_VCardText, null, {
          default: _withCtx$1(() => [
            _createVNode$1(_component_VTextarea, {
              modelValue: testText.value,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((testText).value = $event)),
              label: "粘贴一条来源频道消息原文",
              placeholder: "剧名.S01E02.2160p.WEB-DL.mkv\nhttps://115.com/s/xxxxx?password=abcd",
              rows: "3",
              density: "compact",
              variant: "outlined",
              "hide-details": ""
            }, null, 8, ["modelValue"]),
            _createElementVNode$1("div", _hoisted_19, [
              _createVNode$1(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-test-tube",
                loading: busy.value === 'test',
                onClick: runTest
              }, {
                default: _withCtx$1(() => [...(_cache[32] || (_cache[32] = [
                  _createTextVNode$1(" 测试（不转发、不入队） ", -1)
                ]))]),
                _: 1
              }, 8, ["loading"])
            ]),
            (testResult.value)
              ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_20, [
                  _createElementVNode$1("div", _hoisted_21, [
                    _cache[33] || (_cache[33] = _createElementVNode$1("strong", null, "识别结果：", -1)),
                    (testResult.value.recognized)
                      ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_22, [
                          _createTextVNode$1(" 《" + _toDisplayString$1(testResult.value.recognized.title) + "》 ", 1),
                          (testResult.value.recognized.year)
                            ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_23, "（" + _toDisplayString$1(testResult.value.recognized.year) + "）", 1))
                            : _createCommentVNode$1("", true),
                          (testResult.value.recognized.season)
                            ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_24, " S" + _toDisplayString$1(String(testResult.value.recognized.season).padStart(2, '0')), 1))
                            : _createCommentVNode$1("", true),
                          (testResult.value.recognized.episode)
                            ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_25, "E" + _toDisplayString$1(String(testResult.value.recognized.episode).padStart(2, '0')), 1))
                            : _createCommentVNode$1("", true)
                        ]))
                      : (_openBlock$1(), _createElementBlock$1("span", _hoisted_26, "无法识别（不影响转发：转发只按关键词与扩展名匹配）"))
                  ]),
                  (testResult.value.links?.length)
                    ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_27, [
                        _createElementVNode$1("strong", null, "解析到 " + _toDisplayString$1(testResult.value.links.length) + " 个链接", 1)
                      ]))
                    : _createCommentVNode$1("", true),
                  _createVNode$1(_component_VList, {
                    density: "compact",
                    class: "fwd-test-list"
                  }, {
                    default: _withCtx$1(() => [
                      (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(testResult.value.rules, (trace, index) => {
                        return (_openBlock$1(), _createBlock$1(_component_VListItem, { key: index }, {
                          prepend: _withCtx$1(() => [
                            _createVNode$1(_component_VIcon, {
                              icon: trace.matched ? 'mdi-share-outline' : 'mdi-minus-circle-outline',
                              size: "18",
                              color: trace.matched ? 'success' : 'warning'
                            }, null, 8, ["icon", "color"])
                          ]),
                          default: _withCtx$1(() => [
                            _createVNode$1(_component_VListItemTitle, { class: "fwd-test-name" }, {
                              default: _withCtx$1(() => [
                                _createTextVNode$1(_toDisplayString$1(trace.rule_name) + " ", 1),
                                (!trace.enabled)
                                  ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                                      key: 0,
                                      size: "x-small",
                                      variant: "tonal",
                                      color: "default",
                                      label: "",
                                      class: "fwd-test-off"
                                    }, {
                                      default: _withCtx$1(() => [...(_cache[34] || (_cache[34] = [
                                        _createTextVNode$1("已停用", -1)
                                      ]))]),
                                      _: 1
                                    }))
                                  : _createCommentVNode$1("", true),
                                (trace.pin)
                                  ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                                      key: 1,
                                      size: "x-small",
                                      variant: "tonal",
                                      color: "info",
                                      label: "",
                                      class: "fwd-test-off"
                                    }, {
                                      default: _withCtx$1(() => [...(_cache[35] || (_cache[35] = [
                                        _createTextVNode$1("置顶", -1)
                                      ]))]),
                                      _: 1
                                    }))
                                  : _createCommentVNode$1("", true)
                              ]),
                              _: 2
                            }, 1024),
                            _createVNode$1(_component_VListItemSubtitle, { class: "fwd-test-msg" }, {
                              default: _withCtx$1(() => [
                                _createTextVNode$1(_toDisplayString$1(_unref$1(decisionLabel)(trace.decision)) + " · " + _toDisplayString$1(trace.reason) + " ", 1),
                                (trace.matched && trace.send_text)
                                  ? (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 0 }, [
                                      _createTextVNode$1(" ▸ 将发送：" + _toDisplayString$1(trace.send_text), 1)
                                    ], 64))
                                  : _createCommentVNode$1("", true)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _: 2
                        }, 1024))
                      }), 128))
                    ]),
                    _: 1
                  })
                ]))
              : _createCommentVNode$1("", true)
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$1(_component_VCard, {
      flat: "",
      class: "fwd-card"
    }, {
      default: _withCtx$1(() => [
        _createVNode$1(_component_VCardItem, null, {
          append: _withCtx$1(() => [
            _createVNode$1(_component_VSelect, {
              modelValue: decisionFilter.value,
              "onUpdate:modelValue": [
                _cache[2] || (_cache[2] = $event => ((decisionFilter).value = $event)),
                onDecisionFilter
              ],
              items: [{ value: '', title: '全部决策' }, ...decisions.value],
              "item-title": "title",
              "item-value": "value",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              class: "fwd-filter"
            }, null, 8, ["modelValue", "items"])
          ]),
          default: _withCtx$1(() => [
            _createVNode$1(_component_VCardTitle, { class: "text-subtitle-2" }, {
              default: _withCtx$1(() => [...(_cache[36] || (_cache[36] = [
                _createTextVNode$1("转发流水", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$1(_component_VCardText, null, {
          default: _withCtx$1(() => [
            _createElementVNode$1("div", _hoisted_28, [
              _createVNode$1(_component_VTextField, {
                modelValue: hitKeyword.value,
                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((hitKeyword).value = $event)),
                placeholder: "按片名 / 规则 / 说明搜索",
                "prepend-inner-icon": "mdi-magnify",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                clearable: "",
                class: "fwd-hits-search"
              }, null, 8, ["modelValue"]),
              _createVNode$1(_component_VBtn, {
                size: "small",
                variant: "tonal",
                color: "error",
                "prepend-icon": "mdi-delete-outline",
                disabled: !hitsTotal.value,
                onClick: _cache[4] || (_cache[4] = $event => (askClear('filtered')))
              }, {
                default: _withCtx$1(() => [...(_cache[37] || (_cache[37] = [
                  _createTextVNode$1(" 删除筛选结果 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"]),
              _createVNode$1(_component_VBtn, {
                size: "small",
                variant: "text",
                color: "error",
                disabled: !hitsTotal.value,
                onClick: _cache[5] || (_cache[5] = $event => (askClear('all')))
              }, {
                default: _withCtx$1(() => [...(_cache[38] || (_cache[38] = [
                  _createTextVNode$1(" 清空本类流水 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"])
            ]),
            _createVNode$1(_component_VTable, {
              density: "compact",
              class: "fwd-hits"
            }, {
              default: _withCtx$1(() => [
                _cache[40] || (_cache[40] = _createElementVNode$1("thead", null, [
                  _createElementVNode$1("tr", null, [
                    _createElementVNode$1("th", { class: "fwd-nowrap" }, "时间"),
                    _createElementVNode$1("th", { class: "fwd-nowrap" }, "规则"),
                    _createElementVNode$1("th", { class: "fwd-nowrap" }, "来源"),
                    _createElementVNode$1("th", null, "媒体"),
                    _createElementVNode$1("th", { class: "fwd-nowrap" }, "决策"),
                    _createElementVNode$1("th", null, "说明")
                  ])
                ], -1)),
                _createElementVNode$1("tbody", null, [
                  (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(hits.value, (item) => {
                    return (_openBlock$1(), _createElementBlock$1("tr", {
                      key: item.id
                    }, [
                      _createElementVNode$1("td", _hoisted_29, _toDisplayString$1(fmtTime(item.created_at)), 1),
                      _createElementVNode$1("td", _hoisted_30, _toDisplayString$1(item.rule_name), 1),
                      _createElementVNode$1("td", _hoisted_31, _toDisplayString$1(chatTitleMap.value[item.chat_id] || item.chat_id), 1),
                      _createElementVNode$1("td", null, [
                        (item.title)
                          ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_32, _toDisplayString$1(mediaName(item)), 1))
                          : (_openBlock$1(), _createElementBlock$1("span", _hoisted_33, "—"))
                      ]),
                      _createElementVNode$1("td", _hoisted_34, [
                        _createVNode$1(_component_VChip, {
                          size: "x-small",
                          variant: "tonal",
                          color: _unref$1(decisionColor)(item.decision),
                          label: ""
                        }, {
                          default: _withCtx$1(() => [
                            _createTextVNode$1(_toDisplayString$1(_unref$1(decisionLabel)(item.decision)), 1)
                          ]),
                          _: 2
                        }, 1032, ["color"])
                      ]),
                      _createElementVNode$1("td", _hoisted_35, _toDisplayString$1(item.detail), 1)
                    ]))
                  }), 128)),
                  (!hits.value.length)
                    ? (_openBlock$1(), _createElementBlock$1("tr", _hoisted_36, [...(_cache[39] || (_cache[39] = [
                        _createElementVNode$1("td", {
                          colspan: "6",
                          class: "fwd-hits-empty"
                        }, "暂无记录", -1)
                      ]))]))
                    : _createCommentVNode$1("", true)
                ])
              ]),
              _: 1
            }),
            _createElementVNode$1("div", _hoisted_37, [
              _createVNode$1(_component_VBtn, {
                size: "small",
                variant: "text",
                disabled: hitsPage.value <= 1,
                "prepend-icon": "mdi-chevron-left",
                onClick: prevHits
              }, {
                default: _withCtx$1(() => [...(_cache[41] || (_cache[41] = [
                  _createTextVNode$1(" 上一页 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"]),
              _createElementVNode$1("span", _hoisted_38, "第 " + _toDisplayString$1(hitsPage.value) + " 页 · 共 " + _toDisplayString$1(hitsTotal.value) + " 条", 1),
              _createVNode$1(_component_VBtn, {
                size: "small",
                variant: "text",
                disabled: hitsPage.value * hitsPageSize >= hitsTotal.value,
                "append-icon": "mdi-chevron-right",
                onClick: nextHits
              }, {
                default: _withCtx$1(() => [...(_cache[42] || (_cache[42] = [
                  _createTextVNode$1(" 下一页 ", -1)
                ]))]),
                _: 1
              }, 8, ["disabled"])
            ])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _cache[50] || (_cache[50] = _createElementVNode$1("div", { class: "fwd-hint" }, " 风控提示：TG 个人号转发有严格频率限制，插件按「聚合窗口 + 全局冷却 + FloodWait 退避」克制发送； 转发目标建议用小号或私密频道，避免主号因高频转发被限制。 ", -1)),
    _createVNode$1(_component_VDialog, {
      modelValue: clearDialog.value,
      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((clearDialog).value = $event)),
      "max-width": "460"
    }, {
      default: _withCtx$1(() => [
        _createVNode$1(_component_VCard, null, {
          default: _withCtx$1(() => [
            _createVNode$1(_component_VCardTitle, { class: "text-subtitle-1" }, {
              default: _withCtx$1(() => [
                _createTextVNode$1(_toDisplayString$1(clearTarget.value === 'all' ? '清空转发流水' : '删除筛选结果'), 1)
              ]),
              _: 1
            }),
            _createVNode$1(_component_VCardText, { class: "text-body-2" }, {
              default: _withCtx$1(() => [
                (hasFilter.value)
                  ? (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 0 }, [
                      _cache[43] || (_cache[43] = _createTextVNode$1(" 当前有筛选条件，将只删除筛选出的 ", -1)),
                      _createElementVNode$1("strong", null, _toDisplayString$1(hitsTotal.value), 1),
                      _cache[44] || (_cache[44] = _createTextVNode$1(" 条流水 ", -1)),
                      (filterText.value)
                        ? (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 0 }, [
                            _createTextVNode$1("（筛选：" + _toDisplayString$1(filterText.value) + "）", 1)
                          ], 64))
                        : _createCommentVNode$1("", true),
                      _cache[45] || (_cache[45] = _createTextVNode$1(" ，删除后不可恢复；未筛选部分不受影响。如需清空全部，请先清除筛选条件。 ", -1))
                    ], 64))
                  : (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 1 }, [
                      _cache[46] || (_cache[46] = _createTextVNode$1(" 将删除本面板的", -1)),
                      _cache[47] || (_cache[47] = _createElementVNode$1("strong", null, "全部转发流水", -1)),
                      _createTextVNode$1("（共 " + _toDisplayString$1(hitsTotal.value) + " 条），删除后不可恢复； 资源监控的流水不受影响。 ", 1)
                    ], 64))
              ]),
              _: 1
            }),
            _createVNode$1(_component_VCardActions, null, {
              default: _withCtx$1(() => [
                _createVNode$1(_component_VSpacer),
                _createVNode$1(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[6] || (_cache[6] = $event => (clearDialog.value = false))
                }, {
                  default: _withCtx$1(() => [...(_cache[48] || (_cache[48] = [
                    _createTextVNode$1("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode$1(_component_VBtn, {
                  color: "error",
                  loading: clearing.value,
                  onClick: runClear
                }, {
                  default: _withCtx$1(() => [...(_cache[49] || (_cache[49] = [
                    _createTextVNode$1("删除", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const ConfigForwardPane = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-cd06622a"]]);

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
  // ② 115 网盘（登录态只走扫码，Cookie 存插件数据，不放配置/表单）
  pan115_enabled: false,
  pan115_target_cid: '',
  pan115_batch_max_size: 20,
  // ④ TG 资源监控（规则结构见 /monitor/rules 接口返回；id 由后端补缺）
  monitor_enabled: false,
  monitor_rules: [],
  // ⑤ 历史消息缓存（设置由 /cache/settings 归一，这里保证「保存配置」不丢字段）
  cache_enabled: false,
  cache_chat_ids: [],
  cache_destination: 'smart',
  cache_sync_mode: 'relative',
  cache_sync_days: 30,
  cache_batch_size: 200,
  cache_subscribe_enabled: true,
  cache_cron: '0 */6 * * *',
  cache_subscribe_cron: '*/30 * * * *',
  // ⑥ TG 通用转发（规则结构见 /forward/rules 接口返回；id 由后端补缺，f 前缀）
  forward_enabled: false,
  forward_rules: [],
  // 通知（P7 启用：走 MP 通知渠道 post_message）
  notify_on_hit: true,
  notify_on_error: true,
  notify_on_search: true,
};

// ⚠️ 新增配置项时必须同步加到这里：保存是"整份覆盖"，
// 表单里没有的字段会被清空（后端自管状态请改存插件数据，不要放配置）。

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
  { key: 'pan115', title: '115 网盘', icon: 'mdi-cloud-outline', desc: '登录态、目标目录、批量提交与通知' },
  { key: 'monitor', title: '资源监控', icon: 'mdi-radar', desc: '监听频道、推送目标、仅缺集' },
  { key: 'cache', title: '消息缓存', icon: 'mdi-database-outline', desc: '缓存频道、同步与检索' },
  { key: 'forward', title: '通用转发', icon: 'mdi-share-outline', desc: '关键词与扩展名匹配、置顶与内容转换' },
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
                      : _createCommentVNode("", true)
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
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-394db4a1"]]);

export { Config as default };
