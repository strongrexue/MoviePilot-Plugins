<script setup>
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
import { computed, onMounted, ref } from 'vue'
import { FRONTEND_VERSION } from './version'
import { defaultConfig } from './configDefaults'
import {
  getPluginApi,
  getPluginConfig,
  postPluginApi,
  savePluginConfig,
  unwrap,
} from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'SubscribeCenter' },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close'])

const form = ref(defaultConfig())
const loading = ref(false)
const busy = ref('')
const status = ref(null)
const tip = ref({ show: false, ok: true, text: '' })

/** 后端版本号；与前端不一致时提示硬刷新。 */
const backendVersion = computed(() => String(status.value?.plugin_version || ''))
const versionMismatch = computed(() => {
  if (!backendVersion.value) return ''
  return backendVersion.value === FRONTEND_VERSION
    ? ''
    : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backendVersion.value}`
})

/** 已实现的数据源（其余源在当前版本会在日志里明确跳过）。 */
const IMPLEMENTED = ['tmdb']

const sourceRows = [
  { key: 'enable_tmdb', label: 'TMDB', hint: '核心定档源，自带 TMDB ID（当前唯一已实现）' },
  { key: 'enable_bangumi', label: 'Bangumi', hint: '日番 / 中文元数据（尚未实现）' },
  { key: 'enable_douban_rss', label: '豆瓣 RSS', hint: '需自建 RSSHub（尚未实现）' },
  { key: 'enable_simkl', label: 'Simkl Calendar', hint: '未来 33 天 TV + 动画 + 电影（尚未实现）' },
  { key: 'enable_justwatch', label: 'JustWatch', hint: '溪流媒体上线发现，只记日志（尚未实现）' },
]

function setTip(text, ok = true) {
  tip.value = { show: true, ok, text }
}

function mergeConfig(value) {
  const base = defaultConfig()
  if (value && typeof value === 'object') {
    for (const key of Object.keys(base)) {
      if (value[key] !== undefined && value[key] !== null) base[key] = value[key]
    }
  }
  return base
}

function buildPayload() {
  // 只提交 default_config 里声明过的键，避免把宿主的其它数据带回去
  const payload = {}
  for (const key of Object.keys(defaultConfig())) payload[key] = form.value[key]
  return payload
}

function cronValid() {
  return String(form.value.cron || '').trim().split(/\s+/).length === 5
}

async function loadConfig() {
  loading.value = true
  try {
    const value = await getPluginConfig(props.api, props.pluginId)
    form.value = mergeConfig(value && Object.keys(value).length ? value : props.initialConfig)
  } catch (error) {
    form.value = mergeConfig(props.initialConfig)
    setTip(error?.message || '配置读取失败', false)
  } finally {
    loading.value = false
  }
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status'))
  } catch (error) {
    // 状态失败不影响保存配置，只在控制台留痕
    console.warn('[SubscribeCenter] 状态读取失败：', error?.message || error)
  }
}

async function save() {
  if (busy.value) return
  if (!cronValid()) {
    setTip('cron 必须是 5 段式（分 时 日 月 周），例如 0 3 * * *', false)
    return
  }
  busy.value = 'save'
  try {
    const payload = buildPayload()
    // 两条路都走：宿主编排 + 自持保存
    emit('save', payload)
    await savePluginConfig(props.api, props.pluginId, payload)
    setTip('设置已保存')
    await loadStatus()
  } catch (error) {
    setTip(error?.message || '保存失败', false)
  } finally {
    busy.value = ''
  }
}

async function runOnce() {
  if (busy.value) return
  busy.value = 'run'
  try {
    const result = unwrap(
      await postPluginApi(props.api, props.pluginId, 'run_once', {}, { timeoutMs: 600000 }),
    )
    if (result?.skipped) {
      setTip('已有发现任务正在运行，本次跳过')
    } else {
      const s = result?.summary || {}
      setTip(
        `本次完成：拉取 ${s.fetched ?? 0} 条 / 新增 ${s.added ?? 0} 条 / `
          + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`
          + (s.dry_run ? '（dry-run，未写入）' : ''),
      )
    }
    await loadStatus()
  } catch (error) {
    setTip(error?.message || '运行失败', false)
  } finally {
    busy.value = ''
  }
}

onMounted(() => {
  loadConfig()
  loadStatus()
})
</script>

<template>
  <div class="sc-root">
    <VAlert
      v-if="versionMismatch"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-3"
      :text="`${versionMismatch}：浏览器仍在用缓存的旧联邦组件。请按 Ctrl+Shift+R 硬刷新页面后再操作。`"
    />

    <VAlert
      v-if="tip.show"
      :type="tip.ok ? 'success' : 'error'"
      variant="tonal"
      density="compact"
      class="mb-3"
      :text="tip.text"
    />

    <VCard variant="tonal" class="mb-3">
      <VCardTitle class="d-flex align-center flex-wrap ga-2">
        <span>胖虎订阅中心</span>
        <VChip size="small" variant="flat" color="primary">v{{ FRONTEND_VERSION }}</VChip>
        <VChip
          v-if="status"
          size="small"
          variant="tonal"
          :color="status.enabled ? 'success' : 'default'"
        >
          {{ status.enabled ? '已启用' : '未启用' }}
        </VChip>
        <VChip v-if="status" size="small" variant="tonal">
          今日写入 {{ status.written_today }} / {{ status.daily_limit }}
        </VChip>
        <VChip
          v-if="status && !status.first_run_completed"
          size="small"
          variant="tonal"
          color="warning"
        >
          首次运行将强制 dry-run
        </VChip>
      </VCardTitle>
      <VCardText class="sc-hint">
        只做三件事：发现 → 去重 → 写订阅。版本控制、洗版与下载优先级由 MoviePilot
        后台订阅规则接管，本插件不介入。
      </VCardText>
    </VCard>

    <VCard variant="outlined" class="mb-3">
      <VCardTitle class="text-subtitle-1">基础</VCardTitle>
      <VCardText>
        <VSwitch v-model="form.enabled" label="启用插件" density="compact" hide-details class="mb-2" />
        <VSwitch
          v-model="form.discovery_page_enabled"
          label="在「发现」分区显示入口"
          density="compact"
          hide-details
          :disabled="!form.enabled"
          class="mb-2"
        />
        <VSwitch
          v-model="form.dry_run"
          label="dry-run（只记录不写入）"
          density="compact"
          hide-details
          class="mb-2"
        />
        <VSwitch v-model="form.notify" label="发送运行摘要通知" density="compact" hide-details />
        <VSwitch
          v-model="form.reset_daily_counter"
          label="清零今日写入计数（测试用，保存后自动关闭）"
          density="compact"
          hide-details
          color="warning"
          class="mt-2"
        />
        <div class="sc-hint mt-1">
          勾选并保存后，本次会把「今日已写入 N 条」清零，方便同一天反复测。
          <b>这是测试开关</b>，目标达成后会评估是否保留；保存即自动置回关闭，
          不会让每日上限永久失效。
        </div>
        <div class="sc-hint mt-2">
          首次运行无论此开关如何都会强制 dry-run 一次，确认结果后再按本开关执行。
        </div>
      </VCardText>
    </VCard>

    <VCard variant="outlined" class="mb-3">
      <VCardTitle class="text-subtitle-1">数据源</VCardTitle>
      <VCardText>
        <div v-for="row in sourceRows" :key="row.key" class="mb-2">
          <VSwitch v-model="form[row.key]" :label="row.label" density="compact" hide-details />
          <div class="sc-hint ml-10">
            {{ row.hint }}
            <span v-if="!IMPLEMENTED.includes(row.key.replace('enable_', ''))" class="sc-warn">
              （当前版本已启用也不会运行）
            </span>
          </div>
        </div>
      </VCardText>
    </VCard>

    <VCard variant="outlined" class="mb-3">
      <VCardTitle class="text-subtitle-1">发现窗口与阈值</VCardTitle>
      <VCardText>
        <VRow dense>
          <VCol cols="12" sm="6">
            <VTextField
              v-model.number="form.tmdb_future_days"
              label="TMDB 发现窗口（天）"
              type="number"
              min="1"
              max="90"
              density="compact"
              hide-details
              class="mb-2"
            />
          </VCol>
          <VCol cols="12" sm="6">
            <VTextField
              v-model.number="form.min_rating_tmdb"
              label="TMDB 最低评分"
              type="number"
              step="0.1"
              min="0"
              max="10"
              density="compact"
              hide-details
              class="mb-2"
            />
          </VCol>
          <VCol cols="12" sm="6">
            <VTextField
              v-model.number="form.min_popularity"
              label="最低关注度（popularity）"
              type="number"
              step="1"
              min="0"
              density="compact"
              hide-details
              class="mb-2"
            />
          </VCol>
        </VRow>
        <div class="sc-hint">
          TMDB 只保留「今天 ~ 今天 + N 天」内的定档条目。注意宿主 discover 不支持按地区过滤，
          结果会偏欧美。
        </div>
        <div class="sc-hint mt-1">
          <b>最低关注度</b>：新片还没人评分，popularity 是唯一可用的质量信号。
          设 0 表示不过滤，会把同日上映的冷门片也订进来（观众级大片 100+、
          院线片 10~50、冷门片 &lt;5）。</div>
      </VCardText>
    </VCard>

    <VCard variant="outlined" class="mb-3">
      <VCardTitle class="text-subtitle-1">写入与调度</VCardTitle>
      <VCardText>
        <VRow dense>
          <VCol cols="12" sm="6">
            <VTextField
              v-model.number="form.daily_limit"
              label="每日写入上限"
              type="number"
              min="1"
              max="50"
              density="compact"
              hide-details
              class="mb-2"
            />
          </VCol>
          <VCol cols="12" sm="6">
            <VTextField
              v-model="form.cron"
              label="执行时间（5 段式 cron）"
              :error="!cronValid()"
              :error-messages="cronValid() ? [] : ['需要 5 段，例如 0 3 * * *']"
              density="compact"
              hide-details
              class="mb-2"
            />
          </VCol>
          <VCol cols="12" sm="6">
            <VTextField
              v-model="form.timezone"
              label="时区"
              density="compact"
              hide-details
              class="mb-2"
            />
          </VCol>
        </VRow>
        <div class="sc-hint">修改 cron 后需要重新保存配置才会重建定时任务。</div>
      </VCardText>
    </VCard>

    <div class="d-flex flex-wrap ga-2">
      <VBtn
        color="primary"
        :loading="busy === 'save'"
        :disabled="loading"
        prepend-icon="mdi-content-save"
        @click="save"
      >
        保存配置
      </VBtn>
      <VBtn
        variant="tonal"
        :loading="busy === 'run'"
        :disabled="loading"
        prepend-icon="mdi-radar"
        @click="runOnce"
      >
        立即运行一次
      </VBtn>
      <VBtn variant="text" prepend-icon="mdi-close" @click="emit('close')">关闭</VBtn>
    </div>

    <div class="sc-hint mt-3">
      「立即运行一次」会真实触发一次发现流程；首次仍会强制 dry-run，不会写入订阅。
    </div>
  </div>
</template>

<style scoped>
.sc-root {
  padding: 4px;
}
.sc-hint {
  font-size: 12px;
  line-height: 1.5;
  opacity: 0.7;
}
.sc-warn {
  color: rgb(var(--v-theme-warning));
}
</style>
