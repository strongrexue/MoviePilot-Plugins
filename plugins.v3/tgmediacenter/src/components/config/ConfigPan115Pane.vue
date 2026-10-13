<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from '../api'

/**
 * ② 115 网盘面板。
 *
 * 结构对齐 MA 的「115 网盘」设置：账号与授权 / 任务设置。
 * 登录方式只保留**扫码登录**（App 通道，不触发安全密钥）；
 * Cookie 由扫码换取后保存在插件数据内部，界面上不展示、不可粘贴。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
})

const status = ref(null)
const loading = ref(false)
const busy = ref('')
const message = ref('')
const messageOk = ref(true)
const pushText = ref('')
const pushResult = ref(null)

const form = computed(() => props.config.form)

const accountLine = computed(() => {
  const info = status.value || {}
  if (!info.cookie_configured) return '未登录（请扫码）'
  if (!info.authorized) return '已取得登录态，尚未验证（点「测试连接」）'
  const device = info.login_device ? `（登录设备：${info.login_device}）` : ''
  return `${info.account ? `当前登录账号：${info.account}` : '已连接'}${device}`
})

const spaceLine = computed(() => {
  const space = status.value?.space || {}
  if (!space.total) return '空间：未知'
  return `空间：${space.used || '?'} / ${space.total}`
})

function setMessage(text, ok = true) {
  message.value = text || ''
  messageOk.value = ok
}

async function loadStatus() {
  loading.value = true
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'pan115/status', { timeoutMs: 15000 }))
  } catch (err) {
    setMessage(err?.message || '读取 115 状态失败', false)
  } finally {
    loading.value = false
  }
}

async function check() {
  if (busy.value) return
  busy.value = 'check'
  setMessage('正在测试 115 连接…')
  try {
    const info = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/check', {}, { timeoutMs: 40000 }))
    status.value = info
    setMessage(info?.account ? `115 连接正常：${info.account}` : '115 连接正常')
  } catch (err) {
    setMessage(err?.message || '测试 115 连接失败', false)
    await loadStatus()
  } finally {
    busy.value = ''
  }
}

async function clearCookie() {
  if (busy.value) return
  busy.value = 'logout'
  try {
    const info = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/logout', {}, { timeoutMs: 20000 }))
    status.value = info
    setMessage('已清除 115 登录态')
  } catch (err) {
    setMessage(err?.message || '清除失败', false)
  } finally {
    busy.value = ''
  }
}

async function verifyDir() {
  if (busy.value) return
  busy.value = 'dir'
  setMessage('正在校验目标目录…')
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/verify_dir', {
      cid: String(form.value.pan115_target_cid || '').trim(),
    }, { timeoutMs: 30000 }))
    setMessage(data?.message || `目录可用：${data?.cid || ''}`)
  } catch (err) {
    setMessage(err?.message || '目录校验失败', false)
  } finally {
    busy.value = ''
  }
}

async function push(dryRun) {
  if (busy.value) return
  busy.value = dryRun ? 'parse' : 'push'
  setMessage(dryRun ? '正在解析链接…' : '正在推送到 115（按批次提交，可能需要一点时间）…')
  pushResult.value = null
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/push', {
      text: String(pushText.value || ''),
      cid: String(form.value.pan115_target_cid || '').trim(),
      batch_size: Number(form.value.pan115_batch_max_size) || 0,
      dry_run: Boolean(dryRun),
    }, { timeoutMs: 58000 }))
    pushResult.value = data
    setMessage(data?.message || (dryRun ? '解析完成' : '推送完成'), !(data?.failed > 0))
  } catch (err) {
    setMessage(err?.message || '推送失败', false)
  } finally {
    busy.value = ''
  }
}

// ------------------------------------------------------------------ 扫码登录
const qr = ref(null)
const qrApp = ref('alipaymini')
const qrBusy = ref(false)
let qrTimer = null

const qrApps = computed(() => status.value?.qr_apps || [])

async function qrStart() {
  if (qrBusy.value) return
  qrBusy.value = true
  setMessage('正在获取二维码…')
  try {
    const data = unwrap(await postPluginApi(
      props.api, props.pluginId, 'pan115/qr_start', { app: qrApp.value }, { timeoutMs: 30000 },
    ))
    qr.value = data
    setMessage(data?.message || '请用 115 App 扫描二维码')
    startQrPolling()
  } catch (err) {
    setMessage(err?.message || '获取二维码失败', false)
  } finally {
    qrBusy.value = false
  }
}

async function qrPollOnce() {
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/qr_poll', {}, { timeoutMs: 30000 }))
    qr.value = data
    const state = data?.status
    if (state === 'success') {
      qrStopPolling()
      if (data?.status_data) status.value = data.status_data
      setMessage(data?.message || '扫码登录成功')
      await loadStatus()
    } else if (state === 'expired' || state === 'canceled') {
      qrStopPolling()
      setMessage(data?.message || '二维码已失效，请重新获取', false)
    } else {
      setMessage(data?.status_text || '等待扫码')
    }
  } catch (err) {
    qrStopPolling()
    setMessage(err?.message || '查询扫码状态失败', false)
  }
}

function startQrPolling() {
  qrStopPolling()
  qrTimer = window.setInterval(qrPollOnce, 2000)
}

function qrStopPolling() {
  if (qrTimer) {
    window.clearInterval(qrTimer)
    qrTimer = null
  }
}

async function qrCancel() {
  qrStopPolling()
  try {
    await postPluginApi(props.api, props.pluginId, 'pan115/qr_cancel', {}, { timeoutMs: 20000 })
  } catch {
    // 取消失败不影响本地状态清理
  }
  qr.value = null
  setMessage('已取消扫码登录')
}

onMounted(async () => {
  await loadStatus()
  // 刷新页面后若仍有进行中的扫码会话，恢复二维码并继续轮询
  const pending = status.value?.qr_pending
  if (pending?.image) {
    qr.value = {
      app: pending.app,
      image: pending.image,
      status: 'waiting',
      status_text: '等待扫码',
      message: '继续等待扫码…',
      expires_in: pending.expires_in,
    }
    startQrPolling()
  }
})

onUnmounted(qrStopPolling)
</script>

<template>
  <div class="p115-pane">
    <VCard flat class="p115-card">
      <VCardItem>
        <template #prepend>
          <VSwitch v-model="form.pan115_enabled" color="primary" hide-details inset />
        </template>
        <VCardTitle class="text-subtitle-2">启用 115 网盘作为推送目标</VCardTitle>
        <VCardSubtitle class="text-caption">
          资源监控 / 通用转发命中后，可把分享链接与磁力/ed2k 推送到 115（转存或离线下载）。
        </VCardSubtitle>
      </VCardItem>
    </VCard>

    <VAlert
      v-if="message"
      :type="messageOk ? 'info' : 'warning'"
      variant="tonal"
      density="comfortable"
      class="p115-message"
    >{{ message }}</VAlert>

    <VCard flat class="p115-card">
      <VCardTitle class="text-subtitle-2">账号与授权</VCardTitle>
      <VCardText>
        <div class="p115-status">
          <span class="p115-account">{{ accountLine }}</span>
          <span class="p115-sep">|</span>
          <span>{{ spaceLine }}</span>
          <span v-if="status?.last_check" class="p115-updated">检测于 {{ status.last_check }}</span>
        </div>

        <!-- 扫码登录（推荐）：App 通道不会触发 115 的「安全密钥」二次验证 -->
        <div class="p115-qr">
          <div class="p115-qr-form">
            <VSelect
              v-model="qrApp"
              :items="qrApps"
              item-title="title"
              item-value="value"
              label="登录设备"
              density="compact"
              variant="outlined"
              hide-details
              class="p115-qr-app"
              :disabled="Boolean(qr)"
            />
            <VBtn
              color="primary"
              variant="flat"
              :loading="qrBusy"
              prepend-icon="mdi-qrcode-scan"
              @click="qrStart"
            >
              {{ qr ? '重新获取二维码' : '扫码登录' }}
            </VBtn>
            <VBtn v-if="qr" variant="text" color="error" prepend-icon="mdi-close" @click="qrCancel">取消</VBtn>
          </div>

          <div v-if="qr?.image" class="p115-qr-body">
            <img :src="qr.image" alt="115 登录二维码" class="p115-qr-img" />
            <div class="p115-qr-meta">
              <div class="p115-qr-state">{{ qr.status_text || '等待扫码' }}</div>
              <div class="p115-qr-tip">用 115 App 扫描二维码，并在手机上点击确认</div>
              <div class="p115-qr-tip">会话绑定设备：{{ qr.app }}</div>
              <div v-if="qr.expires_in" class="p115-qr-tip">
                二维码有效期约 {{ Math.max(1, Math.ceil(qr.expires_in / 60)) }} 分钟
              </div>
            </div>
          </div>
        </div>

        <div class="p115-actions">
          <VBtn color="primary" variant="flat" :loading="busy === 'check'" prepend-icon="mdi-connection" @click="check">
            测试连接
          </VBtn>
          <VBtn
            variant="text"
            color="error"
            :loading="busy === 'logout'"
            prepend-icon="mdi-logout"
            @click="clearCookie"
          >
            清除登录态
          </VBtn>
          <VSpacer />
          <VBtn size="small" variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="loadStatus">
            刷新状态
          </VBtn>
        </div>

        <div class="p115-hint">
          登录只用<strong>扫码</strong>（App 通道）：115 对网页 Cookie 有设备风控，文件接口会要求「安全密钥」验证，
          扫码绑定的 App 设备不会触发该验证，所以设备列表只保留 App 端。
          扫码成功后 Cookie 自动保存在插件内部（不显示在界面上），也不会被「保存配置」清空；
          Cookie 失效时重新扫码即可。
        </div>
      </VCardText>
    </VCard>

    <VCard flat class="p115-card">
      <VCardTitle class="text-subtitle-2">任务设置</VCardTitle>
      <VCardText>
        <VRow dense>
          <VCol cols="12" md="8">
            <VTextField v-model="form.pan115_target_cid" label="转存文件夹 CID" density="compact" variant="outlined" hide-details />
          </VCol>
          <VCol cols="12" md="4" class="d-flex align-center">
            <VBtn size="small" variant="tonal" :loading="busy === 'dir'" prepend-icon="mdi-folder-check-outline" @click="verifyDir">
              校验目录
            </VBtn>
          </VCol>
          <VCol cols="12" md="4">
            <VTextField
              v-model.number="form.pan115_batch_max_size"
              type="number"
              label="单批最大链接数"
              density="compact"
              variant="outlined"
              hide-details
            />
          </VCol>
        </VRow>
        <div class="p115-hint">
          转存与离线下载都保存到该 CID（在 115 里打开目标文件夹，地址栏 <code>cid=</code> 后面就是）。
          单批上限用于分批提交，避免一次提交过多被 115 拒绝。
        </div>
      </VCardText>
    </VCard>

    <VCard flat class="p115-card">
      <VCardTitle class="text-subtitle-2">推送测试</VCardTitle>
      <VCardText>
        <VTextarea
          v-model="pushText"
          label="粘贴链接（115 分享链接 / 磁力 / ed2k，可多行多条）"
          placeholder="https://115.com/s/xxxxx?password=abcd&#10;magnet:?xt=urn:btih:...&#10;ed2k://|file|..."
          rows="3"
          density="compact"
          variant="outlined"
          hide-details
        />
        <div class="p115-actions">
          <VBtn
            variant="tonal"
            :loading="busy === 'parse'"
            :disabled="Boolean(busy) && busy !== 'parse'"
            prepend-icon="mdi-text-search"
            @click="push(true)"
          >
            解析测试（不提交）
          </VBtn>
          <VBtn
            color="success"
            variant="flat"
            :loading="busy === 'push'"
            :disabled="Boolean(busy) && busy !== 'push'"
            prepend-icon="mdi-cloud-upload-outline"
            @click="push(false)"
          >
            推送到 115
          </VBtn>
        </div>

        <div v-if="pushResult" class="p115-result">
          <div class="p115-result-head">{{ pushResult.message }}</div>
          <VList density="compact" class="p115-result-list">
            <VListItem v-for="(item, index) in pushResult.results" :key="index">
              <template #prepend>
                <VIcon :icon="item.ok ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline'" size="18"
                       :color="item.ok ? 'success' : 'warning'" />
              </template>
              <VListItemTitle class="p115-result-name">{{ item.target }}</VListItemTitle>
              <VListItemSubtitle class="p115-result-msg">{{ item.message }}</VListItemSubtitle>
            </VListItem>
          </VList>
        </div>

        <div class="p115-hint">
          解析测试不需要 Cookie，可先用它确认链接能被正确识别（含提取码）。
          实际推送需要已保存的 Cookie 与目标目录 CID。
        </div>
      </VCardText>
    </VCard>
  </div>
</template>

<style scoped>
.p115-pane { display: flex; flex-direction: column; gap: 12px; }
.p115-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.p115-message { font-size: 13px; }
.p115-status { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
.p115-account { color: rgb(var(--v-theme-primary)); font-weight: 500; }
.p115-sep { opacity: 0.4; }
.p115-updated { margin-left: auto; font-size: 12px; opacity: 0.6; }
.p115-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
.p115-qr { margin-top: 12px; padding: 12px; border-radius: 10px; background: rgba(var(--v-theme-on-surface), 0.03); }
.p115-qr-form { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.p115-qr-app { flex: 0 0 260px; max-width: 100%; }
.p115-qr-body { display: flex; gap: 16px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
.p115-qr-img { width: 168px; height: 168px; border-radius: 8px; background: #fff; padding: 6px; }
.p115-qr-meta { display: flex; flex-direction: column; gap: 6px; min-width: 180px; }
.p115-qr-state { font-size: 14px; font-weight: 500; color: rgb(var(--v-theme-primary)); }
.p115-qr-tip { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.65); line-height: 1.6; }
.p115-sub { margin-top: 14px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); }
.p115-hint { margin-top: 10px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.7; }
.p115-hint code {
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  font-size: 11px;
}
.p115-result { margin-top: 12px; }
.p115-result-head { font-size: 13px; margin-bottom: 4px; }
.p115-result-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.p115-result-name { font-size: 13px; }
.p115-result-msg { font-size: 12px; opacity: 0.75; }
</style>
