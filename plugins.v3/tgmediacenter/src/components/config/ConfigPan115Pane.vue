<script setup>
import { computed, onMounted, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from '../api'
import SecretField from './SecretField.vue'

/**
 * ② 115 网盘面板。
 *
 * 结构对齐 MA 的「115 网盘」设置：账号与授权 / 任务设置；
 * 差异是登录方式——v1 采用**手动 Cookie**（设计文档决策），不做扫码登录。
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
  if (!info.cookie_configured) return '未配置 Cookie'
  if (!info.authorized) return 'Cookie 已填写，尚未验证（点「测试连接」）'
  return info.account ? `当前登录账号：${info.account}` : '已连接'
})

const spaceLine = computed(() => {
  const space = status.value?.space || {}
  if (!space.total) return '空间：未知'
  return `空间：${space.used || '?'} / ${space.total}`
})

const offlineLine = computed(() => {
  const offline = status.value?.offline || {}
  return `离线配额：${offline.text || '未检测'}`
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
    form.value.pan115_cookie = ''
    setMessage('已清除 115 Cookie 与状态缓存')
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

onMounted(loadStatus)
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
          <span class="p115-sep">|</span>
          <span>{{ offlineLine }}</span>
          <span v-if="status?.last_check" class="p115-updated">检测于 {{ status.last_check }}</span>
        </div>

        <VRow dense class="mt-2">
          <VCol cols="12">
            <SecretField
              v-model="form.pan115_cookie"
              label="115 Cookie"
              placeholder="UID=...; CID=...; SEID=...; KID=..."
            />
          </VCol>
        </VRow>

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
            清除 Cookie
          </VBtn>
          <VSpacer />
          <VBtn size="small" variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="loadStatus">
            刷新状态
          </VBtn>
        </div>

        <div class="p115-hint">
          登录态用<strong>手动 Cookie</strong>（v1 不做扫码登录）：浏览器登录 115 后按 F12 →
          Application/Network → 复制请求头里的 Cookie 整条（需含 <code>UID</code> 与 <code>CID</code>）粘贴到上方并保存。
          Cookie 会过期，失效后重测会提示。
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
          单批上限用于分批提交，避免一次提交过多被 115 拒绝；CMS 联动属二期能力，本版本不提供。
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
