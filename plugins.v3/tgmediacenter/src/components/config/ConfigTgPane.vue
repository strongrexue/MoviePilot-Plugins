<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from '../api'
import { FRONTEND_VERSION } from '../version'
import SecretField from './SecretField.vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
})

const status = ref(null)
const statusLoading = ref(false)
const busy = ref('')
const message = ref('')
const messageOk = ref(true)
const loginStage = ref('idle') // idle | code_sent | need_password
const code = ref('')
const password = ref('')
const dialogs = ref([])
const dialogsUpdatedAt = ref('')
// 当前待验证码的上下文：投递渠道 + 手机号掩码 + 发码时间
const sent = ref(null)
// 距离允许重新发送验证码的剩余秒数
const resendIn = ref(0)
// 账号手机号是否明文显示（凭据输入框由 SecretField 各自管理）
const reveal = ref({ phone: false })
let countdownId = null

const form = computed(() => props.config.form)

/**
 * 前端构建版本与后端插件版本是否一致。
 *
 * 联邦组件入口无哈希、宿主加载器也不加缓存参数，因此"插件更新了但浏览器还在用旧
 * 组件"是常态。版本不一致时直接提示，避免对着旧界面排查新问题。
 */
const versionMismatch = computed(() => {
  const backend = String(status.value?.plugin_version || '')
  if (!backend) return ''
  return backend === FRONTEND_VERSION ? '' : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backend}`
})

const sendLabel = computed(() => {
  if (resendIn.value > 0) return `重新发送（${resendIn.value}s）`
  return loginStage.value === 'code_sent' ? '重新发送验证码' : '发送验证码'
})

const sendDisabled = computed(() => Boolean(busy.value) || resendIn.value > 0)

function setMessage(text, ok = true) {
  message.value = text || ''
  messageOk.value = ok
}

/** 打码敏感值：保留首尾片段便于核对。 */
function maskValue(value, keep = 4) {
  const text = String(value || '')
  if (!text) return ''
  if (text.length <= keep * 2) return '*'.repeat(text.length)
  return `${text.slice(0, keep)}${'*'.repeat(6)}${text.slice(-keep)}`
}

function startCountdown(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  if (countdownId) {
    clearInterval(countdownId)
    countdownId = null
  }
  resendIn.value = total
  if (total <= 0) return
  countdownId = setInterval(() => {
    resendIn.value = Math.max(0, resendIn.value - 1)
    if (resendIn.value <= 0 && countdownId) {
      clearInterval(countdownId)
      countdownId = null
    }
  }, 1000)
}

function applyPending(pending) {
  if (!pending) return
  sent.value = pending
  loginStage.value = loginStage.value === 'need_password' ? 'need_password' : 'code_sent'
  // 仅在未倒计时时同步，避免覆盖刚发码后的本地计时
  if (!countdownId && resendIn.value <= 0) startCountdown(pending.resend_in)
}

async function loadStatus() {
  statusLoading.value = true
  try {
    const info = unwrap(await getPluginApi(props.api, props.pluginId, 'status', { timeoutMs: 15000 }))
    status.value = info
    // 硬刷新后从后端恢复登录向导，避免用户误以为需要重新发码
    if (info?.authorized) {
      loginStage.value = 'idle'
      sent.value = null
      startCountdown(0)
    } else {
      applyPending(info?.pending_login)
    }
  } catch (err) {
    setMessage(err?.message || '状态读取失败', false)
  } finally {
    statusLoading.value = false
  }
}

async function loadDialogs() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'telegram/dialogs', { timeoutMs: 15000 }))
    dialogs.value = data?.dialogs || []
    dialogsUpdatedAt.value = data?.updated_at || ''
  } catch {
    dialogs.value = []
    dialogsUpdatedAt.value = ''
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
  ))
  dialogs.value = data?.dialogs || []
  dialogsUpdatedAt.value = data?.updated_at || ''
  return dialogs.value.length
}

/** 网关中断（502 等）时后端可能仍在跑，回头同步一次状态以拿到真实结果。 */
async function resyncAfterTransportError(err) {
  if (err?.code !== 'GATEWAY_TIMEOUT' && err?.status !== 502 && err?.status !== 504) return
  await loadStatus()
  await loadDialogs()
}

async function sendCode() {
  if (busy.value) return
  if (resendIn.value > 0) {
    setMessage(`请先使用已收到的验证码，${resendIn.value} 秒后可重新发送`, false)
    return
  }
  busy.value = 'send_code'
  setMessage('')
  try {
    const phone = String(form.value.tg_phone || '').trim()
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
    ))
    loginStage.value = 'code_sent'
    sent.value = {
      delivery: result?.delivery || 'unknown',
      delivery_text: result?.delivery_text || '已发送，请查看 Telegram',
      phone_masked: result?.phone_masked || '',
      sent_at: new Date().toLocaleTimeString(),
    }
    startCountdown(result?.resend_in)
    setMessage(result?.message || '验证码已发送')
  } catch (err) {
    setMessage(err?.message || '发送验证码失败', false)
    await resyncAfterTransportError(err)
  } finally {
    busy.value = ''
  }
}

async function signIn() {
  if (busy.value) return
  busy.value = 'sign_in'
  setMessage('')
  try {
    const result = unwrap(await postPluginApi(props.api, props.pluginId, 'telegram/sign_in', {
      phone: String(form.value.tg_phone || '').trim(),
      code: String(code.value || '').trim(),
      password: String(password.value || '').trim(),
    }, { timeoutMs: 62000 }))
    if (result?.need_password) {
      loginStage.value = 'need_password'
      setMessage(result?.message || '请输入两步验证密码', false)
    } else if (result?.authorized) {
      loginStage.value = 'idle'
      code.value = ''
      password.value = ''
      sent.value = null
      startCountdown(0)
      await loadStatus()
      // 首次登录**不再自动拉取**对话列表：改由用户手动点「刷新对话列表」。
      // 拉取要遍历账号全部对话，放在登录流程里会让人以为"登录卡住了"，
      // 而且登录本身已经成功，不该被后续动作拖住。
      setMessage(
        dialogs.value.length
          ? `登录成功，已复用本地缓存的 ${dialogs.value.length} 个对话；如需更新请点「刷新对话列表」`
          : '登录成功。请点「刷新对话列表」拉取群组 / 频道（后续配置监控与转发规则会用到）',
      )
    } else {
      setMessage(result?.message || '登录未完成', false)
    }
  } catch (err) {
    setMessage(err?.message || '登录失败', false)
    await resyncAfterTransportError(err)
  } finally {
    busy.value = ''
  }
}

async function logout() {
  if (busy.value) return
  busy.value = 'logout'
  setMessage('')
  try {
    const result = unwrap(await postPluginApi(props.api, props.pluginId, 'telegram/logout', {}, { timeoutMs: 40000 }))
    loginStage.value = 'idle'
    dialogs.value = []
    dialogsUpdatedAt.value = ''
    sent.value = null
    startCountdown(0)
    setMessage(result?.message || '已退出登录')
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '退出登录失败', false)
  } finally {
    busy.value = ''
  }
}

async function refreshDialogs() {
  if (busy.value) return
  busy.value = 'refresh'
  setMessage('正在拉取对话列表（首次可能较慢，请稍候）…')
  try {
    const count = await fetchDialogs()
    setMessage(count > 0 ? `对话列表已刷新，共 ${count} 条` : '拉取完成，但该账号没有可取用的对话', count > 0)
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '刷新对话列表失败', false)
    await resyncAfterTransportError(err)
  } finally {
    busy.value = ''
  }
}

async function reconnect() {
  if (busy.value) return
  busy.value = 'connect'
  setMessage('正在连接 Telegram（可能需要十几秒）…')
  try {
    const info = unwrap(await postPluginApi(props.api, props.pluginId, 'telegram/connect', {}, { timeoutMs: 32000 }))
    status.value = info
    if (info?.authorized) {
      loginStage.value = 'idle'
      sent.value = null
      setMessage('已连接并处于登录状态')
    } else {
      setMessage('已连接，但当前未登录：请发送验证码登录', false)
    }
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '连接 Telegram 失败', false)
  } finally {
    busy.value = ''
  }
}

const chips = computed(() => {
  const info = status.value || {}
  const connection = info.connected
    ? { text: 'TG 已连接', color: 'success' }
    : info.running
      ? { text: 'TG 连接断开', color: 'error' }
      : { text: 'TG 未启动', color: 'default' }
  return [
    { text: info.telethon_available ? 'telethon 已安装' : 'telethon 未安装', color: info.telethon_available ? 'success' : 'error' },
    info.api_id_issue
      ? { text: 'API ID 格式不对', color: 'error' }
      : { text: info.api_configured ? 'API 凭证已填' : 'API 凭证未填', color: info.api_configured ? 'success' : 'warning' },
    { text: info.session_present ? '会话已保存' : '无会话', color: info.session_present ? 'success' : 'default' },
    connection,
    { text: info.authorized ? '已登录' : '未登录', color: info.authorized ? 'success' : 'warning' },
  ]
})

/**
 * 对话列表的下拉框选项。
 *
 * 原实现用整块 VCard + VList 展示，占掉页面一大片高度；改成下拉框内部滑动后，
 * 只渲染展开时可见的条目。type / name 缺失时用「其他」/「名称未知」兜底。
 */
const dialogItems = computed(() => (dialogs.value || []).map((item) => ({
  title: `${item?.type || '其他'} · ${item?.name || '名称未知'}（${item?.id ?? ''}）`,
  value: item?.id ?? null,
})))

/** 会话已保存但客户端没连上：提示自愈路径，避免误以为"登录丢了"。 */
const needsReconnect = computed(() => {
  const info = status.value || {}
  return Boolean(info.api_configured && info.session_present && !info.connected && !statusLoading.value)
})

onMounted(async () => {
  await loadStatus()
  await loadDialogs()
})

onUnmounted(() => {
  if (countdownId) clearInterval(countdownId)
  countdownId = null
})
</script>

<template>
  <div class="tg-pane">
    <div class="tg-status-head">
      <div class="tg-status-chips">
        <VChip v-for="chip in chips" :key="chip.text" :color="chip.color" size="small" variant="tonal" label>
          {{ chip.text }}
        </VChip>
      </div>
      <div class="tg-status-actions">
        <VBtn size="small" variant="text" prepend-icon="mdi-connection" :loading="busy === 'connect'" @click="reconnect">
          重连
        </VBtn>
        <VBtn size="small" variant="text" prepend-icon="mdi-refresh" :loading="statusLoading" @click="loadStatus">
          刷新状态
        </VBtn>
      </div>
    </div>

    <VAlert v-if="versionMismatch" type="warning" variant="tonal" density="comfortable" class="tg-message">
      {{ versionMismatch }} —— 浏览器仍在用缓存的旧联邦组件。请按 Ctrl+Shift+R 硬刷新页面（必要时清缓存）后再操作，否则会对着旧界面排查新问题。
    </VAlert>

    <VAlert v-if="status?.me" type="success" variant="tonal" density="comfortable" class="tg-account">
      已登录：{{ status.me.name || status.me.username }}
      <span v-if="status.me.username">（@{{ status.me.username }}）</span>
      <span v-if="status.me.phone" class="tg-secret" :title="reveal.phone ? '点击隐藏' : '点击显示'"
            @click="reveal.phone = !reveal.phone">
        · {{ reveal.phone ? status.me.phone : maskValue(status.me.phone) }}
        <VIcon :icon="reveal.phone ? 'mdi-eye-off-outline' : 'mdi-eye-outline'" size="14" />
      </span>
      <span> · 对话缓存 {{ status.dialog_count }} 条</span>
      <span v-if="status.dialogs_updated_at"> · 更新于 {{ status.dialogs_updated_at }}</span>
    </VAlert>

    <VAlert
      v-if="message"
      :type="messageOk ? 'info' : 'warning'"
      variant="tonal"
      density="comfortable"
      class="tg-message"
    >{{ message }}</VAlert>

    <VCard flat class="tg-card">
      <VCardTitle class="text-subtitle-2">API 凭证</VCardTitle>
      <VCardText>
        <VRow dense>
          <VCol cols="12" md="6">
            <VTextField
              v-model="form.tg_api_id"
              label="API ID（纯数字）"
              type="number"
              placeholder="12345678"
              density="compact"
              variant="outlined"
              hide-details
            />
          </VCol>
          <VCol cols="12" md="6">
            <SecretField v-model="form.tg_api_hash" label="API Hash" />
          </VCol>
          <VCol cols="12" md="6">
            <SecretField v-model="form.tg_phone" label="手机号（含国家码）" placeholder="+8613800000000" />
          </VCol>
          <VCol cols="12" md="6">
            <VTextField
              v-model.number="form.tg_user_cooldown_seconds"
              type="number"
              label="个人账号转发冷却（秒）"
              density="compact"
              variant="outlined"
              hide-details
            />
          </VCol>
          <VCol cols="12" md="6">
            <VTextField
              v-model.number="form.tg_keep_alive_seconds"
              type="number"
              label="保活间隔（秒）"
              density="compact"
              variant="outlined"
              hide-details
            />
          </VCol>
          <VCol cols="12" md="6">
            <VTextField
              v-model.number="form.tg_aggregation_window_seconds"
              type="number"
              step="0.5"
              label="消息聚合窗口（秒）"
              density="compact"
              variant="outlined"
              hide-details
            />
          </VCol>
        </VRow>
        <VAlert
          v-if="status && status.api_id_issue"
          type="error"
          variant="tonal"
          density="compact"
          class="tg-message"
        >{{ status.api_id_issue }}</VAlert>
        <div class="tg-hint">
          API ID / Hash 需在 my.telegram.org 申请；代理自动继承 MoviePilot 的系统代理设置。
          API ID、API Hash、手机号默认打码，点右侧眼睛可查看（打码只影响显示，保存的仍是真实值）。
        </div>
      </VCardText>
    </VCard>

    <VCard flat class="tg-card">
      <VCardTitle class="text-subtitle-2">登录向导</VCardTitle>
      <VCardText>
        <!-- 已授权：收起验证码输入与登录按钮，只保留状态与操作（对齐 MA 的"已授权"形态） -->
        <template v-if="status?.authorized">
          <div class="tg-authorized">
            <VChip color="success" variant="tonal" prepend-icon="mdi-account-check-outline" label>
              Telegram 客户端 已授权
            </VChip>
            <span v-if="status?.me" class="tg-authorized-name">
              {{ status.me.name || status.me.username }}
              <span v-if="status.me.username">（@{{ status.me.username }}）</span>
            </span>
          </div>
          <div class="tg-wizard-actions">
            <VBtn
              variant="tonal"
              :loading="busy === 'refresh'"
              :disabled="Boolean(busy) && busy !== 'refresh'"
              prepend-icon="mdi-account-multiple-outline"
              @click="refreshDialogs"
            >
              刷新对话列表
            </VBtn>
            <VBtn
              variant="text"
              color="error"
              :loading="busy === 'logout'"
              prepend-icon="mdi-logout"
              @click="logout"
            >
              退出登录
            </VBtn>
          </div>
          <div class="tg-hint">
            已登录状态下不需要验证码。如需更换账号，请先「退出登录」。
            <template v-if="!dialogs.length">
              尚未拉取对话列表：请点一次「刷新对话列表」（登录后不会自动拉取）。
            </template>
          </div>
        </template>

        <template v-else>
          <VAlert v-if="needsReconnect" type="warning" variant="tonal" density="comfortable" class="tg-message">
            会话已保存，但 TG 客户端当前未连接：插件已在后台自动重连，约 10 秒后点「刷新状态」；
            也可点右上角「重连」立即重试。
          </VAlert>
          <VAlert
            v-if="sent && loginStage !== 'idle'"
            type="info"
            variant="tonal"
            density="comfortable"
            class="tg-message"
          >
            验证码{{ sent.delivery_text }}
            <span v-if="sent.phone_masked"> · {{ sent.phone_masked }}</span>
            <span v-if="resendIn > 0"> · {{ resendIn }} 秒后可重新发送</span>
          </VAlert>
          <div class="tg-wizard">
            <VBtn
              color="primary"
              variant="flat"
              :loading="busy === 'send_code'"
              :disabled="sendDisabled"
              prepend-icon="mdi-send-outline"
              @click="sendCode"
            >
              {{ sendLabel }}
            </VBtn>
            <VTextField
              v-model="code"
              label="验证码"
              density="compact"
              variant="outlined"
              hide-details
              class="tg-wizard-input"
              :disabled="loginStage === 'need_password'"
            />
            <VBtn
              color="success"
              variant="flat"
              :loading="busy === 'sign_in'"
              prepend-icon="mdi-login-variant"
              @click="signIn"
            >
              登录
            </VBtn>
          </div>
          <div v-if="loginStage === 'need_password'" class="tg-wizard tg-wizard-password">
            <VTextField
              v-model="password"
              type="password"
              label="两步验证密码"
              density="compact"
              variant="outlined"
              hide-details
              class="tg-wizard-input"
            />
            <VBtn
              color="warning"
              variant="flat"
              :loading="busy === 'sign_in'"
              prepend-icon="mdi-shield-key-outline"
              @click="signIn"
            >
              提交两步验证
            </VBtn>
          </div>
          <div class="tg-wizard-actions">
            <VBtn
              variant="tonal"
              :loading="busy === 'refresh'"
              :disabled="Boolean(busy) && busy !== 'refresh'"
              prepend-icon="mdi-account-multiple-outline"
              @click="refreshDialogs"
            >
              刷新对话列表
            </VBtn>
          </div>
          <div class="tg-hint">
            凭证需先点底部「保存配置」再发码。若未收到验证码，等倒计时结束后可重新发送；
            刷新页面不会丢失已发出的验证码，直接输入即可。
          </div>
        </template>
      </VCardText>
    </VCard>

    <!-- 对话列表：只读下拉框，展开后在菜单内滑动查看 / 搜索，不再整块铺开 -->
    <div class="tg-dialogs">
      <VAutocomplete
        :items="dialogItems"
        :model-value="null"
        :label="`对话列表（${dialogs.length} 个）`"
        density="compact"
        variant="outlined"
        hide-details
        :menu-props="{ maxHeight: 320 }"
        :no-data-text="dialogs.length ? '没有匹配的对话' : '暂无缓存：登录后点「刷新对话列表」拉取'"
      />
      <div class="tg-hint">
        <template v-if="dialogsUpdatedAt">更新于 {{ dialogsUpdatedAt }}。 </template>
        展开下拉框可滑动查看全部对话，也可直接输入关键词搜索；点「刷新对话列表」重新拉取。
      </div>
    </div>
  </div>
</template>

<style scoped>
.tg-pane { display: flex; flex-direction: column; gap: 8px; }
.tg-status-head { display: flex; align-items: center; justify-content: space-between; gap: 6px; flex-wrap: wrap; }
.tg-status-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.tg-status-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.tg-authorized { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tg-authorized-name { font-size: 13px; color: rgba(var(--v-theme-on-surface), 0.75); }
.tg-account,
.tg-message { font-size: 13px; }
/* 分区卡外观（对齐效果图「豆瓣中心」）：有底色的圆角块 + 1px 描边，块与块之间 8px。
   Vuetify 的 flat 卡片会把背景重置成与对话框同色的 surface，故用 !important 压过它，
   描边也改用 on-surface 的显式 alpha，避免主题变量缺失时整条 border 声明失效（计算值 0px） */
.tg-card {
  background: rgba(var(--v-theme-on-surface), 0.04) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10) !important;
  border-radius: 10px;
}
/* 卡片内外边距统一压到 10/12（压过 Vuetify 直系子元素的 16/24）；标题区与正文区相邻处只留一份 */
.tg-card > .v-card-item { padding: 10px 12px; }
.tg-card > .v-card-title { padding: 10px 12px; }
.tg-card > .v-card-text { padding: 10px 12px; }
.tg-card > .v-card-item + .v-card-text,
.tg-card > .v-card-title + .v-card-text { padding-top: 0; }
.tg-wizard { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
.tg-wizard-password { margin-top: 6px; }
.tg-wizard-input { flex: 1 1 200px; min-width: 160px; }
.tg-wizard-actions { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }
.tg-dialogs { display: flex; flex-direction: column; gap: 6px; }
.tg-dialogs .tg-hint { margin-top: 0; }
.tg-hint { margin-top: 4px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.5; }
.tg-secret { cursor: pointer; user-select: none; }
</style>
