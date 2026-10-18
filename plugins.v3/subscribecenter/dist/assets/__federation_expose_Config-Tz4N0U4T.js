import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, F as FRONTEND_VERSION, g as getPluginConfig, u as unwrap, a as getPluginApi, p as postPluginApi, s as savePluginConfig } from './_plugin-vue_export-helper-Dr61UsNT.js';

/**
 * 插件默认配置（前端快照）。
 *
 * ⚠️ 键集合必须与后端 `core/constants.py` 的 `default_config()` **严格一致**。
 * 宿主 `update_config()` 是整份覆盖：任一侧多一个键或少一个键，保存配置时
 * 都会被静默清掉。`tests/v3/subscribecenter/test_subscribecenter_plugin.py`
 * 对此设了回归锁（test_default_config_key_set_matches_frontend）。
 */
const configDefaults = {
  enabled: false,
  // ---------------- 数据源开关
  enable_tmdb: true,
  enable_anilist: true,
  enable_bangumi: false,
  enable_douban_rss: false,
  // ---------------- 发现窗口与阈值
  tmdb_future_days: 3,
  bangumi_future_days: 3,
  min_rating_tmdb: 6.0,
  min_rating_bangumi: 6.0,
  min_rating_douban: 6.0,
  min_popularity: 15.0,
  // ---------------- AniList（番剧 / 国漫）
  anilist_future_days: 3,
  //: AniList 的 popularity 量纲与 TMDB 完全不同（冷门番上千、主流番 2~5 万）
  min_rating_anilist: 6.0,
  anilist_min_popularity: 1000.0,
  //: 是否包含国产动画（countryOfOrigin=CN），默认开
  anilist_include_donghua: true,
  //: Bangumi 是否按季拆分订阅（默认关：国产动画多为单季多集）
  bangumi_split_season: false,
  //: 是否只保留指定原始语言的条目
  filter_original_language: true,
  tmdb_original_languages: 'zh,ja,ko,en',
  // ---------------- 豆瓣 RSS 源列表
  // ---------------- 豆瓣 RSS 榜单（每榜独立配置）
  rsshub_domain: 'https://rsshub.ddsrem.com',
  douban_rss_sources: [
    { name: '电影即将上映', url: '/douban/movie/coming', enabled: true, max_items: 0, future_days: 30, min_want: 0 },
    { name: '剧集即将播出', url: '/douban/tv/coming', enabled: true, max_items: 0, future_days: 30, min_want: 0 },
    { name: '近期热门剧集', url: '/douban/list/tv_real_time_hotest', enabled: true, max_items: 0, future_days: 3, min_want: 0 },
    { name: '近期热门国产剧', url: '/douban/list/tv_domestic', enabled: true, max_items: 0, future_days: 3, min_want: 0 },
    { name: '近期热门综艺', url: '/douban/list/tv_variety', enabled: true, max_items: 0, future_days: 3, min_want: 0 },
    { name: '近期热门动画', url: '/douban/list/tv_animation', enabled: true, max_items: 0, future_days: 3, min_want: 0 },
    { name: '豆瓣推荐剧集', url: '/douban/recommended/tv', enabled: true, max_items: 0, future_days: 3, min_want: 0 },
    { name: '近期热门电影', url: '/douban/list/movie_real_time_hotest', enabled: false, max_items: 0, future_days: 3, min_want: 0 },
    { name: '华语口碑剧集', url: '/douban/list/tv_chinese_best_weekly', enabled: false, max_items: 0, future_days: 3, min_want: 0 },
    { name: '全球口碑剧集', url: '/douban/list/tv_global_best_weekly', enabled: false, max_items: 0, future_days: 3, min_want: 0 },
    { name: '电影口碑榜', url: '/douban/list/movie_weekly_best', enabled: false, max_items: 0, future_days: 3, min_want: 0 },
    { name: '日剧', url: '/douban/list/tv_japanese', enabled: false, max_items: 0, future_days: 3, min_want: 0 },
    { name: '韩剧', url: '/douban/list/tv_korean', enabled: false, max_items: 0, future_days: 3, min_want: 0 },
    { name: '美剧', url: '/douban/list/tv_american', enabled: false, max_items: 0, future_days: 3, min_want: 0 },
  ],
  douban_max_items_per_feed: 30,
  douban_future_days: 3,
  douban_min_want: 0,
  resolve_concurrency: 8,
  prefer_episode_group: true,
  resubscribe_completed: true,
  // ---------------- Simkl
  // ---------------- 写入
  daily_limit: 30,
  dry_run: false,
  // ---------------- 调度与通知
  cron: '0 3 * * *',
  timezone: 'Asia/Shanghai',
  notify: false,
  // ---------------- 界面
  discovery_page_enabled: false,
  // ---------------- 测试辅助
  //: 一次性开关：保存配置时把「今日已写入条数」清零，便于同一天反复测试
  reset_daily_counter: false,
  // ---------------- 配置结构版本（随本次发布一起更新，用于默认值迁移）
  config_version: 4,
  // ---------------- 一次性执行
  onlyonce: false,
};

/** 返回默认配置的深拷贝（避免多处共享同一份可变对象）。 */
function defaultConfig() {
  return JSON.parse(JSON.stringify(configDefaults))
}

const {resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createVNode:_createVNode,createElementVNode:_createElementVNode,unref:_unref,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,normalizeClass:_normalizeClass,createStaticVNode:_createStaticVNode} = await importShared('vue');


const _hoisted_1 = { class: "sc-root" };
const _hoisted_2 = { class: "sc-header" };
const _hoisted_3 = { class: "sc-header-main" };
const _hoisted_4 = { class: "sc-logo" };
const _hoisted_5 = { class: "sc-title" };
const _hoisted_6 = { class: "sc-body" };
const _hoisted_7 = { class: "sc-nav" };
const _hoisted_8 = ["onClick"];
const _hoisted_9 = { class: "sc-nav-label" };
const _hoisted_10 = {
  key: 0,
  class: "sc-nav-badge"
};
const _hoisted_11 = { class: "sc-content" };
const _hoisted_12 = { class: "sc-cards" };
const _hoisted_13 = { class: "sc-stat-top" };
const _hoisted_14 = { class: "sc-stat-label" };
const _hoisted_15 = { class: "sc-stat-value" };
const _hoisted_16 = { class: "sc-stat-sub" };
const _hoisted_17 = {
  key: 0,
  class: "sc-card"
};
const _hoisted_18 = { class: "sc-card" };
const _hoisted_19 = { class: "sc-flow" };
const _hoisted_20 = { class: "sc-card" };
const _hoisted_21 = { class: "sc-row" };
const _hoisted_22 = { class: "sc-card" };
const _hoisted_23 = { class: "sc-list-head" };
const _hoisted_24 = { class: "sc-hint" };
const _hoisted_25 = { class: "sc-list-row" };
const _hoisted_26 = { class: "sc-list-row sc-list-params" };
const _hoisted_27 = { class: "sc-card" };
const _hoisted_28 = { class: "sc-row" };
const _hoisted_29 = { class: "sc-card" };
const _hoisted_30 = { class: "sc-card-title" };
const _hoisted_31 = { class: "sc-card" };
const _hoisted_32 = { class: "sc-row" };
const _hoisted_33 = { class: "sc-card" };
const _hoisted_34 = { class: "sc-card-title" };
const _hoisted_35 = { class: "sc-card" };
const _hoisted_36 = { class: "sc-card-title" };
const _hoisted_37 = { class: "sc-card" };
const _hoisted_38 = { class: "sc-card-title" };
const _hoisted_39 = { class: "sc-row" };
const _hoisted_40 = { class: "sc-row" };
const _hoisted_41 = {
  key: 5,
  class: "sc-card"
};
const _hoisted_42 = { class: "sc-row-main" };
const _hoisted_43 = { class: "sc-row-label" };
const _hoisted_44 = { class: "sc-row-hint" };
const _hoisted_45 = { class: "sc-row" };
const _hoisted_46 = {
  key: 6,
  class: "sc-card"
};
const _hoisted_47 = { class: "sc-card-title sc-preview-head" };
const _hoisted_48 = { class: "sc-preview-action" };
const _hoisted_49 = {
  key: 0,
  class: "sc-empty"
};
const _hoisted_50 = { class: "d-flex align-center flex-wrap ga-2" };
const _hoisted_51 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_52 = {
  key: 1,
  class: "sc-hint"
};
const _hoisted_53 = {
  key: 2,
  class: "sc-hint"
};
const _hoisted_54 = { class: "sc-footer" };
const _hoisted_55 = { class: "sc-footer-right" };

const {computed,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'SubscribeCenter' },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

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
 *
 * 版面（0.9.0 重做）：
 * - 左侧分区导航 + 右侧卡片内容 + 底部吸底操作栏；
 * - 首屏「总览」用数据卡呈现关键状态，不必滚到底就看清；
 * - 每个开关一行（标题/说明在左、开关在右），避免一长串灰色文字堆叠。
 */
const props = __props;
const emit = __emit;

const form = ref(defaultConfig());
const loading = ref(false);
const busy = ref('');
const status = ref(null);
const tip = ref({ show: false, ok: true, text: '' });
const previewItems = ref([]);
const activeSection = ref('overview');

/** 决策常量 -> 中文标签（与后端 core/constants.py 逐字对应）。 */
const DECISION_LABELS = {
  added: '新增',
  skipped_dry_run: 'dry-run',
  pending_review: '待确认',
  skipped_special: '特别篇',
  skipped_finished: '已播完',
  skipped_no_date: '无日期',
  skipped_want: '想看不足',
  skipped_rating: '评分不足',
  skipped_popularity: '关注度不足',
  skipped_out_of_window: '超出窗口',
  skipped_not_future: '档期已过',
  skipped_duplicate: '重复',
  skipped_daily_limit: '触达上限',
  skipped_already_subscribed: '已订阅',
  skipped_already_completed: '已完成过',
};

/** 后端版本号；与前端不一致时提示硬刷新。 */
const backendVersion = computed(() => String(status.value?.plugin_version || ''));
const versionMismatch = computed(() => {
  if (!backendVersion.value) return ''
  return backendVersion.value === FRONTEND_VERSION
    ? ''
    : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backendVersion.value}`
});

/** 已实现的数据源（其余源在当前版本会在日志里明确跳过）。 */
const IMPLEMENTED = ['tmdb', 'anilist', 'douban_rss'];

/** 豆瓣 RSS 地址：后端存字符串数组，界面用多行文本编辑。 */
computed({
  get() {
    const value = form.value.douban_rss_sources;
    return Array.isArray(value) ? value.join('\n') : String(value || '')
  },
  set(value) {
    form.value.douban_rss_sources = String(value || '')
      .split(/[\n,，]+/)
      .map((entry) => entry.trim())
      .filter(Boolean);
  },
});

const sourceRows = [
  { key: 'enable_tmdb', label: 'TMDB', hint: '全球电影/剧集，自带 TMDB ID（身份最可靠）' },
  {
    key: 'enable_anilist',
    label: 'AniList',
    hint: '番剧 + 国漫；官方 GraphQL，自带开播日、在播状态与热度',
  },
  { key: 'enable_douban_rss', label: '豆瓣 RSS', hint: '经 RSSHub；上映日期与豆瓣 ID 均可解析' },
];

/** 基础开关：一行一个，左标题右开关。 */
const switchRows = [
  {
    key: 'enabled',
    label: '启用插件',
    hint: '关闭后定时任务与手动运行都会跳过',
  },
  {
    key: 'discovery_page_enabled',
    label: '在「发现」分区显示入口',
    hint: '关闭只是不显示入口，插件仍会按时运行',
  },
  {
    key: 'dry_run',
    label: 'dry-run（只记录不写入）',
    hint: '调参阶段建议开启：跑完整流程但不真的建订阅',
  },
  {
    key: 'notify_each_subscription',
    label: '每条新订阅都发 MP 原生通知',
    hint: 'MP 自带的「新增订阅」消息；关闭后只有下面的运行摘要',
  },
  {
    key: 'notify',
    label: '发送运行摘要通知',
    hint: '每次运行结束后推送一条汇总消息',
  },
];

const enabledSourceCount = computed(
  () => sourceRows.filter((row) => form.value[row.key]).length,
);

const sectionNav = computed(() => [
  { key: 'overview', label: '总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'tmdb', label: 'TMDB', icon: 'mdi-movie-open-outline' },
  { key: 'anilist', label: 'AniList', icon: 'mdi-animation-outline' },
  { key: 'douban', label: '豆瓣榜单', icon: 'mdi-movie-filter-outline' },
  { key: 'schedule', label: '写入与调度', icon: 'mdi-calendar-clock' },
  { key: 'preview', label: '预览结果', icon: 'mdi-eye-outline' },
]);

const overviewCards = computed(() => {
  const written = status.value?.written_today;
  const limit = status.value?.daily_limit;
  return [
    {
      icon: 'mdi-download-network-outline',
      label: '今日写入',
      value: written != null ? `${written}` : '—',
      sub:
        limit == null
          ? '上限未取到'
          : Number(limit) <= 0
            ? '不限制写入条数'
            : `上限 ${limit} 条`,
      color: 'primary',
    },
    {
      icon: 'mdi-radar',
      label: '已启用数据源',
      value: `${enabledSourceCount.value}`,
      sub: `共 ${sourceRows.length} 个，已实现 ${IMPLEMENTED.length} 个`,
      color: 'info',
    },
    {
      icon: 'mdi-calendar-range',
      label: '发现窗口',
      value: `${form.value.tmdb_future_days ?? '—'} 天`,
      sub: `Bangumi ${form.value.bangumi_future_days ?? '—'} 天 · 豆瓣 ${form.value.douban_future_days ?? '—'} 天`,
      color: 'success',
    },
    {
      icon: 'mdi-source-branch',
      label: '组件版本',
      value: `v${FRONTEND_VERSION}`,
      sub: backendVersion.value ? `后端 v${backendVersion.value}` : '后端版本未知',
      color: versionMismatch.value ? 'warning' : 'default',
    },
  ]
});

/** 概览里的提醒条目（只显示确实需要注意的）。 */
const overviewAlerts = computed(() => {
  const list = [];
  if (versionMismatch.value) {
    list.push({
      type: 'warning',
      text: `${versionMismatch.value}：浏览器仍在用缓存的旧联邦组件，请按 Ctrl+Shift+R 硬刷新后再操作。`,
    });
  }
  if (status.value && !status.value.first_run_completed) {
    list.push({
      type: 'info',
      text: '首次运行会强制 dry-run 一次：只记录不写入，确认结果后再放开。',
    });
  }
  if (!form.value.enabled) {
    list.push({ type: 'warning', text: '插件当前未启用，定时任务不会执行。' });
  }
  if (form.value.dry_run) {
    list.push({ type: 'info', text: 'dry-run 已开启：本次运行不会真的建订阅。' });
  }
  if (!cronValid()) {
    list.push({ type: 'error', text: '执行时间不是合法的 5 段式 cron（分 时 日 月 周）。' });
  }
  const pending = sourceRows.filter(
    (row) => form.value[row.key] && !IMPLEMENTED.includes(row.key.replace('enable_', '')),
  );
  if (pending.length) {
    list.push({
      type: 'info',
      text: `已启用但当前版本不会运行：${pending.map((row) => row.label).join('、')}`,
    });
  }
  return list
});

/** 豆瓣榜单列表（每榜独立配置）。 */
const doubanLists = computed(() => form.value.douban_rss_sources || []);

/** 添加一条自定义榜单。 */
function addDoubanList() {
  if (!Array.isArray(form.value.douban_rss_sources)) form.value.douban_rss_sources = [];
  form.value.douban_rss_sources.push({
    name: '自定义榜单',
    url: '',
    enabled: true,
    max_items: 30,
    future_days: 3,
    min_want: 0,
  });
}

/** 删除一条榜单。 */
function removeDoubanList(index) {
  const list = form.value.douban_rss_sources;
  if (Array.isArray(list) && index >= 0 && index < list.length) list.splice(index, 1);
}

/** 统计启用条数（卡片标题用）。 */
const doubanEnabledCount = computed(
  () => doubanLists.value.filter((entry) => entry && entry.enabled).length,
);

function setTip(text, ok = true) {
  tip.value = { show: true, ok, text };
}

function mergeConfig(value) {
  const base = defaultConfig();
  if (value && typeof value === 'object') {
    for (const key of Object.keys(base)) {
      if (value[key] !== undefined && value[key] !== null) base[key] = value[key];
    }
  }
  return base
}

function buildPayload() {
  // 只提交 default_config 里声明过的键，避免把宿主的其它数据带回去
  const payload = {};
  for (const key of Object.keys(defaultConfig())) payload[key] = form.value[key];
  return payload
}

function cronValid() {
  return String(form.value.cron || '').trim().split(/\s+/).length === 5
}

async function loadConfig() {
  loading.value = true;
  try {
    const value = await getPluginConfig(props.api, props.pluginId);
    form.value = mergeConfig(value && Object.keys(value).length ? value : props.initialConfig);
  } catch (error) {
    form.value = mergeConfig(props.initialConfig);
    setTip(error?.message || '配置读取失败', false);
  } finally {
    loading.value = false;
  }
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status'));
  } catch (error) {
    // 状态失败不影响保存配置，只在控制台留痕
    console.warn('[SubscribeCenter] 状态读取失败：', error?.message || error);
  }
}

async function save() {
  if (busy.value) return
  if (!cronValid()) {
    setTip('cron 必须是 5 段式（分 时 日 月 周），例如 0 3 * * *', false);
    return
  }
  busy.value = 'save';
  try {
    const payload = buildPayload();
    // 两条路都走：宿主编排 + 自持保存
    emit('save', payload);
    await savePluginConfig(props.api, props.pluginId, payload);
    setTip('设置已保存');
    await loadStatus();
  } catch (error) {
    setTip(error?.message || '保存失败', false);
  } finally {
    busy.value = '';
  }
}

async function runOnce() {
  if (busy.value) return
  busy.value = 'run';
  try {
    const result = unwrap(
      await postPluginApi(props.api, props.pluginId, 'run_once', {}, { timeoutMs: 600000 }),
    );
    if (result?.skipped) {
      setTip('已有发现任务正在运行，本次跳过');
    } else {
      const s = result?.summary || {};
      setTip(
        `本次完成：拉取 ${s.fetched ?? 0} 条 / 新增 ${s.added ?? 0} 条 / `
          + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`
          + (s.dry_run ? '（dry-run，未写入）' : ''),
      );
    }
    await loadStatus();
  } catch (error) {
    setTip(error?.message || '运行失败', false);
  } finally {
    busy.value = '';
  }
}

/**
 * 只读预览：跑完整流水线但**不写订阅、不消耗每日额度**。
 * 这是调参的主要工具 —— 改门槛/窗口后先预览，满意再真跑。
 */
async function preview() {
  if (busy.value) return
  busy.value = 'preview';
  previewItems.value = [];
  try {
    const result = unwrap(
      await postPluginApi(props.api, props.pluginId, 'preview', {}, { timeoutMs: 600000 }),
    );
    if (result?.skipped) {
      setTip('已有发现任务正在运行，本次跳过');
      return
    }
    previewItems.value = result?.items || [];
    activeSection.value = 'preview';
    const s = result?.summary || {};
    const reasons = Object.entries(result?.rejections || {})
      .map(([key, count]) => `${DECISION_LABELS[key] || key} ${count}`)
      .join(' · ');
    setTip(
      `预览完成（未写入）：会订 ${previewItems.value.length} 条 / 拉取 ${s.fetched ?? 0} 条`
        + (reasons ? `；被拦下：${reasons}` : ''),
    );
  } catch (error) {
    setTip(error?.message || '预览失败', false);
  } finally {
    busy.value = '';
  }
}

onMounted(() => {
  loadConfig();
  loadStatus();
});

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VDivider = _resolveComponent("VDivider");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (tip.value.show)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: tip.value.ok ? 'success' : 'error',
          variant: "tonal",
          density: "compact",
          closable: "",
          class: "sc-tip mb-2",
          text: tip.value.text,
          "onClick:close": _cache[0] || (_cache[0] = $event => (tip.value.show = false))
        }, null, 8, ["type", "text"]))
      : _createCommentVNode("", true),
    _createElementVNode("div", _hoisted_2, [
      _createElementVNode("div", _hoisted_3, [
        _createElementVNode("div", _hoisted_4, [
          _createVNode(_component_VIcon, {
            icon: "mdi-movie-open-star-outline",
            size: "22"
          })
        ]),
        _createElementVNode("div", null, [
          _createElementVNode("div", _hoisted_5, [
            _cache[28] || (_cache[28] = _createTextVNode(" 胖虎订阅中心 ", -1)),
            _createVNode(_component_VChip, {
              size: "x-small",
              variant: "flat",
              color: "primary",
              class: "ml-2"
            }, {
              default: _withCtx(() => [
                _createTextVNode(" v" + _toDisplayString(_unref(FRONTEND_VERSION)), 1)
              ]),
              _: 1
            })
          ]),
          _cache[29] || (_cache[29] = _createElementVNode("div", { class: "sc-subtitle" }, " 发现片源 → 解析身份 → 去重 → 写订阅。版本控制与洗版由 MoviePilot 接管，本插件不介入。 ", -1))
        ])
      ]),
      _createVNode(_component_VSwitch, {
        modelValue: form.value.enabled,
        "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((form.value.enabled) = $event)),
        label: form.value.enabled ? '已启用' : '未启用',
        color: "success",
        density: "compact",
        "hide-details": "",
        class: "sc-header-switch"
      }, null, 8, ["modelValue", "label"])
    ]),
    _createElementVNode("div", _hoisted_6, [
      _createElementVNode("nav", _hoisted_7, [
        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sectionNav.value, (item) => {
          return (_openBlock(), _createElementBlock("button", {
            key: item.key,
            type: "button",
            class: _normalizeClass(["sc-nav-item", { 'sc-nav-active': activeSection.value === item.key }]),
            onClick: $event => (activeSection.value = item.key)
          }, [
            _createVNode(_component_VIcon, {
              icon: item.icon,
              size: "18"
            }, null, 8, ["icon"]),
            _createElementVNode("span", _hoisted_9, _toDisplayString(item.label), 1),
            (item.badge)
              ? (_openBlock(), _createElementBlock("span", _hoisted_10, _toDisplayString(item.badge), 1))
              : _createCommentVNode("", true)
          ], 10, _hoisted_8))
        }), 128))
      ]),
      _createElementVNode("section", _hoisted_11, [
        (activeSection.value === 'overview')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
              _createElementVNode("div", _hoisted_12, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overviewCards.value, (card) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: card.label,
                    class: "sc-stat"
                  }, [
                    _createElementVNode("div", _hoisted_13, [
                      _createVNode(_component_VIcon, {
                        icon: card.icon,
                        size: "18",
                        color: card.color
                      }, null, 8, ["icon", "color"]),
                      _createElementVNode("span", _hoisted_14, _toDisplayString(card.label), 1)
                    ]),
                    _createElementVNode("div", _hoisted_15, _toDisplayString(card.value), 1),
                    _createElementVNode("div", _hoisted_16, _toDisplayString(card.sub), 1)
                  ]))
                }), 128))
              ]),
              (overviewAlerts.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_17, [
                    _cache[30] || (_cache[30] = _createElementVNode("div", { class: "sc-card-title" }, "需要注意", -1)),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overviewAlerts.value, (alert, index) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: index,
                        class: _normalizeClass(["sc-alert-row", `sc-alert-${alert.type}`])
                      }, [
                        _createVNode(_component_VIcon, {
                          icon: alert.type === 'error'
                  ? 'mdi-alert-circle-outline'
                  : alert.type === 'warning'
                    ? 'mdi-alert-outline'
                    : 'mdi-information-outline',
                          size: "16"
                        }, null, 8, ["icon"]),
                        _createElementVNode("span", null, _toDisplayString(alert.text), 1)
                      ], 2))
                    }), 128))
                  ]))
                : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_18, [
                _cache[37] || (_cache[37] = _createElementVNode("div", { class: "sc-card-title" }, "运行链路", -1)),
                _createElementVNode("div", _hoisted_19, [
                  _cache[31] || (_cache[31] = _createElementVNode("span", { class: "sc-flow-node" }, "拉取候选", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[32] || (_cache[32] = _createElementVNode("span", { class: "sc-flow-node" }, "身份解析", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[33] || (_cache[33] = _createElementVNode("span", { class: "sc-flow-node" }, "季号裁决", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[34] || (_cache[34] = _createElementVNode("span", { class: "sc-flow-node" }, "阈值过滤", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[35] || (_cache[35] = _createElementVNode("span", { class: "sc-flow-node" }, "去重", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[36] || (_cache[36] = _createElementVNode("span", { class: "sc-flow-node sc-flow-accent" }, "写订阅", -1))
                ]),
                _cache[38] || (_cache[38] = _createElementVNode("div", { class: "sc-hint mt-2" }, " 季号由 TMDB 的真实数据裁决（哪一季还有未播集），不猜豆瓣/Bangumi 的命名含义。 ", -1))
              ])
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'douban')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
              _createElementVNode("div", _hoisted_20, [
                _createElementVNode("div", _hoisted_21, [
                  _cache[39] || (_cache[39] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "启用豆瓣 RSS"),
                    _createElementVNode("div", { class: "sc-row-hint" }, "经 RSSHub 的豆瓣路线发现；下面每条榜单可独立配置")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.enable_douban_rss,
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((form.value.enable_douban_rss) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ])
              ]),
              _createElementVNode("div", _hoisted_22, [
                _cache[41] || (_cache[41] = _createElementVNode("div", { class: "sc-card-title" }, "豆瓣 RSS 路线", -1)),
                _createVNode(_component_VTextField, {
                  modelValue: form.value.rsshub_domain,
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((form.value.rsshub_domain) = $event)),
                  label: "RSSHub 域名（总控）",
                  density: "compact",
                  "hide-details": "",
                  variant: "outlined",
                  placeholder: "http://192.168.50.134:1200",
                  class: "mb-2",
                  disabled: !form.value.enable_douban_rss
                }, null, 8, ["modelValue", "disabled"]),
                _cache[42] || (_cache[42] = _createElementVNode("div", { class: "sc-hint mb-2" }, [
                  _createTextVNode(" 每条榜单只填**路由**（如 "),
                  _createElementVNode("code", null, "/douban/movie/coming"),
                  _createTextVNode("）， 实际请求 = 域名 + 路由。换 RSSHub 地址只改这里，不用逐条改。 ")
                ], -1)),
                _createElementVNode("div", _hoisted_23, [
                  _createElementVNode("span", _hoisted_24, "已启用 " + _toDisplayString(doubanEnabledCount.value) + " / " + _toDisplayString(doubanLists.value.length) + " 条", 1),
                  _createVNode(_component_VBtn, {
                    size: "x-small",
                    variant: "tonal",
                    "prepend-icon": "mdi-plus",
                    onClick: addDoubanList
                  }, {
                    default: _withCtx(() => [...(_cache[40] || (_cache[40] = [
                      _createTextVNode(" 添加榜单 ", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(doubanLists.value, (entry, index) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: index,
                    class: _normalizeClass(["sc-list-item", { 'sc-list-off': !entry.enabled }])
                  }, [
                    _createElementVNode("div", _hoisted_25, [
                      _createVNode(_component_VSwitch, {
                        modelValue: entry.enabled,
                        "onUpdate:modelValue": $event => ((entry.enabled) = $event),
                        density: "compact",
                        "hide-details": "",
                        color: "primary",
                        class: "sc-list-switch"
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _createVNode(_component_VTextField, {
                        modelValue: entry.name,
                        "onUpdate:modelValue": $event => ((entry.name) = $event),
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        placeholder: "榜单名称",
                        style: {"max-width":"160px"}
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _createVNode(_component_VTextField, {
                        modelValue: entry.url,
                        "onUpdate:modelValue": $event => ((entry.url) = $event),
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        placeholder: "/douban/movie/coming 或完整 URL",
                        class: "sc-list-url"
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _createVNode(_component_VBtn, {
                        size: "x-small",
                        variant: "text",
                        color: "error",
                        icon: "mdi-delete-outline",
                        onClick: $event => (removeDoubanList(index))
                      }, null, 8, ["onClick"])
                    ]),
                    _createElementVNode("div", _hoisted_26, [
                      _createVNode(_component_VTextField, {
                        modelValue: entry.max_items,
                        "onUpdate:modelValue": $event => ((entry.max_items) = $event),
                        modelModifiers: { number: true },
                        label: "每榜条数（0=沿用全局）",
                        type: "number",
                        min: "1",
                        max: "200",
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined"
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _createVNode(_component_VTextField, {
                        modelValue: entry.future_days,
                        "onUpdate:modelValue": $event => ((entry.future_days) = $event),
                        modelModifiers: { number: true },
                        label: "窗口天数（0=沿用全局）",
                        type: "number",
                        min: "0",
                        max: "120",
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined"
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _createVNode(_component_VTextField, {
                        modelValue: entry.min_want,
                        "onUpdate:modelValue": $event => ((entry.min_want) = $event),
                        modelModifiers: { number: true },
                        label: "最低想看（0=不限）",
                        type: "number",
                        min: "0",
                        step: "100",
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined"
                      }, null, 8, ["modelValue", "onUpdate:modelValue"])
                    ])
                  ], 2))
                }), 128)),
                _cache[43] || (_cache[43] = _createStaticVNode("<div class=\"sc-hint mt-2\" data-v-d69d8351><b data-v-d69d8351>电影上映类</b>（<code data-v-d69d8351>/douban/movie/coming</code>）带精确上映日期，按窗口过滤，最准。<br data-v-d69d8351><b data-v-d69d8351>剧集类</b>（<code data-v-d69d8351>/douban/tv/coming</code>、<code data-v-d69d8351>/douban/list/tv_*</code>、 <code data-v-d69d8351>/douban/recommended/tv</code>）没有日期，按「TMDB 还有没有未播集」判断，等效追番。<br data-v-d69d8351><b data-v-d69d8351>电影榜单类</b>没有日期，会被跳过。<code data-v-d69d8351>ustop250</code> 与 <code data-v-d69d8351>/douban/movie/new</code> 在新版 RSSHub 已 404。 </div>", 1))
              ])
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'tmdb')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
              _createElementVNode("div", _hoisted_27, [
                _createElementVNode("div", _hoisted_28, [
                  _cache[44] || (_cache[44] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "启用 TMDB 数据源"),
                    _createElementVNode("div", { class: "sc-row-hint" }, "TMDB 即将上映 / 热门发现（电影与剧集）")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.enable_tmdb,
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((form.value.enable_tmdb) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ])
              ]),
              _createElementVNode("div", _hoisted_29, [
                _createElementVNode("div", _hoisted_30, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-movie-open-outline",
                    size: "16"
                  }),
                  _cache[45] || (_cache[45] = _createTextVNode(" TMDB ", -1))
                ]),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.tmdb_future_days,
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((form.value.tmdb_future_days) = $event)),
                          modelModifiers: { number: true },
                          label: "发现窗口（天）",
                          type: "number",
                          min: "1",
                          max: "90",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.min_rating_tmdb,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((form.value.min_rating_tmdb) = $event)),
                          modelModifiers: { number: true },
                          label: "最低评分",
                          type: "number",
                          step: "0.1",
                          min: "0",
                          max: "10",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.min_popularity,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.value.min_popularity) = $event)),
                          modelModifiers: { number: true },
                          label: "最低关注度",
                          type: "number",
                          step: "1",
                          min: "0",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _cache[46] || (_cache[46] = _createElementVNode("div", { class: "sc-hint" }, [
                  _createTextVNode(" 只保留「今天 ~ 今天 + N 天」内的定档条目。"),
                  _createElementVNode("b", null, "最低关注度"),
                  _createTextVNode("是新片唯一可用的质量信号 （观众级大片 100+、院线片 10~50、冷门片 <5），设 0 表示不过滤。 ")
                ], -1)),
                _createVNode(_component_VDivider, { class: "my-3" }),
                _createVNode(_component_VSwitch, {
                  modelValue: form.value.filter_original_language,
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.value.filter_original_language) = $event)),
                  label: "只保留指定原始语言的条目",
                  density: "compact",
                  "hide-details": "",
                  color: "primary"
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: form.value.tmdb_original_languages,
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.value.tmdb_original_languages) = $event)),
                  label: "允许的原始语言（逗号分隔）",
                  density: "compact",
                  "hide-details": "",
                  variant: "outlined",
                  disabled: !form.value.filter_original_language,
                  placeholder: "zh,ja,ko,en",
                  class: "mt-2"
                }, null, 8, ["modelValue", "disabled"]),
                _cache[47] || (_cache[47] = _createElementVNode("div", { class: "sc-hint mt-1" }, " 语种码：zh 华语 / ja 日语 / ko 韩语 / en 英语。小语种片通常不会被下载，进订阅只会白占额度。 ", -1))
              ])
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'anilist')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
              _createElementVNode("div", _hoisted_31, [
                _createElementVNode("div", _hoisted_32, [
                  _cache[48] || (_cache[48] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "启用 AniList 数据源"),
                    _createElementVNode("div", { class: "sc-row-hint" }, "番剧新番 / 连载 / 国漫（含下一集播出时间）")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.enable_anilist,
                    "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.value.enable_anilist) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ])
              ]),
              _createElementVNode("div", _hoisted_33, [
                _createElementVNode("div", _hoisted_34, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-animation-outline",
                    size: "16"
                  }),
                  _cache[49] || (_cache[49] = _createTextVNode(" AniList ", -1))
                ]),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.anilist_future_days,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.value.anilist_future_days) = $event)),
                          modelModifiers: { number: true },
                          label: "发现窗口（天）",
                          type: "number",
                          min: "1",
                          max: "90",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.min_rating_anilist,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.value.min_rating_anilist) = $event)),
                          modelModifiers: { number: true },
                          label: "最低评分",
                          type: "number",
                          step: "0.1",
                          min: "0",
                          max: "10",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.anilist_min_popularity,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.value.anilist_min_popularity) = $event)),
                          modelModifiers: { number: true },
                          label: "最低热度",
                          type: "number",
                          min: "0",
                          step: "100",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "3",
                      class: "d-flex align-center"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: form.value.anilist_include_donghua,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.value.anilist_include_donghua) = $event)),
                          label: "包含国漫",
                          density: "compact",
                          "hide-details": "",
                          color: "primary"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _cache[50] || (_cache[50] = _createElementVNode("div", { class: "sc-hint" }, [
                  _createElementVNode("b", null, "番剧与国漫的最佳源。"),
                  _createTextVNode("两条发现通道缺一不可："),
                  _createElementVNode("br"),
                  _createTextVNode(" • "),
                  _createElementVNode("b", null, "新番"),
                  _createTextVNode("：按「开播日」落窗口，覆盖当季 + 下季已定档；"),
                  _createElementVNode("br"),
                  _createTextVNode(" • "),
                  _createElementVNode("b", null, "连载中"),
                  _createTextVNode("：按「下一集播出时间」落窗口 —— "),
                  _createElementVNode("b", null, "国漫只能靠这条"),
                  _createTextVNode(" （《遮天》2023 年开播、208 集，开播日永远在窗口外）。"),
                  _createElementVNode("br"),
                  _createTextVNode(" 热度量纲与 TMDB 不同（冷门番上千、主流番 2~5 万），所以单独设门槛。 国漫默认包含，只想订日番就关掉。 ")
                ], -1))
              ])
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'douban')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
              _createElementVNode("div", _hoisted_35, [
                _createElementVNode("div", _hoisted_36, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-movie-filter-outline",
                    size: "16"
                  }),
                  _cache[51] || (_cache[51] = _createTextVNode(" 豆瓣 RSS ", -1))
                ]),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.douban_future_days,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.value.douban_future_days) = $event)),
                          modelModifiers: { number: true },
                          label: "发现窗口（天）",
                          type: "number",
                          min: "1",
                          max: "90",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2",
                          disabled: !form.value.enable_douban_rss
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.min_rating_douban,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((form.value.min_rating_douban) = $event)),
                          modelModifiers: { number: true },
                          label: "最低评分",
                          type: "number",
                          step: "0.1",
                          min: "0",
                          max: "10",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2",
                          disabled: !form.value.enable_douban_rss
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.douban_min_want,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.value.douban_min_want) = $event)),
                          modelModifiers: { number: true },
                          label: "最低想看人数（0 = 不限）",
                          type: "number",
                          min: "0",
                          step: "100",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2",
                          disabled: !form.value.enable_douban_rss
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.douban_max_items_per_feed,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.value.douban_max_items_per_feed) = $event)),
                          modelModifiers: { number: true },
                          label: "每个榜单最多取 N 条",
                          type: "number",
                          min: "1",
                          max: "200",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2",
                          disabled: !form.value.enable_douban_rss
                        }, null, 8, ["modelValue", "disabled"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.resolve_concurrency,
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.value.resolve_concurrency) = $event)),
                          modelModifiers: { number: true },
                          label: "身份解析并发数",
                          type: "number",
                          min: "1",
                          max: "16",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          class: "mb-2"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _cache[52] || (_cache[52] = _createElementVNode("div", { class: "sc-hint" }, [
                  _createTextVNode(" 豆瓣窗口独立于 TMDB（「即将上映」是策展列表，可以放宽）。想看人数只有 coming 类路线提供， 榜单类没有该数据，"),
                  _createElementVNode("b", null, "缺失时不拦"),
                  _createTextVNode("。候选多不需要手动减 —— 解析是并发的， 实测 260 条约 20~30 秒。 ")
                ], -1))
              ]),
              _createElementVNode("div", _hoisted_37, [
                _createElementVNode("div", _hoisted_38, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-check-decagram-outline",
                    size: "16"
                  }),
                  _cache[53] || (_cache[53] = _createTextVNode(" 订阅行为 ", -1))
                ]),
                _createElementVNode("div", _hoisted_39, [
                  _cache[54] || (_cache[54] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "已完成过的订阅允许重新订阅"),
                    _createElementVNode("div", { class: "sc-row-hint" }, [
                      _createTextVNode(" 从媒体库删掉文件后想重新下时需要。真正"),
                      _createElementVNode("b", null, "已经播完"),
                      _createTextVNode("的剧不会因此重复订阅。 ")
                    ])
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.resubscribe_completed,
                    "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((form.value.resubscribe_completed) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_40, [
                  _cache[55] || (_cache[55] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "用 TMDB 分组精确订阅被压成单季的番剧"),
                    _createElementVNode("div", { class: "sc-row-hint" }, [
                      _createTextVNode(" 如《药屋少女的呢喃》= 1 季 60 集，第 49~60 集才是第 3 季。开启后只订那 12 集， "),
                      _createElementVNode("b", null, "不会去补前 48 集旧番"),
                      _createTextVNode("。 ")
                    ])
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.prefer_episode_group,
                    "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.value.prefer_episode_group) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ])
              ])
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'schedule')
          ? (_openBlock(), _createElementBlock("div", _hoisted_41, [
              _cache[57] || (_cache[57] = _createElementVNode("div", { class: "sc-card-title" }, "写入与调度", -1)),
              _createVNode(_component_VRow, { dense: "" }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCol, {
                    cols: "12",
                    sm: "6"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VTextField, {
                        modelValue: form.value.daily_limit,
                        "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((form.value.daily_limit) = $event)),
                        modelModifiers: { number: true },
                        label: "每日写入上限（0 = 不限）",
                        type: "number",
                        min: "0",
                        max: 100000,
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        class: "mb-2"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VCol, {
                    cols: "12",
                    sm: "6"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VTextField, {
                        modelValue: form.value.resolve_concurrency,
                        "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((form.value.resolve_concurrency) = $event)),
                        modelModifiers: { number: true },
                        label: "身份解析并发数",
                        type: "number",
                        min: "1",
                        max: "16",
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        class: "mb-2"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VCol, {
                    cols: "12",
                    sm: "6"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VTextField, {
                        modelValue: form.value.cron,
                        "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((form.value.cron) = $event)),
                        label: "执行时间（5 段式 cron）",
                        error: !cronValid(),
                        "error-messages": cronValid() ? [] : ['需要 5 段，例如 0 3 * * *'],
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        class: "mb-2"
                      }, null, 8, ["modelValue", "error", "error-messages"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_VCol, {
                    cols: "12",
                    sm: "6"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VTextField, {
                        modelValue: form.value.timezone,
                        "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((form.value.timezone) = $event)),
                        label: "时区",
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        class: "mb-2"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _cache[58] || (_cache[58] = _createElementVNode("div", { class: "sc-hint" }, "修改 cron 后需要重新保存配置才会重建定时任务。", -1)),
              _createVNode(_component_VDivider, { class: "my-3" }),
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(switchRows.filter((item) => item.key !== 'enabled'), (row) => {
                return (_openBlock(), _createElementBlock("div", {
                  key: row.key,
                  class: "sc-row"
                }, [
                  _createElementVNode("div", _hoisted_42, [
                    _createElementVNode("div", _hoisted_43, _toDisplayString(row.label), 1),
                    _createElementVNode("div", _hoisted_44, _toDisplayString(row.hint), 1)
                  ]),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value[row.key],
                    "onUpdate:modelValue": $event => ((form.value[row.key]) = $event),
                    density: "compact",
                    "hide-details": "",
                    color: "primary",
                    disabled: row.key !== 'notify' && !form.value.enabled
                  }, null, 8, ["modelValue", "onUpdate:modelValue", "disabled"])
                ]))
              }), 128)),
              _createElementVNode("div", _hoisted_45, [
                _cache[56] || (_cache[56] = _createElementVNode("div", { class: "sc-row-main" }, [
                  _createElementVNode("div", { class: "sc-row-label" }, "清零今日写入计数（测试开关）"),
                  _createElementVNode("div", { class: "sc-row-hint" }, " 保存后把「今日已写入 N 条」清零，方便同一天反复测；保存即自动置回关闭。 首次运行无论此开关如何都会强制 dry-run 一次。 ")
                ], -1)),
                _createVNode(_component_VSwitch, {
                  modelValue: form.value.reset_daily_counter,
                  "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((form.value.reset_daily_counter) = $event)),
                  density: "compact",
                  "hide-details": "",
                  color: "warning"
                }, null, 8, ["modelValue"])
              ])
            ]))
          : _createCommentVNode("", true),
        (activeSection.value === 'preview')
          ? (_openBlock(), _createElementBlock("div", _hoisted_46, [
              _createElementVNode("div", _hoisted_47, [
                _createVNode(_component_VIcon, {
                  icon: "mdi-eye-outline",
                  size: "16"
                }),
                _cache[61] || (_cache[61] = _createTextVNode(" 预览结果 ", -1)),
                _createVNode(_component_VChip, {
                  size: "x-small",
                  variant: "flat",
                  color: "info",
                  class: "ml-2"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 会订 " + _toDisplayString(previewItems.value.length) + " 条 ", 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_VChip, {
                  size: "x-small",
                  variant: "tonal",
                  class: "ml-1"
                }, {
                  default: _withCtx(() => [...(_cache[59] || (_cache[59] = [
                    _createTextVNode("未写入 · 未消耗额度", -1)
                  ]))]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_48, [
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    color: "info",
                    size: "small",
                    loading: busy.value === 'preview',
                    disabled: loading.value,
                    "prepend-icon": "mdi-eye-outline",
                    onClick: preview
                  }, {
                    default: _withCtx(() => [...(_cache[60] || (_cache[60] = [
                      _createTextVNode(" 开始预览 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading", "disabled"])
                ])
              ]),
              (!previewItems.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_49, [...(_cache[62] || (_cache[62] = [
                    _createTextVNode(" 还没有预览结果。点上方「开始预览」跑一次 —— 它跑完整流程但", -1),
                    _createElementVNode("b", null, "不写订阅、不消耗每日额度", -1),
                    _createTextVNode("，是调参的主要手段。 ", -1)
                  ]))]))
                : _createCommentVNode("", true),
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(previewItems.value, (row, index) => {
                return (_openBlock(), _createElementBlock("div", {
                  key: index,
                  class: "sc-preview-row"
                }, [
                  _createElementVNode("div", _hoisted_50, [
                    _createVNode(_component_VChip, {
                      size: "x-small",
                      variant: "flat",
                      color: "info"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(row.media_type), 1)
                      ]),
                      _: 2
                    }, 1024),
                    _createElementVNode("b", null, _toDisplayString(row.title), 1),
                    (row.year)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_51, "(" + _toDisplayString(row.year) + ")", 1))
                      : _createCommentVNode("", true),
                    (row.release_date)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_52, "放送 " + _toDisplayString(row.release_date), 1))
                      : _createCommentVNode("", true),
                    _createVNode(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: "warning"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 关注度 " + _toDisplayString(row.popularity != null ? row.popularity.toFixed(1) : '—'), 1)
                      ]),
                      _: 2
                    }, 1024),
                    (row.rating != null)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_53, "评分 " + _toDisplayString(row.rating), 1))
                      : _createCommentVNode("", true)
                  ])
                ]))
              }), 128))
            ]))
          : _createCommentVNode("", true)
      ])
    ]),
    _createElementVNode("div", _hoisted_54, [
      _createVNode(_component_VBtn, {
        variant: "text",
        size: "small",
        onClick: _cache[27] || (_cache[27] = $event => (emit('close')))
      }, {
        default: _withCtx(() => [...(_cache[63] || (_cache[63] = [
          _createTextVNode("关闭", -1)
        ]))]),
        _: 1
      }),
      _createElementVNode("div", _hoisted_55, [
        _createVNode(_component_VBtn, {
          variant: "tonal",
          size: "small",
          loading: busy.value === 'run',
          disabled: loading.value,
          "prepend-icon": "mdi-radar",
          onClick: runOnce
        }, {
          default: _withCtx(() => [...(_cache[64] || (_cache[64] = [
            _createTextVNode(" 立即运行一次 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "disabled"]),
        _createVNode(_component_VBtn, {
          color: "primary",
          size: "small",
          loading: busy.value === 'save',
          disabled: loading.value,
          "prepend-icon": "mdi-content-save",
          onClick: save
        }, {
          default: _withCtx(() => [...(_cache[65] || (_cache[65] = [
            _createTextVNode(" 保存配置 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "disabled"])
      ])
    ])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-d69d8351"]]);

export { Config as default };
