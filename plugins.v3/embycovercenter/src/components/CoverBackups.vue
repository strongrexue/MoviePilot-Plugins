<script setup>
import { onMounted, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from './api'

/**
 * 封面备份管理：按服务器分节列出各媒体库的备份版本，支持恢复（指定版本或最新）。
 * 备份由自动封面在覆盖上传前自动生成（每库保留最近 3 版），本组件只做展示与恢复。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const backups = ref([])
const loading = ref(false)
const error = ref('')
const message = ref('')
const messageOk = ref(false)
const restoring = ref('')
/** 待确认的恢复动作：{ item, timestamp, label }，点「恢复」前先弹确认。 */
const pending = ref(null)

function close() {
  emit('update:modelValue', false)
}

/** 恢复入口：先弹确认，防止误点把媒体库封面覆盖掉。 */
function openRestore(item, timestamp) {
  if (restoring.value) return
  pending.value = {
    item,
    timestamp: timestamp || '',
    label: formatStamp(timestamp || (item.versions.length ? item.versions[0].timestamp : '')),
  }
}

function confirmRestore() {
  const target = pending.value
  pending.value = null
  if (target) restore(target.item, target.timestamp)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'cover_backups')) || {}
    backups.value = Array.isArray(data.backups) ? data.backups : []
  } catch (err) {
    error.value = err?.message || '读取备份列表失败'
    backups.value = []
  } finally {
    loading.value = false
  }
}

async function restore(item, timestamp) {
  const key = `${item.server}/${item.library_id}/${timestamp || 'latest'}`
  if (restoring.value) return
  restoring.value = key
  message.value = ''
  try {
    const data =
      unwrap(await postPluginApi(props.api, props.pluginId, 'cover_backup/restore', {
        server: item.server,
        library_id: item.library_id,
        timestamp: timestamp || '',
      })) || {}
    message.value = data.message || '封面已从备份恢复'
    messageOk.value = true
  } catch (err) {
    message.value = err?.message || '恢复失败'
    messageOk.value = false
  } finally {
    restoring.value = ''
  }
}

function formatSize(size) {
  const kb = Number(size || 0) / 1024
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`
}

function formatStamp(stamp) {
  const raw = String(stamp || '')
  if (raw.length !== 15) return raw
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)} ${raw.slice(9, 11)}:${raw.slice(11, 13)}:${raw.slice(13, 15)}`
}

onMounted(load)
</script>

<template>
  <VDialog
    :model-value="props.modelValue"
    max-width="640"
    scrollable
    @update:model-value="value => emit('update:modelValue', value)"
  >
    <VCard class="ec-bk">
      <VCardItem class="py-3">
        <VCardTitle class="text-subtitle-1">封面备份管理</VCardTitle>
        <VCardSubtitle class="text-caption">自动封面覆盖上传前自动保存原版封面，每库保留最近 3 版</VCardSubtitle>
        <template #append>
          <VBtn icon="mdi-refresh" size="small" variant="text" :loading="loading" @click="load" />
          <VBtn icon="mdi-close" size="small" variant="text" @click="close" />
        </template>
      </VCardItem>
      <VDivider />
      <VCardText class="ec-bk-body">
        <VAlert v-if="error" type="warning" variant="tonal" density="compact" class="mb-2">{{ error }}</VAlert>
        <VAlert v-if="message" :type="messageOk ? 'success' : 'error'" variant="tonal" density="compact" class="mb-2">
          {{ message }}
        </VAlert>
        <div v-if="!loading && !backups.length" class="text-caption text-medium-emphasis py-4 text-center">
          暂无备份。开启自动封面并执行一轮任务后，原版封面会自动存到这里。
        </div>
        <div v-for="item in backups" :key="`${item.server}/${item.library_id}`" class="ec-bk-lib mb-3">
          <div class="d-flex align-center mb-1">
            <VIcon icon="mdi-folder-outline" size="16" class="mr-1 text-medium-emphasis" />
            <span class="text-subtitle-2">{{ item.server }} · {{ item.library_name }}</span>
          </div>
          <div class="ec-bk-versions">
            <VChip
              v-for="version in item.versions"
              :key="version.filename"
              size="small"
              variant="tonal"
              color="primary"
              class="ma-1"
              :disabled="!!restoring"
              @click="openRestore(item, version.timestamp)"
            >
              <VProgressCircular v-if="restoring === `${item.server}/${item.library_id}/${version.timestamp}`" size="12" width="2" indeterminate class="mr-1" />
              {{ formatStamp(version.timestamp) }} · {{ formatSize(version.size) }}
            </VChip>
            <VChip
              v-if="item.versions.length > 1"
              size="small"
              variant="outlined"
              class="ma-1"
              :disabled="!!restoring"
              @click="openRestore(item, item.versions[0].timestamp)"
            >
              恢复最新
            </VChip>
          </div>
        </div>
      </VCardText>
    </VCard>

    <VDialog
      :model-value="!!pending"
      max-width="400"
      persistent
      @update:model-value="value => { if (!value) pending = null }"
    >
      <VCard v-if="pending">
        <VCardItem class="py-3">
          <VCardTitle class="text-subtitle-1">恢复封面</VCardTitle>
        </VCardItem>
        <VCardText class="text-body-2">
          将把「{{ pending.item.server }} · {{ pending.item.library_name }}」的封面恢复为
          {{ pending.label }} 的备份，会覆盖 Emby 里的当前封面。确定恢复吗？
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" :disabled="!!restoring" @click="pending = null">取消</VBtn>
          <VBtn color="primary" variant="flat" :loading="!!restoring" @click="confirmRestore">恢复</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VDialog>
</template>

<style>
/* 非 scoped：联邦构建会剥离 scoped 块；ec-bk 命名空间避免污染宿主。 */
.ec-bk .ec-bk-body {
  max-height: 55vh;
}
.ec-bk .ec-bk-lib {
  border: 1px solid rgba(var(--v-theme-primary), 0.14);
  border-radius: 10px;
  padding: 8px 10px;
  background: rgba(var(--v-theme-primary), 0.04);
}
.ec-bk .ec-bk-versions .v-chip {
  cursor: pointer;
}
.ec-bk .ec-bk-versions .v-chip:hover {
  filter: brightness(1.06);
}
</style>
