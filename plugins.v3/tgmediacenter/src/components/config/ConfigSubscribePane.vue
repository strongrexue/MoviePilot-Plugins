<script setup>
import { computed, onMounted, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from '../api'

/**
 * ③ 订阅服务面板：MP 榜单（走 MP API）/ 豆瓣榜单（走 RSSHub）双 Tab。
 *
 * 两个 Tab 共用一个订阅源引擎：勾选订阅源 → 立即抓取 → 建宿主订阅。
 * 每个 Tab 各有「立即抓取」按钮 + 「最近抓取结果」列表；
 * 顶部总览卡片显示两类订阅源数量。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  config: { type: Object, required: true },
})

const form = computed(() => props.config.form)

const loading = ref(false)
const busy = ref('')
const message = ref('')
const messageOk = ref(true)
const activeTab = ref('mp')
const status = ref(null)

// 订阅源常量表（来自 /subscribe/sources），按通道分组
const allSources = ref([])
const mpSources = computed(() => allSources.value.filter((s) => s.channel === 'mp'))
const doubanSources = computed(() => allSources.value.filter((s) => s.channel === 'douban'))

// 总览计数：显示表单实时勾选数（勾选立即反映，无需先保存）
const mpCount = computed(() => countEnabled('mp'))
const doubanCount = computed(() => countEnabled('douban'))

function countEnabled(channel) {
  return (form.value.subscribe_sources || []).filter((s) => s.enabled && s.channel === channel).length
}

// 用户勾选的订阅源（config.subscribe_sources），key → 配置项
const selectedMap = computed(() => {
  const map = {}
  for (const item of form.value.subscribe_sources || []) {
    if (item && item.key) map[item.key] = item
  }
  return map
})

function isEnabled(sourceKey) {
  return Boolean(selectedMap.value[sourceKey]?.enabled)
}

function minRatingOf(sourceKey) {
  return Number(selectedMap.value[sourceKey]?.min_rating || 0)
}

function setMessage(text, ok = true) {
  message.value = text || ''
  messageOk.value = ok
}

async function loadSources() {
  loading.value = true
  try {
    allSources.value = unwrap(await getPluginApi(props.api, props.pluginId, 'subscribe/sources', { timeoutMs: 15000 }))
  } catch (err) {
    setMessage(err?.message || '读取订阅源列表失败', false)
  } finally {
    loading.value = false
  }
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'subscribe/status', { timeoutMs: 15000 }))
  } catch (err) {
    // 状态读取失败不阻塞勾选
  }
}

// 勾选/取消一个订阅源：写回 form.subscribe_sources
function toggleSource(source) {
  const list = form.value.subscribe_sources || []
  const idx = list.findIndex((item) => item.key === source.key)
  if (idx >= 0) {
    list[idx] = { ...list[idx], enabled: !list[idx].enabled }
  } else {
    list.push({ key: source.key, channel: source.channel, enabled: true, min_rating: 0, media_type: 'all' })
  }
  // 触发响应式更新
  form.value.subscribe_sources = [...list]
}

function setMinRating(sourceKey, value) {
  const list = form.value.subscribe_sources || []
  const idx = list.findIndex((item) => item.key === sourceKey)
  if (idx >= 0) {
    list[idx] = { ...list[idx], min_rating: Number(value) || 0 }
    form.value.subscribe_sources = [...list]
  }
}

async function sync(channel, dryRun) {
  if (busy.value) return
  busy.value = `${channel}-${dryRun ? 'parse' : 'sync'}`
  setMessage(dryRun ? '正在解析订阅源…' : '正在同步订阅源（可能耗时）…')
  try {
    const data = unwrap(await postPluginApi(props.api, props.pluginId, 'subscribe/sync', {
      channel,
      dry_run: Boolean(dryRun),
    }, { timeoutMs: 58000 }))
    // sync 接口返回的就是本次结果（含 results），实时写进 last_result 供下方列表展示
    status.value = { ...(status.value || {}), last_result: data }
    setMessage(data?.message || '同步完成', !(data?.failed > 0))
  } catch (err) {
    setMessage(err?.message || '同步失败', false)
  } finally {
    busy.value = ''
  }
}

onMounted(async () => {
  await loadSources()
  await loadStatus()
})
</script>

<template>
  <div class="sub-pane">
    <!-- 总览卡片 -->
    <VCard flat class="sub-card">
      <VCardItem>
        <template #prepend>
          <VSwitch v-model="form.subscribe_enabled" color="primary" hide-details inset />
        </template>
        <VCardTitle class="text-subtitle-2">启用订阅服务</VCardTitle>
        <VCardSubtitle class="text-caption">
          MP 榜单 {{ mpCount }} 个 · 豆瓣榜单 {{ doubanCount }} 个（勾选后请点右下「保存配置」生效）
        </VCardSubtitle>
      </VCardItem>
    </VCard>

    <VAlert
      v-if="message"
      :type="messageOk ? 'info' : 'warning'"
      variant="tonal"
      density="comfortable"
      class="sub-message"
    >{{ message }}</VAlert>

    <!-- 双 Tab -->
    <VTabs v-model="activeTab" grow density="comfortable">
      <VTab value="mp" prepend-icon="mdi-server-network">MP 榜单</VTab>
      <VTab value="douban" prepend-icon="mdi-rss">豆瓣榜单</VTab>
    </VTabs>

    <!-- MP 榜单 Tab -->
    <VWindow v-model="activeTab">
      <VWindowItem value="mp">
        <VCard flat class="sub-card">
          <VCardText>
            <VProgressLinear v-if="loading" indeterminate color="primary" height="2" class="mb-2" />
            <VList density="comfortable" class="sub-list">
              <VListItem v-for="source in mpSources" :key="source.key">
                <template #prepend>
                  <VCheckbox
                    :model-value="isEnabled(source.key)"
                    color="primary"
                    hide-details
                    @update:model-value="toggleSource(source)"
                  />
                </template>
                <VListItemTitle class="text-body-2">{{ source.name }}</VListItemTitle>
                <VListItemSubtitle class="text-caption">走宿主 API · 无需配置</VListItemSubtitle>
                <template #append>
                  <VTextField
                    v-if="isEnabled(source.key)"
                    :model-value="minRatingOf(source.key)"
                    type="number"
                    density="compact"
                    variant="outlined"
                    hide-details
                    label="评分≥"
                    style="width: 90px"
                    min="0"
                    max="10"
                    step="0.5"
                    @update:model-value="(v) => setMinRating(source.key, v)"
                  />
                </template>
              </VListItem>
            </VList>
            <div class="sub-actions">
              <VBtn
                variant="tonal"
                :loading="busy === 'mp-parse'"
                :disabled="Boolean(busy) && busy !== 'mp-parse'"
                prepend-icon="mdi-text-search"
                @click="sync('mp', true)"
              >
                解析测试
              </VBtn>
              <VBtn
                color="primary"
                variant="flat"
                :loading="busy === 'mp-sync'"
                :disabled="Boolean(busy) && busy !== 'mp-sync'"
                prepend-icon="mdi-cloud-download-outline"
                @click="sync('mp', false)"
              >
                立即抓取
              </VBtn>
            </div>
            <div class="sub-hint">MP 榜单直接用 MoviePilot 的 TMDB / Bangumi 能力，无需填写任何地址。</div>
          </VCardText>
        </VCard>
      </VWindowItem>

      <!-- 豆瓣榜单 Tab -->
      <VWindowItem value="douban">
        <VCard flat class="sub-card">
          <VCardText>
            <VTextField
              v-model="form.subscribe_rsshub_base"
              label="RSSHub 地址"
              density="compact"
              variant="outlined"
              hide-details
              placeholder="https://rsshub.app"
              class="mb-2"
            />
            <VProgressLinear v-if="loading" indeterminate color="primary" height="2" class="mb-2" />
            <VList density="comfortable" class="sub-list">
              <VListItem v-for="source in doubanSources" :key="source.key">
                <template #prepend>
                  <VCheckbox
                    :model-value="isEnabled(source.key)"
                    color="primary"
                    hide-details
                    @update:model-value="toggleSource(source)"
                  />
                </template>
                <VListItemTitle class="text-body-2">{{ source.name }}</VListItemTitle>
                <VListItemSubtitle class="text-caption">/douban/{{ source.path }}</VListItemSubtitle>
                <template #append>
                  <VTextField
                    v-if="isEnabled(source.key)"
                    :model-value="minRatingOf(source.key)"
                    type="number"
                    density="compact"
                    variant="outlined"
                    hide-details
                    label="评分≥"
                    style="width: 90px"
                    min="0"
                    max="10"
                    step="0.5"
                    @update:model-value="(v) => setMinRating(source.key, v)"
                  />
                </template>
              </VListItem>
            </VList>
            <div class="sub-actions">
              <VBtn
                variant="tonal"
                :loading="busy === 'douban-parse'"
                :disabled="Boolean(busy) && busy !== 'douban-parse'"
                prepend-icon="mdi-text-search"
                @click="sync('douban', true)"
              >
                解析测试
              </VBtn>
              <VBtn
                color="primary"
                variant="flat"
                :loading="busy === 'douban-sync'"
                :disabled="Boolean(busy) && busy !== 'douban-sync'"
                prepend-icon="mdi-cloud-download-outline"
                @click="sync('douban', false)"
              >
                立即抓取
              </VBtn>
            </div>
            <div class="sub-hint">
              豆瓣榜单通过 RSSHub 获取，可在上方换成自建实例；解析测试不需要建订阅，可先确认解析正常。
            </div>
          </VCardText>
        </VCard>
      </VWindowItem>
    </VWindow>

    <!-- 最近抓取结果 -->
    <VCard flat class="sub-card">
      <VCardTitle class="text-subtitle-2">最近抓取结果</VCardTitle>
      <VCardText>
        <div v-if="status?.last_result" class="sub-result-head">
          {{ status.last_result.message || '' }}
          <span class="text-caption">
            命中 {{ status.last_result.hit }} · 新建 {{ status.last_result.created }} · 跳过 {{ status.last_result.skipped }}
          </span>
        </div>
        <div v-else class="sub-hint">尚未抓取过，点上方「立即抓取」或「解析测试」查看结果。</div>
        <VList v-if="status?.last_result?.results?.length" density="compact" class="sub-result-list">
          <VListItem v-for="(item, index) in status.last_result.results" :key="index">
            <template #prepend>
              <VIcon :icon="item.ok ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline'" size="18"
                     :color="item.ok ? 'success' : 'warning'" />
            </template>
            <VListItemTitle class="text-body-2">{{ item.title }}</VListItemTitle>
            <VListItemSubtitle class="text-caption">{{ item.message }}</VListItemSubtitle>
          </VListItem>
        </VList>
      </VCardText>
    </VCard>
  </div>
</template>

<style scoped>
.sub-pane { display: flex; flex-direction: column; gap: 12px; }
.sub-card { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 12px; }
.sub-message { font-size: 13px; }
.sub-list { max-height: 360px; overflow-y: auto; }
.sub-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
.sub-hint { margin-top: 10px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); line-height: 1.7; }
.sub-result-head { font-size: 13px; margin-bottom: 6px; display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.sub-result-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
</style>
