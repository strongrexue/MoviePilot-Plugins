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
const previewItems = ref([])

/** 决策常量 -> 中文标签（与后端 core/constants.py 逐字对应）。 */
const DECISION_LABELS = {
  added: '新增',
  skipped_dry_run: 'dry-run',
  pending_review: '待确认',
  skipped_special: '特别篇',
  skipped_finished: '已播完',
  skipped_rating: '评分不足',
  skipped_popularity: '关注度不足',
  skipped_out_of_window: '超出窗口',
  skipped_not_future: '档期已过',
  skipped_duplicate: '重复',
  skipped_daily_limit: '触达上限',
  skipped_already_subscribed: '已订阅',
  skipped_already_completed: '已完成过',
}

/** 后端版本号；与前端不一致时提示硬刷新。 */
const backendVersion = computed(() => String(status.value?.plugin_version || ''))
const versionMismatch = computed(() => {
  if (!backendVersion.value) return ''
  return backendVersion.value === FRONTEND_VERSION
    ? ''
    : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backendVersion.value}`
})

/** 已实现的数据源（其余源在当前版本会在日志里明确跳过）。 */
const IMPLEMENTED = ['tmdb', 'bangumi', 'douban_rss']

/** 豆瓣 RSS 地址：后端存字符串数组，界面用多行文本编辑。 */
const doubanSourcesText = computed({
  get() {
    const value = form.value.douban_rss_sources
    return Array.isArray(value) ? value.join('\n') : String(value || '')
  },
  set(value) {
    form.value.douban_rss_sources = String(value || '')
      .split(/[\n,，]+/)
      .map((entry) => entry.trim())
      .filter(Boolean)
  },
})

const sourceRows = [
  { key: 'enable_tmdb', label: 'TMDB', hint: '全球电影/剧集，自带 TMDB ID（身份最可靠）' },
  { key: 'enable_bangumi', label: 'Bangumi', hint: '当季番剧，自带 subject ID，经宿主换算成 TMDB' },
  { key: 'enable_douban_rss', label: '豆瓣 RSS', hint: '经 RSSHub；上映日期与豆瓣 ID 均可解析' },
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

/**
 * 只读预览：跑完整流水线但**不写订阅、不消耗每日额度**。
 * 这是调参的主要工具 —— 改门槛/窗口后先预览，满意再真跑。
 */
async function preview() {
  if (busy.value) return
  busy.value = 'preview'
  previewItems.value = []
  try {
    const result = unwrap(
      await postPluginApi(props.api, props.pluginId, 'preview', {}, { timeoutMs: 600000 }),
    )
    if (result?.skipped) {
      setTip('已有发现任务正在运行，本次跳过')
      return
    }
    previewItems.value = result?.items || []
    const s = result?.summary || {}
    const reasons = Object.entries(result?.rejections || {})
      .map(([key, count]) => `${DECISION_LABELS[key] || key} ${count}`)
      .join(' · ')
    setTip(
      `预览完成（未写入）：会订 ${previewItems.value.length} 条 / 拉取 ${s.fetched ?? 0} 条`
        + (reasons ? `；被拦下：${reasons}` : ''),
    )
  } catch (error) {
    setTip(error?.message || '预览失败', false)
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
        <VRow dense class="mt-3">
          <VCol cols="12" sm="6">
            <VTextField
              v-model.number="form.bangumi_future_days"
              label="Bangumi 发现窗口（天）"
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
              v-model.number="form.min_rating_bangumi"
              label="Bangumi 最低评分"
              type="number"
              step="0.1"
              min="0"
              max="10"
              density="compact"
              hide-details
              class="mb-2"
            />
          </VCol>
        </VRow>
        <VSwitch
          v-model="form.bangumi_split_season"
          label="Bangumi 按季拆分订阅"
          density="compact"
          hide-details
          class="mt-1"
        />
        <div class="sc-hint mb-3">
          <b>默认关闭</b>，建议保持关闭。国产动画在 TMDB 通常被建模成「单季多集」
          （如《牧神记》是第 1 季 110 集，第 105 集正好对应 Bangumi「牧神记5」的开播日），
          此时 Bangumi 的「第 N 期」并不是 TMDB 的第 N 季 —— 按季订会去找一个不存在的季，
          什么都订不到。关闭后按 TMDB 默认季订阅、靠宿主的按集追踪，才是正确行为。
        </div>

        <VTextarea
          v-model="doubanSourcesText"
          label="豆瓣 RSS 地址（每行一个）"
          rows="2"
          density="compact"
          hide-details
          class="mb-2"
          :disabled="!form.enable_douban_rss"
        />
        <div class="sc-hint mb-3">
          填 RSSHub 的豆瓣路线，例如
          <code>http://192.168.50.134:1200/douban/movie/coming</code>（即将上映）。
          实测可用：<code>/douban/movie/coming</code>、<code>/douban/movie/playing</code>、
          <code>/douban/movie/weekly</code>；<code>ustop250</code> 与
          <code>/douban/movie/new</code> 在新版 RSSHub 已 404。
          条目自带上映日期与豆瓣 ID，可精确匹配 TMDB。
        </div>

        <div class="sc-hint mb-3">
          Bangumi 是<b>独立配置</b>：番剧的窗口与评分门槛跟 TMDB 分开设 ——
          两边评分量纲不同（Bangumi 社区评分普遍偏高），共用门槛会误杀。
        </div>

        <div class="sc-hint mt-1">
          <b>最低关注度</b>：新片还没人评分，popularity 是唯一可用的质量信号。
          设 0 表示不过滤，会把同日上映的冷门片也订进来（观众级大片 100+、
          院线片 10~50、冷门片 &lt;5）。</div>

        <VSwitch
          v-model="form.filter_original_language"
          label="只保留指定原始语言的条目"
          density="compact"
          hide-details
          class="mt-3"
        />
        <VTextField
          v-model="form.tmdb_original_languages"
          label="允许的原始语言（逗号分隔）"
          density="compact"
          hide-details
          :disabled="!form.filter_original_language"
          placeholder="zh,ja,ko,en"
          class="mt-2"
        />
        <div class="sc-hint mt-1">
          语种码：zh 华语 / ja 日语 / ko 韩语 / en 英语。小语种片（印度、土耳其、
          荷兰等）通常不会被下载，进订阅只会白占每日额度。
        </div>
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
        color="info"
        :loading="busy === 'preview'"
        :disabled="loading"
        prepend-icon="mdi-eye-outline"
        @click="preview"
      >
        预览（只看不订）
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
      「<b>预览</b>」跑完整流程但不写订阅、<b>不消耗每日额度</b> —— 调参时先用它看结果。
      「立即运行一次」会真实写入（首次仍强制 dry-run）。
    </div>

    <VCard v-if="previewItems.length" variant="outlined" class="mt-3">
      <VCardTitle class="text-subtitle-1 d-flex align-center flex-wrap ga-2">
        <span>预览结果</span>
        <VChip size="x-small" variant="flat" color="info">会订 {{ previewItems.length }} 条</VChip>
        <VChip size="x-small" variant="tonal">未写入、未消耗额度</VChip>
      </VCardTitle>
      <VCardText>
        <div v-for="(row, index) in previewItems" :key="index" class="sc-preview-row">
          <div class="d-flex align-center flex-wrap ga-2">
            <VChip size="x-small" variant="flat" color="info">{{ row.media_type }}</VChip>
            <b>{{ row.title }}</b>
            <span v-if="row.year" class="sc-hint">({{ row.year }})</span>
            <span v-if="row.release_date" class="sc-hint">放送 {{ row.release_date }}</span>
            <VChip v-if="row.language" size="x-small" variant="text">{{ row.language }}</VChip>
            <VChip size="x-small" variant="tonal" color="warning">
              关注度 {{ row.popularity != null ? row.popularity.toFixed(1) : '—' }}
            </VChip>
            <span v-if="row.rating != null" class="sc-hint">评分 {{ row.rating }}</span>
          </div>
        </div>
      </VCardText>
    </VCard>
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
.sc-preview-row {
  padding: 5px 0;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.08);
}
.sc-preview-row:last-child {
  border-bottom: none;
}
.sc-warn {
  color: rgb(var(--v-theme-warning));
}
</style>
