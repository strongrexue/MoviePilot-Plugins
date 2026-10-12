<script setup>
import { computed, onMounted, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from '../api'

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

const form = computed(() => props.config.form)

function setMessage(text, ok = true) {
  message.value = text || ''
  messageOk.value = ok
}

async function loadStatus() {
  statusLoading.value = true
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status', { timeoutMs: 15000 }))
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
  } catch {
    dialogs.value = []
  }
}

async function sendCode() {
  if (busy.value) return
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
    const result = unwrap(await postPluginApi(props.api, props.pluginId, 'telegram/send_code', { phone }))
    loginStage.value = result?.need_password ? 'need_password' : 'code_sent'
    setMessage(result?.message || '验证码已发送')
  } catch (err) {
    setMessage(err?.message || '发送验证码失败', false)
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
    }))
    if (result?.need_password) {
      loginStage.value = 'need_password'
      setMessage(result?.message || '请输入两步验证密码', false)
    } else if (result?.authorized) {
      loginStage.value = 'idle'
      code.value = ''
      password.value = ''
      setMessage('登录成功，正在拉取对话列表…')
      await loadStatus()
      await refreshDialogs()
    } else {
      setMessage(result?.message || '登录未完成', false)
    }
  } catch (err) {
    setMessage(err?.message || '登录失败', false)
  } finally {
    busy.value = ''
  }
}

async function logout() {
  if (busy.value) return
  busy.value = 'logout'
  setMessage('')
  try {
    const result = unwrap(await postPluginApi(props.api, props.pluginId, 'telegram/logout', {}))
    loginStage.value = 'idle'
    dialogs.value = []
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
  setMessage('')
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'telegram/refresh_dialogs', {}))
    dialogs.value = data?.dialogs || []
    setMessage(`对话列表已刷新，共 ${dialogs.value.length} 条`)
    await loadStatus()
  } catch (err) {
    setMessage(err?.message || '刷新对话列表失败', false)
  } finally {
    busy.value = ''
  }
}

const chips = computed(() => {
  const info = status.value || {}
  return [
    { text: info.telethon_available ? 'telethon 已安装' : 'telethon 未安装', color: info.telethon_available ? 'success' : 'error' },
    { text: info.api_configured ? 'API 凭证已填' : 'API 凭证未填', color: info.api_configured ? 'success' : 'warning' },
    { text: info.session_present ? '会话已保存' : '无会话', color: info.session_present ? 'success' : 'default' },
    { text: info.authorized ? '已登录' : '未登录', color: info.authorized ? 'success' : 'warning' },
  ]
})

onMounted(async () => {
  await loadStatus()
  await loadDialogs()
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
      <VBtn size="small" variant="text" prepend-icon="mdi-refresh" :loading="statusLoading" @click="loadStatus">
        刷新状态
      </VBtn>
    </div>

    <VAlert v-if="status?.me" type="success" variant="tonal" density="comfortable" class="tg-account">
      已登录：{{ status.me.name || status.me.username }}
      <span v-if="status.me.username">（@{{ status.me.username }}）</span>
      <span v-if="status.me.phone"> · {{ status.me.phone }}</span>
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
            <VTextField v-model="form.tg_api_id" label="API ID" density="compact" variant="outlined" hide-details />
          </VCol>
          <VCol cols="12" md="6">
            <VTextField v-model="form.tg_api_hash" label="API Hash" density="compact" variant="outlined" hide-details />
          </VCol>
          <VCol cols="12" md="6">
            <VTextField
              v-model="form.tg_phone"
              label="手机号（含国家码）"
              placeholder="+8613800000000"
              density="compact"
              variant="outlined"
              hide-details
            />
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
        <div class="tg-hint">
          API ID / Hash 需在 my.telegram.org 申请；代理自动继承 MoviePilot 的系统代理设置。
        </div>
      </VCardText>
    </VCard>

    <VCard flat class="tg-card">
      <VCardTitle class="text-subtitle-2">登录向导</VCardTitle>
      <VCardText>
        <div class="tg-wizard">
          <VBtn
            color="primary"
            variant="flat"
            :loading="busy === 'send_code'"
            prepend-icon="mdi-send-outline"
            @click="sendCode"
          >
            发送验证码
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
          已缓存 {{ dialogs.length }} 个对话。首次登录后请点一次「刷新对话列表」，
          资源监控与转发规则的频道下拉会用到它。
        </div>
      </VCardText>
    </VCard>
  </div>
</template>

<style scoped>
.tg-pane { display: flex; flex-direction: column; gap: 12px; }
.tg-status-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.tg-status-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.tg-account,
.tg-message { font-size: 13px; }
.tg-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.tg-wizard { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tg-wizard-password { margin-top: 8px; }
.tg-wizard-input { flex: 1 1 200px; min-width: 160px; }
.tg-wizard-actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.tg-hint { margin-top: 10px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.6; }
</style>
