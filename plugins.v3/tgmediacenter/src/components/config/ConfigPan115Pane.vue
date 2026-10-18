<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from '../api'

/**
 * ② 115 网盘面板。
 *
 * 结构对齐 MA 的「115 网盘」设置：账号与授权 / 任务设置。
 * 登录方式只保留**扫码登录**（App 通道，不触发安全密钥）；
 * Cookie 由扫码换取后保存在插件数据内部；界面用遮罩长条按需展示
 * （默认遮罩，点眼睛/复制时才向后端拉取明文），不会被「保存配置」清空。
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
    ckReset()
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
      ckReset()
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

// ------------------------------------------------------------------ Cookie 遮罩长条
const CK_MASKED = 'UID=••••••••; CID=••••••••; SEID=•••••••• …'
const ckRevealed = ref(false)
const ckBusy = ref(false)
const ckValue = ref('')
const ckToast = ref('')
let ckToastTimer = null

const ckText = computed(() => (ckRevealed.value ? ckValue.value || CK_MASKED : CK_MASKED))

function ckReset() {
  ckRevealed.value = false
  ckValue.value = ''
}

async function ckEnsure() {
  // 明文只在首次点眼睛/复制时向后端拉取，之后仅驻留内存
  if (ckValue.value) return ckValue.value
  ckBusy.value = true
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'pan115/cookie_reveal', {}, { timeoutMs: 15000 }))
    ckValue.value = String(data?.cookie || '')
    return ckValue.value
  } catch (err) {
    setMessage(err?.message || '获取 Cookie 失败', false)
    return ''
  } finally {
    ckBusy.value = false
  }
}

async function ckToggle() {
  if (!ckRevealed.value) {
    const value = await ckEnsure()
    if (!value) return
  }
  ckRevealed.value = !ckRevealed.value
}

async function ckCopy() {
  const value = await ckEnsure()
  if (!value) return
  try {
    await navigator.clipboard.writeText(value)
    ckToast.value = '已复制完整 Cookie'
  } catch {
    ckToast.value = '复制失败：浏览器不允许访问剪贴板'
  }
  if (ckToastTimer) window.clearTimeout(ckToastTimer)
  ckToastTimer = window.setTimeout(() => { ckToast.value = '' }, 1800)
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
      <VCardText class="p115-body">
        <div class="p115-status">
          <span class="p115-account">{{ accountLine }}</span>
          <span class="p115-sep">|</span>
          <span>{{ spaceLine }}</span>
          <span v-if="status?.last_check" class="p115-updated">检测于 {{ status.last_check }}</span>
        </div>

        <!-- 当前登录 Cookie：默认遮罩，点眼睛/复制时才向后端拉取明文 -->
        <div v-if="status?.cookie_configured" class="p115-ck" :class="{ 'p115-ck--open': ckRevealed }">
          <VIcon size="16" class="p115-ck-ico">mdi-key-variant</VIcon>
          <span v-if="status?.login_device" class="p115-ck-chip">{{ status.login_device }}</span>
          <span class="p115-ck-val" :title="ckRevealed ? '已显示完整 Cookie' : '默认遮罩，点右侧眼睛查看'">{{ ckText }}</span>
          <VBtn
            variant="text"
            density="comfortable"
            size="small"
            :icon="ckRevealed ? 'mdi-eye-off' : 'mdi-eye'"
            :aria-pressed="ckRevealed"
            :title="ckRevealed ? '隐藏 Cookie' : '显示 Cookie'"
            :loading="ckBusy"
            class="p115-ck-eye"
            @click="ckToggle"
          />
          <VBtn
            variant="text"
            density="comfortable"
            size="small"
            icon="mdi-content-copy"
            title="复制完整 Cookie"
            @click="ckCopy"
          />
          <Transition name="p115-ck-fade">
            <span v-if="ckToast" class="p115-ck-toast">{{ ckToast }}</span>
          </Transition>
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
      </VCardText>
    </VCard>

    <VCard flat class="p115-card">
      <VCardTitle class="text-subtitle-2">任务设置</VCardTitle>
      <VCardText class="p115-body">
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
      <VCardTitle class="text-subtitle-2">通知</VCardTitle>
      <VCardText class="p115-body">
        <div class="p115-notify">
          <VSwitch v-model="form.notify_on_hit" color="primary" hide-details inset>
            <template #label><span class="p115-switch-label">转存成功后通知我</span></template>
          </VSwitch>
          <VSwitch v-model="form.notify_on_error" color="primary" hide-details inset>
            <template #label><span class="p115-switch-label">转存失败后通知我</span></template>
          </VSwitch>
          <VSwitch v-model="form.notify_on_search" color="primary" hide-details inset>
            <template #label><span class="p115-switch-label">回搜到资源后通知我</span></template>
          </VSwitch>
        </div>
        <div class="p115-hint">
          这三个开关分别管一类通知，关闭哪类就收不到哪类（都走 MoviePilot 通知渠道，
          用哪个渠道、发给谁跟宿主的「通知」设置一致）：
          <br>· <strong>转存成功</strong>：监控 / 转发命中后往 115 转存（或离线）成功，按批汇总一条（如「已转存 3 条」）；
          <br>· <strong>转存失败</strong>：汇总失败条数与原因，115 登录态失效会附上重新扫码的引导（同一故障 6 小时内只提醒一次）；
          <br>· <strong>回搜到资源</strong>：订阅回搜在缓存里找到缺失资源并推送后的结果汇总。
          <br>通用转发本身不发送通知（转发结果在「通用转发」面板的流水里看）。
        </div>
      </VCardText>
    </VCard>

    <VCard flat class="p115-card">
      <VCardTitle class="text-subtitle-2">推送测试</VCardTitle>
      <VCardText class="p115-body">
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

        <VSwitch v-model="form.interactive_push" color="primary" hide-details inset>
          <template #label><span class="p115-switch-label">允许私聊机器人发链接直接转存 115</span></template>
        </VSwitch>
        <div class="p115-hint">
          开启后，私聊 MoviePilot 机器人直接发 115 分享链接 / 磁力 / ed2k，插件会转存到 115
          并回一条回执（成功 / 失败 / 已转存过都会说清）。消息里没有链接时不会有任何回复。
          回执与其余通知一样走宿主的「通知」渠道。
        </div>

        <VSwitch v-model="form.interactive_dedup" color="primary" hide-details inset>
          <template #label><span class="p115-switch-label">私聊转存查重（已转存过的链接不重复转存）</span></template>
        </VSwitch>
        <div class="p115-hint">
          开启后，插件会记住所有已成功转存的链接（含监控 / 回搜转存的）：私聊再发同一条
          链接时直接回「已转存过，本次未重复保存」，不再往 115 里重复存一份
          （115 的分享转存本身不查重，同一分享会落盘多份）。关闭后每次都会实际转存。
        </div>
      </VCardText>
    </VCard>
  </div>
</template>

<style scoped>
/* 分区根容器：卡片之间统一 8px */
.p115-pane { display: flex; flex-direction: column; gap: 8px; }
/* 分区卡的外观与内边距：有底色 + 1px 描边的 10px 圆角块（对齐效果图的分区语言，不再与对话框同底）。
   Vuetify 的 flat 卡片会把背景重置成 surface，故用 !important 压过它；
   描边用 on-surface 的显式 alpha，避免主题变量缺失时整条 border 声明失效（计算值 0px） */
.p115-card {
  background: rgba(var(--v-theme-on-surface), 0.04) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.10) !important;
  border-radius: 10px;
}
/* 内边距统一压到 10/12（压过 Vuetify 直系子元素的 16/24）；标题区与正文区相邻处只留一份，
   模板里不再用 pt-0 之类的工具类叠加 */
.p115-card > .v-card-item { padding: 10px 12px; }
.p115-card > .v-card-title { padding: 10px 12px; }
.p115-card > .v-card-text { padding: 10px 12px; }
.p115-card > .v-card-item + .v-card-text,
.p115-card > .v-card-title + .v-card-text { padding-top: 0; }
/* 卡片正文：纵向堆叠统一 8px（上下内边距由上面的 .p115-card > .v-card-text 统一控制） */
.p115-body { display: flex; flex-direction: column; gap: 8px; }
.p115-message { font-size: 13px; }
/* 同一行内横向元素统一 6px */
.p115-status { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.p115-account { color: rgb(var(--v-theme-primary)); font-weight: 500; }
.p115-sep { opacity: 0.4; }
.p115-updated { margin-left: auto; font-size: 12px; opacity: 0.6; }
.p115-actions { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
/* 登录向导盒子：内边距收紧到 10px，内部纵向堆叠 8px，与外层间距交给父级 gap */
.p115-qr { display: flex; flex-direction: column; gap: 8px; padding: 10px; border-radius: 10px; background: rgba(var(--v-theme-on-surface), 0.03); }
.p115-qr-form { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.p115-qr-app { flex: 0 0 260px; max-width: 100%; }
.p115-qr-body { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.p115-qr-img { width: 168px; height: 168px; border-radius: 8px; background: #fff; padding: 6px; }
.p115-qr-meta { display: flex; flex-direction: column; gap: 8px; min-width: 180px; }
.p115-qr-state { font-size: 14px; font-weight: 500; color: rgb(var(--v-theme-primary)); }
.p115-qr-tip { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.65); line-height: 1.5; }
/* 说明文字：12px / 1.5，与上方控件净间距 4px（父级 gap 8px，用 -4px 抵消） */
.p115-hint { margin-top: -4px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.5; }
/* 通知开关纵向堆叠，间距与其它区块一致 8px */
.p115-notify { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.p115-switch-label { font-size: 13px; }
.p115-hint code {
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  font-size: 11px;
}
/* 推送结果：标题与列表纵向 8px */
.p115-result { display: flex; flex-direction: column; gap: 8px; }
.p115-result-head { font-size: 13px; }
.p115-result-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.p115-result-name { font-size: 13px; }
.p115-result-msg { font-size: 12px; opacity: 0.75; }
/* 当前登录 Cookie 遮罩长条：默认遮罩，明文态主题色描边提示 */
.p115-ck {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 5px 5px 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  transition: border-color 0.15s ease;
}
.p115-ck--open { border-color: rgba(var(--v-theme-primary), 0.55); }
.p115-ck-ico { flex: none; color: rgba(var(--v-theme-on-surface), 0.55); }
.p115-ck-chip {
  flex: none;
  padding: 1px 10px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 999px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.65);
  white-space: nowrap;
}
.p115-ck-val {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, 'JetBrains Mono', Menlo, Consolas, monospace;
  font-size: 12.5px;
  letter-spacing: 0.2px;
}
.p115-ck .v-btn { flex: none; }
.p115-ck--open .p115-ck-eye { color: rgb(var(--v-theme-primary)); }
.p115-ck-toast {
  position: absolute;
  right: 6px;
  bottom: calc(100% + 4px);
  padding: 2px 10px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 999px;
  background: rgba(var(--v-theme-surface), 0.96);
  font-size: 12px;
  color: rgb(var(--v-theme-primary));
  white-space: nowrap;
  z-index: 2;
}
.p115-ck-fade-enter-active, .p115-ck-fade-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.p115-ck-fade-enter-from, .p115-ck-fade-leave-to { opacity: 0; transform: translateY(4px); }
@media (max-width: 560px) {
  .p115-ck-chip { display: none; }
}
</style>
