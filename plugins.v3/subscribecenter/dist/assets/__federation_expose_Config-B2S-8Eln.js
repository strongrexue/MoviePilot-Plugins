import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, F as FRONTEND_VERSION, u as unwrap, g as getPluginApi, a as getPluginConfig, p as postPluginApi, s as savePluginConfig } from './_plugin-vue_export-helper-N-L8Lgmg.js';

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
  // ---------------- 平台首播（腾讯视频 / B 站番剧）
  //: 腾讯视频「即将上线」——电视剧/电影/综艺三个频道（私有接口，默认关）
  enable_qq_video: false,
  qq_video_channels: ['tv', 'movie', 'variety'],
  qq_video_max_items: 40,
  //: B 站番剧时间表（AniList 的备份，默认关）
  enable_bilibili: false,
  bilibili_future_days: 7,
  bilibili_max_items: 30,
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
  // ---------------- 排除规则（黑名单）
  //: 总开关：默认关，关掉时行为与没有这个功能时完全一致
  blacklist_enabled: false,
  //: 排除的电影类型（TMDB genre id）。注意别勾「剧情(18)」，几乎所有片都带
  blacklist_genre_movie: [],
  //: 排除的剧集类型（TMDB genre id）。同理别勾「剧情(18)」
  blacklist_genre_tv: [],
  //: 启用的内置题材预设 key（默认空：内置词表必须用户勾选才生效）
  blacklist_presets: [],
  //: 自定义题材词（一行一个；空格=同时包含，regex: 正则，case: 区分大小写）
  blacklist_words: '',
  //: 是否匹配片名 / 原名
  blacklist_match_title: true,
  //: 是否匹配来源题材串（豆瓣 category / AniList genres+tags）
  blacklist_match_tags: true,
  //: 是否额外查 TMDB 关键词（每条多一次请求，默认关）
  blacklist_tmdb_keywords: false,
  // ---------------- 电影发行日兜底
  //: 来源没给日期时，用 TMDB 的数字/实体发行日补上（默认开）
  movie_release_fallback: true,
  //: 电影「刚上映也算数」的宽限天数（0 = 严格未来）
  movie_release_grace_days: 7,
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
  //: 发现流水里记着「订过」的就不再自动订回来（删掉订阅也拦，清空流水才解锁）
  dedupe_by_history: true,
  // ---------------- Simkl
  // ---------------- 写入
  daily_limit: 30,
  // ---------------- 按播出日自动启停（治「订阅刷新」空转）
  //: 总开关：会改订阅状态，默认关。打开前先点「预览」看清会动哪几条。
  auto_toggle_enabled: false,
  //: 每天几点判定（默认零点后 5 分钟 —— 判定基准是服务器本地日期）
  auto_toggle_cron: '5 0 * * *',
  //: 提前几天算「即将播出」（0 = 只看今天）
  auto_toggle_lookahead_days: 0,
  //: 已播但还没入库时再多留几天 R（等 PT 出种）
  auto_toggle_keep_days: 3,
  //: 洗版订阅的保留窗口（等更好的版本，默认三个月）
  auto_toggle_best_version_keep_days: 90,
  //: 洗版判定模式（after_finale = 季终后才按洗版算，always = 播出期也算）
  auto_toggle_best_version_mode: 'after_finale',
  //: 是否连电影订阅一起管（按 TMDB 发行日判，默认开）
  auto_toggle_movie_enabled: true,
  //: 只有影院上映日期时，按上映日往后推几天估算数字发行（0 = 不估算）
  auto_toggle_movie_theatrical_offset_days: 90,
  //: 单次最多改多少条（0 = 不限）
  auto_toggle_max_changes: 0,
  //: 每次自动启停后是否发通知
  auto_toggle_notify: false,
  //: 用媒体库核对真正入库了多少集（默认关：要连媒体服务器，有开销）
  auto_toggle_library_check: false,
  //: 每轮最多花多少秒核对（0 = 只读媒体库快照，一个请求都不发）
  auto_toggle_library_probe_budget_seconds: 300,
  //: 每条之间等几秒（串行，别把 NAS 打满）
  auto_toggle_library_probe_interval: 1.5,
  // ---------------- 调度与通知
  cron_tmdb: '',
  cron_anilist: '',
  cron_douban_rss: '',
  cron_hot_media: '',
  cron: '0 3 * * *',
  timezone: 'Asia/Shanghai',
  notify: false,
  // ---------------- 界面
  // ---------------- 测试辅助
  //: 一次性开关：保存配置时把「今日已写入条数」清零，便于同一天反复测试
  reset_daily_counter: false,
  // ---------------- 配置结构版本（随本次发布一起更新，用于默认值迁移）
  config_version: 12,
  // ---------------- 一次性执行
  onlyonce: false,
};

/** 返回默认配置的深拷贝（避免多处共享同一份可变对象）。 */
function defaultConfig() {
  return JSON.parse(JSON.stringify(configDefaults))
}

const {resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createVNode:_createVNode,createElementVNode:_createElementVNode,unref:_unref,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,vModelText:_vModelText,withDirectives:_withDirectives,normalizeClass:_normalizeClass,vModelCheckbox:_vModelCheckbox,withModifiers:_withModifiers,createStaticVNode:_createStaticVNode} = await importShared('vue');


const _hoisted_1 = { class: "sc-header" };
const _hoisted_2 = { class: "sc-header-main" };
const _hoisted_3 = { class: "sc-logo" };
const _hoisted_4 = { class: "sc-title" };
const _hoisted_5 = { class: "sc-cfg-toolbar" };
const _hoisted_6 = { class: "sc-cfg-presets" };
const _hoisted_7 = { class: "sc-cfg-search" };
const _hoisted_8 = { class: "sc-body" };
const _hoisted_9 = { class: "sc-nav" };
const _hoisted_10 = ["onClick"];
const _hoisted_11 = { class: "sc-nav-label" };
const _hoisted_12 = {
  key: 0,
  class: "sc-nav-badge"
};
const _hoisted_13 = { class: "sc-content" };
const _hoisted_14 = { class: "sc-cards" };
const _hoisted_15 = { class: "sc-stat-top" };
const _hoisted_16 = { class: "sc-stat-label" };
const _hoisted_17 = { class: "sc-stat-value" };
const _hoisted_18 = { class: "sc-stat-sub" };
const _hoisted_19 = {
  key: 0,
  class: "sc-card"
};
const _hoisted_20 = { class: "sc-card" };
const _hoisted_21 = { class: "sc-flow" };
const _hoisted_22 = { class: "sc-subtabs" };
const _hoisted_23 = { class: "sc-card" };
const _hoisted_24 = { class: "sc-row" };
const _hoisted_25 = { class: "sc-card" };
const _hoisted_26 = { class: "sc-card" };
const _hoisted_27 = { class: "sc-card-title" };
const _hoisted_28 = { class: "sc-card" };
const _hoisted_29 = { class: "sc-card-title" };
const _hoisted_30 = { class: "sc-row" };
const _hoisted_31 = {
  key: 1,
  class: "sc-card"
};
const _hoisted_32 = { class: "sc-list-head" };
const _hoisted_33 = { class: "sc-hint" };
const _hoisted_34 = ["onClick"];
const _hoisted_35 = ["onUpdate:modelValue"];
const _hoisted_36 = { class: "sc-db-name" };
const _hoisted_37 = {
  key: 0,
  class: "sc-db-tag"
};
const _hoisted_38 = { class: "sc-db-sum" };
const _hoisted_39 = {
  key: 0,
  class: "sc-db-body"
};
const _hoisted_40 = { class: "sc-card" };
const _hoisted_41 = { class: "sc-row" };
const _hoisted_42 = { class: "sc-card" };
const _hoisted_43 = { class: "sc-card" };
const _hoisted_44 = { class: "sc-card-title" };
const _hoisted_45 = { class: "sc-card" };
const _hoisted_46 = { class: "sc-row" };
const _hoisted_47 = { class: "sc-card" };
const _hoisted_48 = { class: "sc-card" };
const _hoisted_49 = { class: "sc-card-title" };
const _hoisted_50 = { class: "sc-card" };
const _hoisted_51 = { class: "sc-row" };
const _hoisted_52 = { class: "sc-card" };
const _hoisted_53 = { class: "sc-card-title" };
const _hoisted_54 = { class: "sc-card" };
const _hoisted_55 = { class: "sc-row" };
const _hoisted_56 = { class: "sc-card" };
const _hoisted_57 = { class: "sc-card-title" };
const _hoisted_58 = {
  key: 5,
  class: "sc-card"
};
const _hoisted_59 = { class: "sc-card-title" };
const _hoisted_60 = { class: "sc-hm-group" };
const _hoisted_61 = { class: "sc-hm-head" };
const _hoisted_62 = { class: "sc-hm-group" };
const _hoisted_63 = { class: "sc-hm-head" };
const _hoisted_64 = { class: "sc-card" };
const _hoisted_65 = { class: "sc-card-title" };
const _hoisted_66 = { class: "sc-hint" };
const _hoisted_67 = { class: "sc-hint" };
const _hoisted_68 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_69 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_70 = { class: "sc-row" };
const _hoisted_71 = { class: "sc-row" };
const _hoisted_72 = { class: "sc-row" };
const _hoisted_73 = {
  key: 1,
  class: "mt-2"
};
const _hoisted_74 = {
  key: 2,
  class: "sc-hint mt-1"
};
const _hoisted_75 = {
  key: 2,
  class: "sc-hint mt-2"
};
const _hoisted_76 = { class: "sc-card mt-3" };
const _hoisted_77 = {
  class: "d-flex align-center flex-wrap mt-2",
  style: {"gap":"8px"}
};
const _hoisted_78 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_79 = {
  key: 0,
  class: "sc-hint mt-2"
};
const _hoisted_80 = {
  key: 1,
  class: "sc-hint mt-1",
  style: {"color":"#f97373"}
};
const _hoisted_81 = {
  key: 2,
  class: "mt-2"
};
const _hoisted_82 = ["value"];
const _hoisted_83 = { style: {"font-weight":"600"} };
const _hoisted_84 = { class: "sc-hint" };
const _hoisted_85 = {
  key: 3,
  class: "sc-hint mt-2"
};
const _hoisted_86 = {
  key: 4,
  class: "mt-2"
};
const _hoisted_87 = { class: "sc-hint" };
const _hoisted_88 = {
  key: 7,
  class: "sc-card"
};
const _hoisted_89 = { class: "sc-row-main" };
const _hoisted_90 = { class: "sc-row-label" };
const _hoisted_91 = { class: "sc-row-hint" };
const _hoisted_92 = { class: "sc-row" };
const _hoisted_93 = {
  key: 8,
  class: "sc-card"
};
const _hoisted_94 = { class: "sc-row" };
const _hoisted_95 = { class: "sc-row" };
const _hoisted_96 = { class: "sc-row" };
const _hoisted_97 = { class: "sc-row" };
const _hoisted_98 = { class: "d-flex align-center flex-wrap ga-2" };
const _hoisted_99 = {
  key: 2,
  class: "mt-3"
};
const _hoisted_100 = {
  key: 3,
  class: "mt-3"
};
const _hoisted_101 = { class: "d-flex align-center flex-wrap ga-2 mb-2" };
const _hoisted_102 = { class: "sc-row" };
const _hoisted_103 = {
  key: 0,
  class: "sc-empty"
};
const _hoisted_104 = { class: "d-flex align-center flex-wrap ga-2" };
const _hoisted_105 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_106 = { class: "sc-hint" };
const _hoisted_107 = {
  key: 1,
  class: "sc-hint"
};
const _hoisted_108 = {
  key: 2,
  class: "sc-hint"
};
const _hoisted_109 = {
  key: 3,
  class: "sc-hint"
};
const _hoisted_110 = {
  key: 4,
  class: "sc-hint"
};
const _hoisted_111 = { class: "sc-hint" };
const _hoisted_112 = {
  key: 9,
  class: "sc-card"
};
const _hoisted_113 = { class: "sc-card-title sc-preview-head" };
const _hoisted_114 = { class: "sc-preview-action" };
const _hoisted_115 = {
  key: 0,
  class: "sc-empty"
};
const _hoisted_116 = { class: "d-flex align-center flex-wrap ga-2" };
const _hoisted_117 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_118 = {
  key: 1,
  class: "sc-hint"
};
const _hoisted_119 = {
  key: 2,
  class: "sc-hint"
};
const _hoisted_120 = { class: "sc-footer" };
const _hoisted_121 = { class: "sc-footer-right" };

const {computed,nextTick,onMounted,onUpdated,ref,watch} = await importShared('vue');


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
const doubanTab = ref('basic');
/** 豆瓣榜单里展开的那一条（-1 = 全部收起）。 */
const openList = ref(-1);
const activeSection = ref('overview');
/** 配置项搜索（分区太多，找一项要翻半天）。 */
const searchText = ref('');
/** 根元素：搜索时按 DOM 逐行显隐，比把 66 个字段重排成数据表更可靠。 */
const rootEl = ref(null);
/** 场景预设（后端 core/presets.py 提供，前端只负责点）。 */
const presets = ref([]);
const presetBusy = ref('');
/** 自动启停的预览/执行结果（null = 还没跑过）。 */
const autoToggle = ref(null);
const autoToggleBusy = ref('');
/** 默认只列出会改库的条目：两百条订阅全列出来没人看得下去。 */
const autoToggleShowAll = ref(false);

/** 动作常量 -> 中文标签（与后端 core/autotoggle.py 逐字对应）。 */
const ACTION_LABELS = {
  pause: '暂停',
  resume: '恢复',
  keep: '保持',
  skip: '跳过',
};
const ACTION_COLORS = {
  pause: 'warning',
  resume: 'success',
  keep: 'info',
  skip: 'default',
};

/** 电影的发行基准日类型 -> 中文（与 core/autotoggle.py 的 RELEASE_KIND_LABELS 对应）。 */
const RELEASE_KIND_LABELS = {
  digital: '数字发行',
  physical: '实体发行',
  theatrical: '影院上映',
  premiere: '首映',
  tv: '电视首播',
  general: '上映',
  estimated: '估算发行',
};

/** 洗版判定模式 -> 中文（与 constants.py 的 auto_toggle_best_version_mode 对应）。 */
const BEST_MODE_OPTIONS = [
  { title: '季终后才按洗版判（推荐）', value: 'after_finale' },
  { title: '播出期也算未洗到顶', value: 'always' },
];

const autoToggleItems = computed(() => {
  const data = autoToggle.value;
  if (!data) return []
  const items = Array.isArray(data.items) ? data.items : [];
  if (autoToggleShowAll.value) return items
  return items.filter((row) => row.action === 'pause' || row.action === 'resume')
});

/** 库核对的耗时/预算说明（预算为 0 时说明只读了快照）。 */
const libraryElapsedText = computed(() => {
  const lib = autoToggle.value?.library;
  if (!lib) return ''
  const budget = Number(lib.budget_seconds ?? 0);
  if (!budget) return '只读快照，零请求'
  const elapsed = Number(lib.elapsed ?? 0);
  return `${elapsed.toFixed(1)}s / 预算 ${budget}s`
});

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
  skipped_recorded: '流水已记录（不再自动订）',
  skipped_blacklist: '命中排除规则',
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
const IMPLEMENTED = ['tmdb', 'anilist', 'douban_rss', 'hot_media', 'qq_video', 'bilibili'];

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
    key: 'notify',
    label: '发送运行摘要通知',
    hint: '每次运行结束后推送一条汇总消息',
  },
];

const enabledSourceCount = computed(
  () => sourceRows.filter((row) => form.value[row.key]).length,
);

/** 开关行：enabled 在顶部栏单独渲染，reset_daily_counter 单独一行。 */
const switchRows = [
  {
    key: 'notify',
    label: '发送运行摘要通知',
    hint: '每次运行结束把「新增/跳过/失败」摘要发到 MoviePilot 通知渠道',
  },
  {
    key: 'dedupe_by_history',
    label: '发现流水记过的就不再自动订阅',
    hint:
      '流水里记着这部订阅过，就算你后来把订阅删了，也不会再自动订回来 —— ' +
      '想重新订就去「发现流水」里清空流水（或删掉那几条记录）',
  },
];

const sectionNav = computed(() => [
  { key: 'overview', label: '总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'tmdb', label: 'TMDB', icon: 'mdi-movie-open-outline' },
  { key: 'anilist', label: 'AniList', icon: 'mdi-animation-outline' },
  { key: 'douban', label: '豆瓣榜单', icon: 'mdi-movie-filter-outline' },
  { key: 'hot_media', label: '热门媒体', icon: 'mdi-fire' },
  { key: 'platform', label: '平台首播', icon: 'mdi-television-play' },
  { key: 'blacklist', label: '排除规则', icon: 'mdi-shield-off-outline' },
  { key: 'schedule', label: '写入与调度', icon: 'mdi-calendar-clock' },
  { key: 'autotoggle', label: '自动启停', icon: 'mdi-toggle-switch-outline' },
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
  if (!form.value.enabled) {
    list.push({ type: 'warning', text: '插件当前未启用，定时任务不会执行。' });
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

/** 热门媒体的风格选项（TMDB genre id）。 */
const MOVIE_GENRES = [
  { title: '动作', value: 28 },
  { title: '冒险', value: 12 },
  { title: '动画', value: 16 },
  { title: '喜剧', value: 35 },
  { title: '犯罪', value: 80 },
  { title: '纪录', value: 99 },
  { title: '剧情', value: 18 },
  { title: '家庭', value: 10751 },
  { title: '奇幻', value: 14 },
  { title: '历史', value: 36 },
  { title: '恐怖', value: 27 },
  { title: '音乐', value: 10402 },
  { title: '悬疑', value: 9648 },
  { title: '爱情', value: 10749 },
  { title: '科幻', value: 878 },
  { title: '惊悚', value: 53 },
  { title: '战争', value: 10752 },
  { title: '西部', value: 37 },
];

const TV_GENRES = [
  { title: '动作冒险', value: 10759 },
  { title: '动画', value: 16 },
  { title: '喜剧', value: 35 },
  { title: '犯罪', value: 80 },
  { title: '纪录', value: 99 },
  { title: '剧情', value: 18 },
  { title: '家庭', value: 10751 },
  { title: '儿童', value: 10762 },
  { title: '悬疑', value: 9648 },
  { title: '新闻', value: 10763 },
  { title: '真人秀', value: 10764 },
  { title: '科幻奇幻', value: 10765 },
  { title: '肥皂剧', value: 10766 },
  { title: '脱口秀', value: 10767 },
  { title: '战争政治', value: 10768 },
  { title: '西部', value: 37 },
];

/** 宿主的「订阅数据共享」开关（热门媒体依赖它）。 */
const shareEnabled = ref(false);
ref(false);

async function loadShare() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'system_share'));
    shareEnabled.value = Boolean(data?.enabled);
  } catch (error) {
    /* 读取失败不影响其它配置 */
  }
}

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

/** 拉预设清单（后端描述文案，前端不重复维护）。 */
async function loadPresets() {
  try {
    const payload = unwrap(await getPluginApi(props.api, props.pluginId, 'presets'));
    presets.value = payload?.items || [];
  } catch (error) {
    console.warn('[SubscribeCenter] 预设清单读取失败：', error?.message || error);
  }
}

/** 套用一个场景预设：后端改配置，前端重新读一遍表单。 */
async function applyPreset(name) {
  if (presetBusy.value) return
  const label = name === 'reset' ? '恢复默认' : (presets.value.find((p) => p.key === name)?.title || name);
  if (!window.confirm(`套用「${label}」？\n\n只会改动和追剧范围相关的项，RSSHub 域名、定时、通知不会被改。`)) return
  presetBusy.value = name;
  try {
    const result = unwrap(
      await postPluginApi(props.api, props.pluginId, 'presets/apply', { name }),
    );
    if (result?.config) form.value = mergeConfig(result.config);
    else await loadConfig();
    setTip(`已套用「${result?.title || label}」，改动 ${result?.changed ?? 0} 项（记得保存）`);
  } catch (error) {
    setTip(error?.message || '套用预设失败', false);
  } finally {
    presetBusy.value = '';
  }
}

/** 按搜索词显隐配置行：命中不了的行直接隐藏，分区里空了就整块收起。 */
async function applySearchFilter() {
  await nextTick();
  const root = rootEl.value;
  if (!root) return
  const query = searchText.value.trim().toLowerCase();
  const blocks = root.querySelectorAll('.sc-row, .sc-field, .sc-db-item, .sc-oj-item');
  blocks.forEach((node) => {
    if (!query) {
      node.classList.remove('sc-filtered');
      return
    }
    const hit = String(node.textContent || '').toLowerCase().includes(query);
    node.classList.toggle('sc-filtered', !hit);
  });
  root.querySelectorAll('.sc-card').forEach((card) => {
    if (!query) {
      card.classList.remove('sc-filtered');
      return
    }
    const rows = card.querySelectorAll('.sc-row, .sc-field, .sc-db-item, .sc-oj-item');
    const visible = Array.from(rows).some((row) => !row.classList.contains('sc-filtered'));
    card.classList.toggle('sc-filtered', rows.length > 0 && !visible);
  });
}

watch(searchText, () => applySearchFilter());
watch(activeSection, () => applySearchFilter());
onUpdated(() => {
  if (searchText.value.trim()) applySearchFilter();
});

/** 榜单顺序就是优先级（靠前的先花每日额度），所以要能上下移。 */
function moveDoubanList(index, delta) {
  const list = form.value.douban_rss_sources;
  if (!Array.isArray(list)) return
  const target = index + delta;
  if (target < 0 || target >= list.length) return
  const [row] = list.splice(index, 1);
  list.splice(target, 0, row);
  openList.value = target;
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
    const start = unwrap(
      await postPluginApi(props.api, props.pluginId, 'run_once', {}, { timeoutMs: 60000 }),
    );
    if (!start?.started) {
      setTip(start?.message || '已有发现任务正在运行，本次跳过');
      return
    }
    setTip('已在后台开始执行，正在等结果（可能要一两分钟）…');
    const result = await waitTaskDone('run_once/result');
    const s = result?.summary || {};
    setTip(
      `本次完成：拉取 ${s.fetched ?? 0} 条 / 新增 ${s.added ?? 0} 条 / `
        + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`
        ,
    );
    await loadStatus();
  } catch (error) {
    setTip(error?.message || '运行失败', false);
  } finally {
    busy.value = '';
  }
}

/**
 * 轮询后台任务直到跑完。
 *
 * 预览与「立即运行一次」都要跑一两分钟（拉四个源 + 逐条解析），而宿主
 * 前面的网关几十秒就断——同步等只会拿到 HTTP 502。所以后端那两个接口
 * 只负责「启动」，结果一律靠这里轮询 /…/result 取。
 */
async function waitTaskDone(path, { intervalMs = 4000, maxTries = 450 } = {}) {
  for (let i = 0; i < maxTries; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    const state = unwrap(
      await getPluginApi(props.api, props.pluginId, path, { timeoutMs: 60000 }),
    );
    if (state?.error) throw new Error(state.error)
    if (!state?.running) return state?.result || {}
  }
  throw new Error('等待超时：任务可能还在后台跑，稍后回到这一页看状态')
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
    const start = unwrap(
      await postPluginApi(props.api, props.pluginId, 'preview', {}, { timeoutMs: 60000 }),
    );
    if (!start?.started) {
      setTip(start?.message || '已有发现任务正在运行，本次跳过');
      return
    }
    setTip('预览已在后台开始，正在等结果（首次可能要一两分钟）…');
    const result = await waitTaskDone('preview/result');
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

function autoToggleCronValid() {
  return String(form.value.auto_toggle_cron || '').trim().split(/\s+/).length === 5
}

/**
 * 待处理集号的中文说明。
 *
 * 洗版订阅的 pending 不是「缺集」，而是「还没洗到顶」（已下 1080、还在等更好
 * 的版本），用「缺」会让用户以为 PT 上没资源。所以按原因码分两种说法。
 */
function pendingText(row) {
  const list = row?.pending || [];
  if (!list.length) return ''
  const label = String(row.reason || '').startsWith('best_') ? '待升级' : '缺';
  const head = list.slice(0, 12).join(', ');
  const tail = list.length > 12 ? ` 等 ${list.length} 集` : ' 集';
  // 缺集是「推测」的：订阅没有入库记录时，只能拿播出表减 note 得到。
  // 不写清楚的话，用户会以为插件在说「这些集你真没下」。
  if (row?.assumed) {
    return `${label} ${head}${tail}（推测：订阅没有入库记录，这些集可能不是通过订阅下的）`
  }
  return `${label} ${head}${tail}`
}

/**
 * 自动启停：GET 只算不写。
 *
 * 判定的依据是「今天到底有没有该搜的集」，所以这一步会去查 TMDB 播出表，
 * 首次可能要十几秒（之后走 6 小时缓存）。改参数后先看这一步。
 */
async function loadAutoToggle() {
  if (autoToggleBusy.value) return
  autoToggleBusy.value = 'preview';
  try {
    const data = unwrap(
      await getPluginApi(props.api, props.pluginId, 'auto_toggle', { timeoutMs: 600000 }),
    );
    autoToggle.value = data || null;
    setTip(
      `预览完成（未改动任何订阅）：待暂停 ${data?.paused ?? 0} 条 / `
        + `待恢复 ${data?.resumed ?? 0} 条 / 保持不动 ${data?.kept ?? 0} 条`,
    );
  } catch (error) {
    setTip(error?.message || '预览失败', false);
  } finally {
    autoToggleBusy.value = '';
  }
}

/**
 * 真正改状态：**在后台跑**，接口立刻返回，然后轮询进度。
 *
 * 真机教训：核对媒体库要串行跑几分钟，放在请求里会被网关 502 掐断，
 * 用户只看到一个「请求被网关中断」。所以执行改成后台线程 + 轮询。
 */
async function applyAutoToggle() {
  if (autoToggleBusy.value) return
  if (!window.confirm('将按播出日暂停/恢复订阅状态（含媒体库核对，可能跑几分钟），确定执行？')) return
  autoToggleBusy.value = 'apply';
  try {
    const start = unwrap(
      await postPluginApi(
        props.api,
        props.pluginId,
        'auto_toggle/apply',
        {},
        { timeoutMs: 60000 },
      ),
    );
    setTip(start?.message || '已在后台开始执行');
    const data = await waitAutoToggleDone();
    const last = data?.last_run || {};
    const failed = Number(last.failed || 0);
    setTip(
      `已执行：暂停 ${last.paused ?? 0} 条 / 恢复 ${last.resumed ?? 0} 条`
        + (failed ? ` / 失败 ${failed} 条（详见运行日志）` : ''),
      !failed,
    );
    await loadStatus();
  } catch (error) {
    setTip(error?.message || '执行失败', false);
  } finally {
    autoToggleBusy.value = '';
  }
}

/** 轮询后台执行是否结束，顺便把预览数据刷新一遍。 */
async function waitAutoToggleDone() {
  for (let i = 0; i < 600; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    const data = unwrap(
      await getPluginApi(props.api, props.pluginId, 'auto_toggle', { timeoutMs: 120000 }),
    );
    autoToggle.value = data || null;
    if (!data?.last_run?.running) return data
    setTip(`后台执行中…（已 ${(i + 1) * 3} 秒，核对媒体库是按条串行的）`);
  }
  return autoToggle.value
}

/** 排除规则元数据（内置题材预设 + 类型中文名）。 */
const blacklistMeta = ref(null);
/** 排除规则自测表单与结果。 */
const blacklistTestForm = ref({ title: '', tags: '', media_type: 'tv' });
const blacklistTestResult = ref(null);
const blacklistTestBusy = ref(false);

/** 内置题材预设（后端下发，勾选后才生效）。 */
const blacklistPresets = computed(() => blacklistMeta.value?.presets || []);

/** 某个预设会匹配哪些词（勾选后原样摊给用户看，不藏着）。 */
function presetWords(key) {
  const preset = blacklistPresets.value.find((entry) => entry.key === key);
  return preset ? preset.words : []
}

/** 当前生效的规则条数（0 = 黑名单等于没开）。 */
const blacklistRuleCount = computed(() => {
  const genres = (form.value.blacklist_genre_movie || []).length
    + (form.value.blacklist_genre_tv || []).length;
  const lines = String(form.value.blacklist_words || '')
    .split('\n')
    .filter((line) => line.trim()).length;
  return genres + (form.value.blacklist_presets || []).length + lines
});

async function loadBlacklistMeta() {
  try {
    blacklistMeta.value = unwrap(
      await getPluginApi(props.api, props.pluginId, 'blacklist'),
    ) || null;
  } catch (error) {
    // 元数据拿不到不影响表单本身：类型下拉用的是本地常量表
    blacklistMeta.value = null;
  }
}

/** 拿一段片名/题材串试一下，看会不会被自己的规则拦掉。 */
async function runBlacklistTest() {
  if (blacklistTestBusy.value) return
  blacklistTestBusy.value = true;
  try {
    blacklistTestResult.value = unwrap(
      await postPluginApi(props.api, props.pluginId, 'blacklist/test', {
        title: blacklistTestForm.value.title || '',
        original_title: '',
        media_type: blacklistTestForm.value.media_type || 'tv',
        tags: blacklistTestForm.value.tags || '',
        genre_ids: [],
        keywords: [],
        // 用页面上**当前填的**规则（可能还没保存）—— 自测只认已保存配置的话，
        // 勾完预设不点保存就会得到「不会被拦」，会被当成功能坏了。
        rules: {
          blacklist_enabled: !!form.value.blacklist_enabled,
          blacklist_genre_movie: form.value.blacklist_genre_movie || [],
          blacklist_genre_tv: form.value.blacklist_genre_tv || [],
          blacklist_presets: form.value.blacklist_presets || [],
          blacklist_words: form.value.blacklist_words || '',
          blacklist_match_title: !!form.value.blacklist_match_title,
          blacklist_match_tags: !!form.value.blacklist_match_tags,
          blacklist_tmdb_keywords: !!form.value.blacklist_tmdb_keywords,
        },
      }),
    ) || null;
  } catch (error) {
    blacklistTestResult.value = null;
    setTip(error?.message || '自测失败', false);
  } finally {
    blacklistTestBusy.value = false;
  }
}

// ---------------------------------------------------------------- 体检已有订阅
//
// 用户真机遇到的现象：勾好黑名单、流水里也写着「命中排除题材」，宿主的订阅
// 列表里却确实有这部剧。原因是排除规则只挂在「自动发现 → 写订阅」这条线上，
// 已经存在的订阅（早先订的、重装后数据库带回来的、或从流水手动点「加入订阅」
// 的）它一概不管。体检就是补这一刀：按同一套规则把已有订阅判一遍，只出报告，
// 暂停与否由用户自己勾。

const audit = ref(null);            // { running, started_at, result }
const auditBusy = ref(false);
const auditSelected = ref([]);
const auditDone = ref(false);
const auditHits = computed(() => audit.value?.result?.hits || []);
const auditUncheckable = computed(() => audit.value?.result?.uncheckable || []);
const auditStats = computed(() => {
  const data = audit.value?.result;
  if (!data || !data.total) return ''
  const parts = [
    `共 ${data.total} 条订阅`,
    `核对成功 ${data.checked}`,
    `命中 ${(data.hits || []).length}`,
  ];
  if (data.skipped) parts.push(`核不了 ${data.skipped}`);
  if (data.unchecked) parts.push(`未覆盖 ${data.unchecked}`);
  if (data.elapsed) parts.push(`耗时 ${data.elapsed}s`);
  return parts.join(' · ')
});

async function fetchAudit() {
  const state = unwrap(
    await getPluginApi(props.api, props.pluginId, 'blacklist/audit/result', {
      timeoutMs: 60000,
    }),
  );
  audit.value = state || null;
  return state
}

async function waitAuditDone() {
  for (let i = 0; i < 300; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    const state = await fetchAudit();
    if (!state?.running) return state
    // eslint-disable-next-line no-await-in-loop
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  return null
}

async function runBlacklistAudit() {
  if (auditBusy.value) return
  auditBusy.value = true;
  auditDone.value = false;
  auditSelected.value = [];
  try {
    const start = unwrap(
      await postPluginApi(props.api, props.pluginId, 'blacklist/audit', {}, {
        timeoutMs: 60000,
      }),
    );
    setTip(start?.message || '已开始体检，正在核对已有订阅');
    const state = await waitAuditDone();
    if (!state) {
      setTip('体检还没跑完，稍后再点一次「读结果」', false);
      return
    }
    auditDone.value = true;
    auditSelected.value = (state.result?.hits || []).map((hit) => hit.id);
    const hits = state.result?.hits || [];
    setTip(
      hits.length
        ? `体检完成：${hits.length} 条已有订阅命中排除规则，已默认勾选，点「暂停选中」处理`
        : '体检完成：没有已有订阅命中排除规则',
      hits.length === 0,
    );
  } catch (error) {
    setTip(error?.message || '体检失败', false);
  } finally {
    auditBusy.value = false;
  }
}

async function sweepAudit(action) {
  if (auditBusy.value || !auditSelected.value.length) return
  const verb = action === 'pause' ? '暂停' : '恢复';
  if (!window.confirm(`确定要${verb}选中的 ${auditSelected.value.length} 条订阅？`)) return
  auditBusy.value = true;
  try {
    const data = unwrap(
      await postPluginApi(
        props.api,
        props.pluginId,
        'blacklist/sweep',
        { ids: auditSelected.value, action },
        { timeoutMs: 120000 },
      ),
    );
    const failed = data?.failed || 0;
    setTip(
      `已${verb} ${data?.applied || 0} 条${failed ? `，${failed} 条失败` : ''}`,
      failed === 0,
    );
    auditSelected.value = [];
    await loadStatus();
  } catch (error) {
    setTip(error?.message || `${verb}失败`, false);
  } finally {
    auditBusy.value = false;
  }
}

onMounted(() => {
  loadPresets();
  loadShare();
  loadConfig();
  loadStatus();
  loadBlacklistMeta();
});

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCheckbox = _resolveComponent("VCheckbox");
  const _component_VTextarea = _resolveComponent("VTextarea");

  return (_openBlock(), _createElementBlock("div", {
    ref_key: "rootEl",
    ref: rootEl,
    class: "sc-root"
  }, [
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
    _createElementVNode("div", _hoisted_1, [
      _createElementVNode("div", _hoisted_2, [
        _createElementVNode("div", _hoisted_3, [
          _createVNode(_component_VIcon, {
            icon: "mdi-movie-open-star-outline",
            size: "22"
          })
        ]),
        _createElementVNode("div", null, [
          _createElementVNode("div", _hoisted_4, [
            _cache[83] || (_cache[83] = _createTextVNode(" 胖虎订阅中心 ", -1)),
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
          _cache[84] || (_cache[84] = _createElementVNode("div", { class: "sc-subtitle" }, " 发现片源 → 解析身份 → 去重 → 写订阅。版本控制与洗版由 MoviePilot 接管，本插件不介入。 ", -1))
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
    _createElementVNode("div", _hoisted_5, [
      _createElementVNode("div", _hoisted_6, [
        _cache[86] || (_cache[86] = _createElementVNode("span", { class: "sc-cfg-presets-label" }, "一键配置", -1)),
        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(presets.value, (preset) => {
          return (_openBlock(), _createBlock(_component_VBtn, {
            key: preset.key,
            size: "small",
            variant: "tonal",
            loading: presetBusy.value === preset.key,
            disabled: Boolean(presetBusy.value),
            title: preset.desc,
            onClick: $event => (applyPreset(preset.key))
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(preset.title), 1)
            ]),
            _: 2
          }, 1032, ["loading", "disabled", "title", "onClick"]))
        }), 128)),
        _createVNode(_component_VBtn, {
          size: "small",
          variant: "text",
          loading: presetBusy.value === 'reset',
          disabled: Boolean(presetBusy.value),
          onClick: _cache[2] || (_cache[2] = $event => (applyPreset('reset')))
        }, {
          default: _withCtx(() => [...(_cache[85] || (_cache[85] = [
            _createTextVNode(" 恢复默认 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "disabled"]),
        _cache[87] || (_cache[87] = _createElementVNode("span", { class: "sc-hint sc-cfg-presets-hint" }, " 只改「追什么」，RSSHub 域名 / 定时 / 通知不动 ", -1))
      ]),
      _createElementVNode("div", _hoisted_7, [
        _createVNode(_component_VIcon, {
          icon: "mdi-magnify",
          size: "16",
          class: "sc-dim"
        }),
        _withDirectives(_createElementVNode("input", {
          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((searchText).value = $event)),
          class: "sc-cfg-search-input",
          type: "text",
          placeholder: "搜配置项（窗口 / 想看 / cron…）"
        }, null, 512), [
          [_vModelText, searchText.value]
        ]),
        (searchText.value)
          ? (_openBlock(), _createBlock(_component_VBtn, {
              key: 0,
              size: "x-small",
              variant: "text",
              icon: "mdi-close",
              onClick: _cache[4] || (_cache[4] = $event => (searchText.value = ''))
            }))
          : _createCommentVNode("", true)
      ])
    ]),
    _createElementVNode("div", _hoisted_8, [
      _createElementVNode("nav", _hoisted_9, [
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
            _createElementVNode("span", _hoisted_11, _toDisplayString(item.label), 1),
            (item.badge)
              ? (_openBlock(), _createElementBlock("span", _hoisted_12, _toDisplayString(item.badge), 1))
              : _createCommentVNode("", true)
          ], 10, _hoisted_10))
        }), 128))
      ]),
      _createElementVNode("section", _hoisted_13, [
        (activeSection.value === 'overview')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
              _createElementVNode("div", _hoisted_14, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overviewCards.value, (card) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: card.label,
                    class: "sc-stat"
                  }, [
                    _createElementVNode("div", _hoisted_15, [
                      _createVNode(_component_VIcon, {
                        icon: card.icon,
                        size: "18",
                        color: card.color
                      }, null, 8, ["icon", "color"]),
                      _createElementVNode("span", _hoisted_16, _toDisplayString(card.label), 1)
                    ]),
                    _createElementVNode("div", _hoisted_17, _toDisplayString(card.value), 1),
                    _createElementVNode("div", _hoisted_18, _toDisplayString(card.sub), 1)
                  ]))
                }), 128))
              ]),
              (overviewAlerts.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_19, [
                    _cache[88] || (_cache[88] = _createElementVNode("div", { class: "sc-card-title" }, "需要注意", -1)),
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
              _createElementVNode("div", _hoisted_20, [
                _cache[95] || (_cache[95] = _createElementVNode("div", { class: "sc-card-title" }, "运行链路", -1)),
                _createElementVNode("div", _hoisted_21, [
                  _cache[89] || (_cache[89] = _createElementVNode("span", { class: "sc-flow-node" }, "拉取候选", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[90] || (_cache[90] = _createElementVNode("span", { class: "sc-flow-node" }, "身份解析", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[91] || (_cache[91] = _createElementVNode("span", { class: "sc-flow-node" }, "季号裁决", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[92] || (_cache[92] = _createElementVNode("span", { class: "sc-flow-node" }, "阈值过滤", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[93] || (_cache[93] = _createElementVNode("span", { class: "sc-flow-node" }, "去重", -1)),
                  _createVNode(_component_VIcon, {
                    icon: "mdi-arrow-right",
                    size: "14"
                  }),
                  _cache[94] || (_cache[94] = _createElementVNode("span", { class: "sc-flow-node sc-flow-accent" }, "写订阅", -1))
                ]),
                _cache[96] || (_cache[96] = _createElementVNode("div", { class: "sc-hint mt-2" }, " 季号由 TMDB 的真实数据裁决（哪一季还有未播集），不猜豆瓣/Bangumi 的命名含义。 ", -1))
              ])
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'douban')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
              _createElementVNode("div", _hoisted_22, [
                _createElementVNode("button", {
                  type: "button",
                  class: _normalizeClass(["sc-subtab", { 'sc-subtab-active': doubanTab.value === 'basic' }]),
                  onClick: _cache[5] || (_cache[5] = $event => (doubanTab.value = 'basic'))
                }, " 豆瓣 RSS ", 2),
                _createElementVNode("button", {
                  type: "button",
                  class: _normalizeClass(["sc-subtab", { 'sc-subtab-active': doubanTab.value === 'routes' }]),
                  onClick: _cache[6] || (_cache[6] = $event => (doubanTab.value = 'routes'))
                }, " 豆瓣榜单 ", 2)
              ]),
              (doubanTab.value === 'basic')
                ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    _createElementVNode("div", _hoisted_23, [
                      _createElementVNode("div", _hoisted_24, [
                        _cache[97] || (_cache[97] = _createElementVNode("div", { class: "sc-row-main" }, [
                          _createElementVNode("div", { class: "sc-row-label" }, "启用豆瓣 RSS"),
                          _createElementVNode("div", { class: "sc-row-hint" }, "经 RSSHub 的豆瓣路线发现；下面每条榜单可独立配置")
                        ], -1)),
                        _createVNode(_component_VSwitch, {
                          modelValue: form.value.enable_douban_rss,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((form.value.enable_douban_rss) = $event)),
                          density: "compact",
                          "hide-details": "",
                          color: "primary"
                        }, null, 8, ["modelValue"])
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_25, [
                      _cache[98] || (_cache[98] = _createElementVNode("div", { class: "sc-card-title" }, "独立定时（豆瓣）", -1)),
                      _createVNode(_component_VTextField, {
                        modelValue: form.value.cron_douban_rss,
                        "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((form.value.cron_douban_rss) = $event)),
                        label: "五位 cron，留空=跟随全局定时",
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        placeholder: "例：0 8 * * *",
                        class: "mb-1"
                      }, null, 8, ["modelValue"]),
                      _cache[99] || (_cache[99] = _createElementVNode("div", { class: "sc-hint" }, "留空则跟随「写入与调度」里的全局 cron；填了就会单独按这个时间跑该源。", -1))
                    ]),
                    _createElementVNode("div", _hoisted_26, [
                      _createElementVNode("div", _hoisted_27, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-movie-filter-outline",
                          size: "16"
                        }),
                        _cache[100] || (_cache[100] = _createTextVNode(" 豆瓣 RSS ", -1))
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
                                "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((form.value.douban_future_days) = $event)),
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
                                "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((form.value.min_rating_douban) = $event)),
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
                                "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((form.value.douban_min_want) = $event)),
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
                                "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((form.value.douban_max_items_per_feed) = $event)),
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
                                "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((form.value.resolve_concurrency) = $event)),
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
                      _cache[101] || (_cache[101] = _createElementVNode("div", { class: "sc-hint" }, [
                        _createTextVNode(" 豆瓣窗口独立于 TMDB（「即将上映」是策展列表，可以放宽）。想看人数只有 coming 类路线提供， 榜单类没有该数据，"),
                        _createElementVNode("b", null, "缺失时不拦"),
                        _createTextVNode("。候选多不需要手动减 —— 解析是并发的， 实测 260 条约 20~30 秒。 ")
                      ], -1))
                    ]),
                    _createElementVNode("div", _hoisted_28, [
                      _createElementVNode("div", _hoisted_29, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-check-decagram-outline",
                          size: "16"
                        }),
                        _cache[102] || (_cache[102] = _createTextVNode(" 订阅行为 ", -1))
                      ]),
                      _createElementVNode("div", _hoisted_30, [
                        _cache[103] || (_cache[103] = _createElementVNode("div", { class: "sc-row-main" }, [
                          _createElementVNode("div", { class: "sc-row-label" }, "用 TMDB 分组精确订阅被压成单季的番剧"),
                          _createElementVNode("div", { class: "sc-row-hint" }, [
                            _createTextVNode(" 如《药屋少女的呢喃》= 1 季 60 集，第 49~60 集才是第 3 季。开启后只订那 12 集， "),
                            _createElementVNode("b", null, "不会去补前 48 集旧番"),
                            _createTextVNode("。 ")
                          ])
                        ], -1)),
                        _createVNode(_component_VSwitch, {
                          modelValue: form.value.prefer_episode_group,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((form.value.prefer_episode_group) = $event)),
                          density: "compact",
                          "hide-details": "",
                          color: "primary"
                        }, null, 8, ["modelValue"])
                      ])
                    ])
                  ], 64))
                : _createCommentVNode("", true),
              (doubanTab.value === 'routes')
                ? (_openBlock(), _createElementBlock("div", _hoisted_31, [
                    _cache[106] || (_cache[106] = _createElementVNode("div", { class: "sc-card-title" }, "豆瓣 RSS 路线", -1)),
                    _createVNode(_component_VTextField, {
                      modelValue: form.value.rsshub_domain,
                      "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((form.value.rsshub_domain) = $event)),
                      label: "RSSHub 域名（总控）",
                      density: "compact",
                      "hide-details": "",
                      variant: "outlined",
                      placeholder: "http://192.168.50.134:1200",
                      class: "mb-2",
                      disabled: !form.value.enable_douban_rss
                    }, null, 8, ["modelValue", "disabled"]),
                    _cache[107] || (_cache[107] = _createElementVNode("div", { class: "sc-hint mb-2" }, [
                      _createTextVNode(" 每条榜单只填**路由**（如 "),
                      _createElementVNode("code", null, "/douban/movie/coming"),
                      _createTextVNode("）， 实际请求 = 域名 + 路由。换 RSSHub 地址只改这里，不用逐条改。 ")
                    ], -1)),
                    _createElementVNode("div", _hoisted_32, [
                      _createElementVNode("span", _hoisted_33, "已启用 " + _toDisplayString(doubanEnabledCount.value) + " / " + _toDisplayString(doubanLists.value.length) + " 条", 1),
                      _createVNode(_component_VBtn, {
                        size: "x-small",
                        variant: "tonal",
                        "prepend-icon": "mdi-plus",
                        onClick: addDoubanList
                      }, {
                        default: _withCtx(() => [...(_cache[104] || (_cache[104] = [
                          _createTextVNode(" 添加榜单 ", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(doubanLists.value, (entry, index) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: index,
                        class: _normalizeClass(["sc-db-item", { 'sc-db-off': !entry.enabled }])
                      }, [
                        _createElementVNode("div", {
                          class: "sc-db-head",
                          onClick: $event => (openList.value = openList.value === index ? -1 : index)
                        }, [
                          _createVNode(_component_VIcon, {
                            icon: openList.value === index ? 'mdi-chevron-down' : 'mdi-chevron-right',
                            size: "18",
                            class: "sc-db-chevron"
                          }, null, 8, ["icon"]),
                          _withDirectives(_createElementVNode("input", {
                            type: "checkbox",
                            "onUpdate:modelValue": $event => ((entry.enabled) = $event),
                            onClick: _cache[16] || (_cache[16] = _withModifiers(() => {}, ["stop"]))
                          }, null, 8, _hoisted_35), [
                            [_vModelCheckbox, entry.enabled]
                          ]),
                          _createElementVNode("span", _hoisted_36, _toDisplayString(entry.name || '未命名榜单'), 1),
                          (!entry.enabled)
                            ? (_openBlock(), _createElementBlock("span", _hoisted_37, "未启用"))
                            : _createCommentVNode("", true),
                          _cache[105] || (_cache[105] = _createElementVNode("span", { class: "sc-db-spacer" }, null, -1)),
                          _createVNode(_component_VBtn, {
                            size: "x-small",
                            variant: "text",
                            icon: "mdi-arrow-up",
                            title: "上移（靠前的优先花每日额度）",
                            disabled: index === 0,
                            onClick: _withModifiers($event => (moveDoubanList(index, -1)), ["stop"])
                          }, null, 8, ["disabled", "onClick"]),
                          _createVNode(_component_VBtn, {
                            size: "x-small",
                            variant: "text",
                            icon: "mdi-arrow-down",
                            title: "下移",
                            disabled: index === doubanLists.value.length - 1,
                            onClick: _withModifiers($event => (moveDoubanList(index, 1)), ["stop"])
                          }, null, 8, ["disabled", "onClick"]),
                          _createElementVNode("span", _hoisted_38, " 数量 " + _toDisplayString(entry.max_items || '全局') + " · 窗口 " + _toDisplayString(entry.future_days || '全局') + " 天 · 想看 " + _toDisplayString(entry.min_want || '不限'), 1),
                          _createVNode(_component_VBtn, {
                            size: "x-small",
                            variant: "text",
                            color: "error",
                            icon: "mdi-delete-outline",
                            onClick: _withModifiers($event => (removeDoubanList(index)), ["stop"])
                          }, null, 8, ["onClick"])
                        ], 8, _hoisted_34),
                        (openList.value === index)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_39, [
                              _createVNode(_component_VTextField, {
                                modelValue: entry.url,
                                "onUpdate:modelValue": $event => ((entry.url) = $event),
                                label: "RSSHub 路由或完整 URL",
                                density: "compact",
                                "hide-details": "",
                                variant: "outlined",
                                placeholder: "/douban/movie/coming",
                                class: "mb-2"
                              }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                              _createVNode(_component_VRow, { dense: "" }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VCol, {
                                    cols: "6",
                                    sm: "3"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VTextField, {
                                        modelValue: entry.name,
                                        "onUpdate:modelValue": $event => ((entry.name) = $event),
                                        label: "名称",
                                        density: "compact",
                                        "hide-details": "",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_VCol, {
                                    cols: "6",
                                    sm: "3"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VTextField, {
                                        modelValue: entry.max_items,
                                        "onUpdate:modelValue": $event => ((entry.max_items) = $event),
                                        modelModifiers: { number: true },
                                        label: "每榜条数",
                                        type: "number",
                                        min: "1",
                                        max: "200",
                                        density: "compact",
                                        "hide-details": "",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_VCol, {
                                    cols: "6",
                                    sm: "3"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VTextField, {
                                        modelValue: entry.future_days,
                                        "onUpdate:modelValue": $event => ((entry.future_days) = $event),
                                        modelModifiers: { number: true },
                                        label: "窗口天数（0=全局）",
                                        type: "number",
                                        min: "0",
                                        max: "120",
                                        density: "compact",
                                        "hide-details": "",
                                        variant: "outlined"
                                      }, null, 8, ["modelValue", "onUpdate:modelValue"])
                                    ]),
                                    _: 2
                                  }, 1024),
                                  _createVNode(_component_VCol, {
                                    cols: "6",
                                    sm: "3"
                                  }, {
                                    default: _withCtx(() => [
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
                                    ]),
                                    _: 2
                                  }, 1024)
                                ]),
                                _: 2
                              }, 1024)
                            ]))
                          : _createCommentVNode("", true)
                      ], 2))
                    }), 128)),
                    _cache[108] || (_cache[108] = _createStaticVNode("<div class=\"sc-hint mt-2\" data-v-25babbac><b data-v-25babbac>电影上映类</b>（<code data-v-25babbac>/douban/movie/coming</code>）带精确上映日期，按窗口过滤，最准。<br data-v-25babbac><b data-v-25babbac>剧集类</b>（<code data-v-25babbac>/douban/tv/coming</code>、<code data-v-25babbac>/douban/list/tv_*</code>、 <code data-v-25babbac>/douban/list/show_domestic</code>）没有日期，按「TMDB 还有没有未播集」判断，等效追番。<br data-v-25babbac><b data-v-25babbac>电影榜单类</b>没有日期，会被跳过。<code data-v-25babbac>ustop250</code> 与 <code data-v-25babbac>/douban/movie/new</code> 在新版 RSSHub 已 404。 </div>", 1))
                  ]))
                : _createCommentVNode("", true)
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'tmdb')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
              _createElementVNode("div", _hoisted_40, [
                _createElementVNode("div", _hoisted_41, [
                  _cache[109] || (_cache[109] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "启用 TMDB 数据源"),
                    _createElementVNode("div", { class: "sc-row-hint" }, "TMDB 即将上映 / 热门发现（电影与剧集）")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.enable_tmdb,
                    "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((form.value.enable_tmdb) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ])
              ]),
              _createElementVNode("div", _hoisted_42, [
                _cache[110] || (_cache[110] = _createElementVNode("div", { class: "sc-card-title" }, "独立定时（TMDB）", -1)),
                _createVNode(_component_VTextField, {
                  modelValue: form.value.cron_tmdb,
                  "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((form.value.cron_tmdb) = $event)),
                  label: "五位 cron，留空=跟随全局定时",
                  density: "compact",
                  "hide-details": "",
                  variant: "outlined",
                  placeholder: "例：0 8 * * *",
                  class: "mb-1"
                }, null, 8, ["modelValue"]),
                _cache[111] || (_cache[111] = _createElementVNode("div", { class: "sc-hint" }, "留空则跟随「写入与调度」里的全局 cron；填了就会单独按这个时间跑该源。", -1))
              ]),
              _createElementVNode("div", _hoisted_43, [
                _createElementVNode("div", _hoisted_44, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-movie-open-outline",
                    size: "16"
                  }),
                  _cache[112] || (_cache[112] = _createTextVNode(" TMDB ", -1))
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
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((form.value.tmdb_future_days) = $event)),
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
                          "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((form.value.min_rating_tmdb) = $event)),
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
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((form.value.min_popularity) = $event)),
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
                _cache[113] || (_cache[113] = _createElementVNode("div", { class: "sc-hint" }, [
                  _createTextVNode(" 只保留「今天 ~ 今天 + N 天」内的定档条目。"),
                  _createElementVNode("b", null, "最低关注度"),
                  _createTextVNode("是新片唯一可用的质量信号 （观众级大片 100+、院线片 10~50、冷门片 <5），设 0 表示不过滤。 ")
                ], -1)),
                _createVNode(_component_VDivider, { class: "my-3" }),
                _createVNode(_component_VSwitch, {
                  modelValue: form.value.filter_original_language,
                  "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((form.value.filter_original_language) = $event)),
                  label: "只保留指定原始语言的条目",
                  density: "compact",
                  "hide-details": "",
                  color: "primary"
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: form.value.tmdb_original_languages,
                  "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((form.value.tmdb_original_languages) = $event)),
                  label: "允许的原始语言（逗号分隔）",
                  density: "compact",
                  "hide-details": "",
                  variant: "outlined",
                  disabled: !form.value.filter_original_language,
                  placeholder: "zh,ja,ko,en",
                  class: "mt-2"
                }, null, 8, ["modelValue", "disabled"]),
                _cache[114] || (_cache[114] = _createElementVNode("div", { class: "sc-hint mt-1" }, " 语种码：zh 华语 / ja 日语 / ko 韩语 / en 英语。小语种片通常不会被下载，进订阅只会白占额度。 ", -1))
              ])
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'anilist')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
              _createElementVNode("div", _hoisted_45, [
                _createElementVNode("div", _hoisted_46, [
                  _cache[115] || (_cache[115] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "启用 AniList 数据源"),
                    _createElementVNode("div", { class: "sc-row-hint" }, "番剧新番 / 连载 / 国漫（含下一集播出时间）")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.enable_anilist,
                    "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((form.value.enable_anilist) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ])
              ]),
              _createElementVNode("div", _hoisted_47, [
                _cache[116] || (_cache[116] = _createElementVNode("div", { class: "sc-card-title" }, "独立定时（AniList）", -1)),
                _createVNode(_component_VTextField, {
                  modelValue: form.value.cron_anilist,
                  "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((form.value.cron_anilist) = $event)),
                  label: "五位 cron，留空=跟随全局定时",
                  density: "compact",
                  "hide-details": "",
                  variant: "outlined",
                  placeholder: "例：0 8 * * *",
                  class: "mb-1"
                }, null, 8, ["modelValue"]),
                _cache[117] || (_cache[117] = _createElementVNode("div", { class: "sc-hint" }, "留空则跟随「写入与调度」里的全局 cron；填了就会单独按这个时间跑该源。", -1))
              ]),
              _createElementVNode("div", _hoisted_48, [
                _createElementVNode("div", _hoisted_49, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-animation-outline",
                    size: "16"
                  }),
                  _cache[118] || (_cache[118] = _createTextVNode(" AniList ", -1))
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
                          "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((form.value.anilist_future_days) = $event)),
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
                          "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((form.value.min_rating_anilist) = $event)),
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
                          "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((form.value.anilist_min_popularity) = $event)),
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
                          "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((form.value.anilist_include_donghua) = $event)),
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
                _cache[119] || (_cache[119] = _createElementVNode("div", { class: "sc-hint" }, [
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
        (activeSection.value === 'platform')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
              _createElementVNode("div", _hoisted_50, [
                _createElementVNode("div", _hoisted_51, [
                  _cache[120] || (_cache[120] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "启用腾讯视频「即将上线」"),
                    _createElementVNode("div", { class: "sc-row-hint" }, "电视剧 / 电影 / 综艺的定档与待播（私有接口，只有排在前面的几条带上线时间）")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.enable_qq_video,
                    "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((form.value.enable_qq_video) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ])
              ]),
              _createElementVNode("div", _hoisted_52, [
                _createElementVNode("div", _hoisted_53, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-television-play",
                    size: "16"
                  }),
                  _cache[121] || (_cache[121] = _createTextVNode(" 腾讯视频 ", -1))
                ]),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.qq_video_max_items,
                          "onUpdate:modelValue": _cache[31] || (_cache[31] = $event => ((form.value.qq_video_max_items) = $event)),
                          modelModifiers: { number: true },
                          label: "每个频道最多取 N 条",
                          type: "number",
                          min: "1",
                          max: "60",
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
                _cache[122] || (_cache[122] = _createElementVNode("div", { class: "sc-hint" }, [
                  _createTextVNode(" 三个频道（电视剧 36 条 / 电影 36 条 / 综艺 12 条，实测）共用一个接口。 "),
                  _createElementVNode("b", null, "只有排在前面的少数几条带「上线时间」"),
                  _createTextVNode("，其余是已上架但没定档的待播片： 带日期的走时间窗口；不带日期的靠「TMDB 是否还有未播集」判定，所以剧集能进、电影会被跳过。 预约人数会当「关注度」参与筛选。 ")
                ], -1))
              ]),
              _createElementVNode("div", _hoisted_54, [
                _createElementVNode("div", _hoisted_55, [
                  _cache[123] || (_cache[123] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "启用 B 站番剧时间表"),
                    _createElementVNode("div", { class: "sc-row-hint" }, [
                      _createTextVNode("公开接口；定位是 "),
                      _createElementVNode("b", null, "AniList 的备份"),
                      _createTextVNode("（限流 / 停服时顶上）")
                    ])
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.enable_bilibili,
                    "onUpdate:modelValue": _cache[32] || (_cache[32] = $event => ((form.value.enable_bilibili) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ])
              ]),
              _createElementVNode("div", _hoisted_56, [
                _createElementVNode("div", _hoisted_57, [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-animation-play-outline",
                    size: "16"
                  }),
                  _cache[124] || (_cache[124] = _createTextVNode(" B 站番剧 ", -1))
                ]),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.bilibili_future_days,
                          "onUpdate:modelValue": _cache[33] || (_cache[33] = $event => ((form.value.bilibili_future_days) = $event)),
                          modelModifiers: { number: true },
                          label: "看多少天（上限 7）",
                          type: "number",
                          min: "1",
                          max: "7",
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
                          modelValue: form.value.bilibili_max_items,
                          "onUpdate:modelValue": _cache[34] || (_cache[34] = $event => ((form.value.bilibili_max_items) = $event)),
                          modelModifiers: { number: true },
                          label: "最多取 N 条",
                          type: "number",
                          min: "1",
                          max: "60",
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
                _cache[125] || (_cache[125] = _createElementVNode("div", { class: "sc-hint" }, " B 站的时间表只有番剧（真人剧返回空数组），且只覆盖近 7 天有更新的番， 所以一年也就几十条——它的价值不在「多」，而在 AniList 掛了时还有一份国内视角的档期。 ", -1))
              ])
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'hot_media')
          ? (_openBlock(), _createElementBlock("div", _hoisted_58, [
              _createElementVNode("div", _hoisted_59, [
                _createVNode(_component_VSwitch, {
                  modelValue: form.value.enable_hot_media,
                  "onUpdate:modelValue": _cache[35] || (_cache[35] = $event => ((form.value.enable_hot_media) = $event)),
                  density: "compact",
                  "hide-details": "",
                  color: "primary",
                  class: "mr-2"
                }, null, 8, ["modelValue"]),
                _cache[126] || (_cache[126] = _createTextVNode(" 热门媒体（MoviePilot 官方热门订阅统计） ", -1))
              ]),
              _cache[129] || (_cache[129] = _createElementVNode("div", { class: "sc-hint" }, " 大家都在订什么。**依赖宿主的「订阅数据共享」**：未开启时官方返回空数据。 ", -1)),
              _createElementVNode("div", _hoisted_60, [
                _createElementVNode("div", _hoisted_61, [
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.hot_media_movie_enabled,
                    "onUpdate:modelValue": _cache[36] || (_cache[36] = $event => ((form.value.hot_media_movie_enabled) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"]),
                  _cache[127] || (_cache[127] = _createElementVNode("span", null, "电影热门", -1))
                ]),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.hot_media_movie_limit,
                          "onUpdate:modelValue": _cache[37] || (_cache[37] = $event => ((form.value.hot_media_movie_limit) = $event)),
                          modelModifiers: { number: true },
                          label: "取前 N 部",
                          type: "number",
                          min: "1",
                          max: "100",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          suffix: "部"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.value.hot_media_movie_genres,
                          "onUpdate:modelValue": _cache[38] || (_cache[38] = $event => ((form.value.hot_media_movie_genres) = $event)),
                          items: MOVIE_GENRES,
                          label: "风格（不选=全部）",
                          multiple: "",
                          chips: "",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "6",
                      sm: "3",
                      md: "2"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.hot_media_movie_min_rating,
                          "onUpdate:modelValue": _cache[39] || (_cache[39] = $event => ((form.value.hot_media_movie_min_rating) = $event)),
                          modelModifiers: { number: true },
                          label: "评分 ≥",
                          type: "number",
                          step: "0.1",
                          min: "0",
                          max: "10",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "6",
                      sm: "3",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.hot_media_movie_min_count,
                          "onUpdate:modelValue": _cache[40] || (_cache[40] = $event => ((form.value.hot_media_movie_min_count) = $event)),
                          modelModifiers: { number: true },
                          label: "订阅人次 ≥",
                          type: "number",
                          min: "0",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          suffix: "人"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _createElementVNode("div", _hoisted_62, [
                _createElementVNode("div", _hoisted_63, [
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.hot_media_tv_enabled,
                    "onUpdate:modelValue": _cache[41] || (_cache[41] = $event => ((form.value.hot_media_tv_enabled) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"]),
                  _cache[128] || (_cache[128] = _createElementVNode("span", null, "剧集热门", -1))
                ]),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.hot_media_tv_limit,
                          "onUpdate:modelValue": _cache[42] || (_cache[42] = $event => ((form.value.hot_media_tv_limit) = $event)),
                          modelModifiers: { number: true },
                          label: "取前 N 部",
                          type: "number",
                          min: "1",
                          max: "100",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          suffix: "部"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.value.hot_media_tv_genres,
                          "onUpdate:modelValue": _cache[43] || (_cache[43] = $event => ((form.value.hot_media_tv_genres) = $event)),
                          items: TV_GENRES,
                          label: "风格（不选=全部）",
                          multiple: "",
                          chips: "",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "6",
                      sm: "3",
                      md: "2"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.hot_media_tv_min_rating,
                          "onUpdate:modelValue": _cache[44] || (_cache[44] = $event => ((form.value.hot_media_tv_min_rating) = $event)),
                          modelModifiers: { number: true },
                          label: "评分 ≥",
                          type: "number",
                          step: "0.1",
                          min: "0",
                          max: "10",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "6",
                      sm: "3",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: form.value.hot_media_tv_min_count,
                          "onUpdate:modelValue": _cache[45] || (_cache[45] = $event => ((form.value.hot_media_tv_min_count) = $event)),
                          modelModifiers: { number: true },
                          label: "订阅人次 ≥",
                          type: "number",
                          min: "0",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          suffix: "人"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _cache[130] || (_cache[130] = _createElementVNode("div", { class: "sc-hint" }, " 「取前 N 部」= 每个榜单抓多少条；「风格」可多选，选了多个会分别查询后合并去重； 「评分 ≥」「订阅人次 ≥」填 0 表示不限。 ", -1)),
              _createVNode(_component_VTextField, {
                modelValue: form.value.cron_hot_media,
                "onUpdate:modelValue": _cache[46] || (_cache[46] = $event => ((form.value.cron_hot_media) = $event)),
                label: "独立定时（留空=跟随全局）",
                density: "compact",
                "hide-details": "",
                variant: "outlined",
                placeholder: "例：0 9 * * *",
                class: "mt-2 mb-1"
              }, null, 8, ["modelValue"])
            ]))
          : _createCommentVNode("", true),
        (activeSection.value === 'blacklist')
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 6 }, [
              _createElementVNode("div", _hoisted_64, [
                _createElementVNode("div", _hoisted_65, [
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.blacklist_enabled,
                    "onUpdate:modelValue": _cache[47] || (_cache[47] = $event => ((form.value.blacklist_enabled) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary",
                    class: "mr-2"
                  }, null, 8, ["modelValue"]),
                  _cache[131] || (_cache[131] = _createTextVNode(" 排除规则（黑名单） ", -1))
                ]),
                _createElementVNode("div", _hoisted_66, [
                  _cache[132] || (_cache[132] = _createTextVNode(" 只拦「自动发现」这条线：命中的片子不会自动订阅，也不会被当成「订过」。 ", -1)),
                  _cache[133] || (_cache[133] = _createElementVNode("b", null, "已有订阅不受影响", -1)),
                  _createTextVNode("（要停请去宿主订阅页暂停），「发现流水」里的手动重新订阅按钮也不受限制。 当前生效规则 " + _toDisplayString(blacklistRuleCount.value) + " 条。 ", 1)
                ]),
                _cache[138] || (_cache[138] = _createElementVNode("div", { class: "sc-card-title mt-3" }, "排除类型", -1)),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.value.blacklist_genre_movie,
                          "onUpdate:modelValue": _cache[48] || (_cache[48] = $event => ((form.value.blacklist_genre_movie) = $event)),
                          items: MOVIE_GENRES,
                          label: "电影：排除这些类型",
                          multiple: "",
                          chips: "",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: form.value.blacklist_genre_tv,
                          "onUpdate:modelValue": _cache[49] || (_cache[49] = $event => ((form.value.blacklist_genre_tv) = $event)),
                          items: TV_GENRES,
                          label: "剧集：排除这些类型",
                          multiple: "",
                          chips: "",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _cache[139] || (_cache[139] = _createElementVNode("div", { class: "sc-hint mt-1" }, [
                  _createTextVNode(" 按 TMDB 类型 id 精确匹配。"),
                  _createElementVNode("b", null, "不要勾「剧情」"),
                  _createTextVNode(" —— 几乎每部片子都带这个类型，勾了整个源都会被拦掉。 "),
                  _createElementVNode("b", null, "「同性」不是 TMDB 类型"),
                  _createTextVNode("（TMDB 没有这个词），要拦它请用下面的「排除题材」。 豆瓣榜单类路线（综艺榜 / 纪录片榜）本身不带类型，会先按路线补上「综艺」「纪录」， 再在身份解析完成后用 TMDB 类型复核一次 —— 所以"),
                  _createElementVNode("b", null, "勾了「真人秀 / 脱口秀」就能拦住综艺榜"),
                  _createTextVNode("。 ")
                ], -1)),
                _cache[140] || (_cache[140] = _createElementVNode("div", { class: "sc-card-title mt-3" }, "排除题材", -1)),
                _cache[141] || (_cache[141] = _createElementVNode("div", { class: "sc-hint" }, [
                  _createTextVNode(" 内置预设"),
                  _createElementVNode("b", null, "默认一条都不生效"),
                  _createTextVNode("，勾了才开始拦；勾选后下面会列出它到底匹配哪些词。 ")
                ], -1)),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(blacklistPresets.value, (preset) => {
                      return (_openBlock(), _createBlock(_component_VCol, {
                        key: preset.key,
                        cols: "12",
                        sm: "6",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VCheckbox, {
                            modelValue: form.value.blacklist_presets,
                            "onUpdate:modelValue": _cache[50] || (_cache[50] = $event => ((form.value.blacklist_presets) = $event)),
                            value: preset.key,
                            density: "compact",
                            "hide-details": "",
                            color: "primary"
                          }, {
                            label: _withCtx(() => [
                              _createElementVNode("span", null, _toDisplayString(preset.label), 1)
                            ]),
                            _: 2
                          }, 1032, ["modelValue", "value"]),
                          _createElementVNode("div", _hoisted_67, _toDisplayString(preset.hint), 1)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128))
                  ]),
                  _: 1
                }),
                (!blacklistPresets.value.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_68, " 没取到内置预设（后端未就绪）。可以直接在下面写自定义词。 "))
                  : _createCommentVNode("", true),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(blacklistPresets.value, (preset) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: `${preset.key}-words`
                  }, [
                    ((form.value.blacklist_presets || []).includes(preset.key))
                      ? (_openBlock(), _createElementBlock("div", _hoisted_69, _toDisplayString(preset.label) + " 会匹配：" + _toDisplayString(presetWords(preset.key).join(' / ')), 1))
                      : _createCommentVNode("", true)
                  ]))
                }), 128)),
                _createVNode(_component_VTextarea, {
                  modelValue: form.value.blacklist_words,
                  "onUpdate:modelValue": _cache[51] || (_cache[51] = $event => ((form.value.blacklist_words) = $event)),
                  label: "自定义题材词（一行一个）",
                  rows: "4",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  class: "mt-2",
                  placeholder: "同性\n韩国 同性\nregex:^(BL|耽美)\ncase:BL"
                }, null, 8, ["modelValue"]),
                _createElementVNode("div", _hoisted_70, [
                  _cache[134] || (_cache[134] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "匹配片名 / 原名"),
                    _createElementVNode("div", { class: "sc-row-hint" }, "片名里出现题材词就拦（关掉则只看来源题材串）")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.blacklist_match_title,
                    "onUpdate:modelValue": _cache[52] || (_cache[52] = $event => ((form.value.blacklist_match_title) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_71, [
                  _cache[135] || (_cache[135] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "匹配来源题材串"),
                    _createElementVNode("div", { class: "sc-row-hint" }, " 豆瓣分类（如「2026 / 泰国 / 剧情 同性」）与 AniList 的 genres / tags ")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.blacklist_match_tags,
                    "onUpdate:modelValue": _cache[53] || (_cache[53] = $event => ((form.value.blacklist_match_tags) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_72, [
                  _cache[136] || (_cache[136] = _createElementVNode("div", { class: "sc-row-main" }, [
                    _createElementVNode("div", { class: "sc-row-label" }, "额外查 TMDB 关键词"),
                    _createElementVNode("div", { class: "sc-row-hint" }, " 只对已通过其它过滤、即将写入的条目查（每条多一次请求，结果按条目缓存） ")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: form.value.blacklist_tmdb_keywords,
                    "onUpdate:modelValue": _cache[54] || (_cache[54] = $event => ((form.value.blacklist_tmdb_keywords) = $event)),
                    density: "compact",
                    "hide-details": "",
                    color: "primary"
                  }, null, 8, ["modelValue"])
                ]),
                _cache[142] || (_cache[142] = _createStaticVNode("<div class=\"sc-hint mt-2\" data-v-25babbac><b data-v-25babbac>写法</b>：中文按「包含」匹配（「同性」能命中「同性恋」）；英文按「整词」（<code data-v-25babbac>BL</code> 不会命中 <code data-v-25babbac>BLADE</code>）； 一行里写多个词用空格分隔 = 同时包含（<code data-v-25babbac>韩国 同性</code> 只拦韩国同性题材）； 行首加 <code data-v-25babbac>regex:</code> 用正则；行首加 <code data-v-25babbac>case:</code> 区分大小写；空行与 <code data-v-25babbac>#</code> 开头的行忽略。 全部留空 = 不排除任何内容。 </div><div class=\"sc-hint mt-2\" data-v-25babbac><b data-v-25babbac>词表参考</b>（只是提示，不会自动生效）： 同性 / 耽美 / BL / boys love / shounen ai / yaoi / 百合 / GL / girls love / yuri / lgbt / gay / lesbian / bisexual / transgender / queer / 综艺 / 真人秀 / 脱口秀 / 访谈 / 短剧 / 微短剧。 地区词也能组合：「泰国 同性」「韩国 同性」。 </div><div class=\"sc-card-title mt-3\" data-v-25babbac>试一下</div>", 3)),
                _createVNode(_component_VRow, { dense: "" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      sm: "5"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: blacklistTestForm.value.title,
                          "onUpdate:modelValue": _cache[55] || (_cache[55] = $event => ((blacklistTestForm.value.title) = $event)),
                          label: "片名",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          placeholder: "例：以你的心诠释我的爱"
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
                          modelValue: blacklistTestForm.value.tags,
                          "onUpdate:modelValue": _cache[56] || (_cache[56] = $event => ((blacklistTestForm.value.tags) = $event)),
                          label: "题材串（可空）",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined",
                          placeholder: "2026 / 泰国 / 剧情 同性"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "6",
                      sm: "2"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: blacklistTestForm.value.media_type,
                          "onUpdate:modelValue": _cache[57] || (_cache[57] = $event => ((blacklistTestForm.value.media_type) = $event)),
                          items: [
                  { title: '剧集', value: 'tv' },
                  { title: '电影', value: 'movie' },
                ],
                          label: "类型",
                          density: "compact",
                          "hide-details": "",
                          variant: "outlined"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "6",
                      sm: "1"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VBtn, {
                          variant: "tonal",
                          size: "small",
                          block: "",
                          loading: blacklistTestBusy.value,
                          onClick: runBlacklistTest
                        }, {
                          default: _withCtx(() => [...(_cache[137] || (_cache[137] = [
                            _createTextVNode(" 自测 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["loading"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                (blacklistTestResult.value)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_73, [
                      (blacklistTestResult.value.matched)
                        ? (_openBlock(), _createBlock(_component_VChip, {
                            key: 0,
                            size: "small",
                            variant: "flat",
                            color: "error"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(" 会被拦下：" + _toDisplayString(blacklistTestResult.value.reason), 1)
                            ]),
                            _: 1
                          }))
                        : (_openBlock(), _createBlock(_component_VChip, {
                            key: 1,
                            size: "small",
                            variant: "flat",
                            color: "success"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(" 不会被拦（当前生效规则 " + _toDisplayString(blacklistTestResult.value.rules) + " 条） ", 1)
                            ]),
                            _: 1
                          })),
                      (blacklistTestResult.value.hint)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_74, _toDisplayString(blacklistTestResult.value.hint), 1))
                        : _createCommentVNode("", true)
                    ]))
                  : _createCommentVNode("", true),
                (!form.value.blacklist_enabled)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_75, " 总开关没开：上面这些规则一条都不会生效。 "))
                  : _createCommentVNode("", true)
              ]),
              _createElementVNode("div", _hoisted_76, [
                _cache[145] || (_cache[145] = _createElementVNode("div", { class: "sc-card-title" }, "体检已有订阅", -1)),
                _cache[146] || (_cache[146] = _createElementVNode("div", { class: "sc-hint" }, [
                  _createTextVNode(" 上面的规则只拦「自动发现」将要写入的新条目，"),
                  _createElementVNode("b", null, "不管已经存在的订阅"),
                  _createTextVNode(" —— 早先订的、重装后随数据库恢复带回来的、或从发现流水手动点 「加入订阅」的，都不会被它清掉。这里按当前规则把已有订阅逐条核对一遍： "),
                  _createElementVNode("b", null, "只出报告，不动手"),
                  _createTextVNode("；要暂停哪几条，自己勾。 每条订阅要查一次 TMDB 详情，200 条大约一两分钟。 ")
                ], -1)),
                _createElementVNode("div", _hoisted_77, [
                  _createVNode(_component_VBtn, {
                    size: "small",
                    color: "primary",
                    variant: "flat",
                    loading: auditBusy.value,
                    disabled: !form.value.blacklist_enabled,
                    onClick: runBlacklistAudit
                  }, {
                    default: _withCtx(() => [...(_cache[143] || (_cache[143] = [
                      _createTextVNode(" 开始体检 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading", "disabled"]),
                  _createVNode(_component_VBtn, {
                    size: "small",
                    variant: "tonal",
                    color: "warning",
                    disabled: auditBusy.value || !auditSelected.value.length,
                    onClick: _cache[58] || (_cache[58] = $event => (sweepAudit('pause')))
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 暂停选中（" + _toDisplayString(auditSelected.value.length) + "） ", 1)
                    ]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode(_component_VBtn, {
                    size: "small",
                    variant: "text",
                    disabled: auditBusy.value || !auditSelected.value.length,
                    onClick: _cache[59] || (_cache[59] = $event => (sweepAudit('resume')))
                  }, {
                    default: _withCtx(() => [...(_cache[144] || (_cache[144] = [
                      _createTextVNode(" 恢复选中 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled"]),
                  (audit.value?.running)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_78, "正在核对，请稍候…"))
                    : _createCommentVNode("", true)
                ]),
                (auditStats.value)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_79, _toDisplayString(auditStats.value), 1))
                  : _createCommentVNode("", true),
                (audit.value?.error)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_80, " 体检失败：" + _toDisplayString(audit.value.error), 1))
                  : _createCommentVNode("", true),
                (auditHits.value.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_81, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(auditHits.value, (hit) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: hit.id,
                          class: "d-flex align-center flex-wrap",
                          style: {"gap":"8px","padding":"4px 0","border-bottom":"1px solid rgba(255, 255, 255, 0.06)"}
                        }, [
                          _withDirectives(_createElementVNode("input", {
                            "onUpdate:modelValue": _cache[60] || (_cache[60] = $event => ((auditSelected).value = $event)),
                            type: "checkbox",
                            value: hit.id
                          }, null, 8, _hoisted_82), [
                            [_vModelCheckbox, auditSelected.value]
                          ]),
                          _createElementVNode("span", _hoisted_83, _toDisplayString(hit.name), 1),
                          _createElementVNode("span", _hoisted_84, " S" + _toDisplayString(hit.season) + " · " + _toDisplayString(hit.state) + " · " + _toDisplayString(hit.media_type === 'movie' ? '电影' : '剧集'), 1),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            variant: "flat",
                            color: "error"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(hit.reason), 1)
                            ]),
                            _: 2
                          }, 1024)
                        ]))
                      }), 128))
                    ]))
                  : (auditDone.value && !audit.value?.running)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_85, " 没有已有订阅命中当前规则。 "))
                    : _createCommentVNode("", true),
                (auditUncheckable.value.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_86, [
                      _createElementVNode("div", _hoisted_87, " 有 " + _toDisplayString(auditUncheckable.value.length) + " 条没法核（来源不是 TMDB / 查详情失败）， 它们既不算命中也不算通过： ", 1),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(auditUncheckable.value.slice(0, 6), (row) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: `u-${row.id}`,
                          class: "sc-hint"
                        }, " · " + _toDisplayString(row.name) + " —— " + _toDisplayString(row.skipped), 1))
                      }), 128))
                    ]))
                  : _createCommentVNode("", true)
              ])
            ], 64))
          : _createCommentVNode("", true),
        (activeSection.value === 'schedule')
          ? (_openBlock(), _createElementBlock("div", _hoisted_88, [
              _cache[148] || (_cache[148] = _createElementVNode("div", { class: "sc-card-title" }, "写入与调度", -1)),
              _createVNode(_component_VRow, { dense: "" }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCol, {
                    cols: "12",
                    sm: "6"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VTextField, {
                        modelValue: form.value.daily_limit,
                        "onUpdate:modelValue": _cache[61] || (_cache[61] = $event => ((form.value.daily_limit) = $event)),
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
                        "onUpdate:modelValue": _cache[62] || (_cache[62] = $event => ((form.value.resolve_concurrency) = $event)),
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
                        "onUpdate:modelValue": _cache[63] || (_cache[63] = $event => ((form.value.cron) = $event)),
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
                        "onUpdate:modelValue": _cache[64] || (_cache[64] = $event => ((form.value.timezone) = $event)),
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
              _cache[149] || (_cache[149] = _createElementVNode("div", { class: "sc-hint" }, "修改 cron 后需要重新保存配置才会重建定时任务。", -1)),
              _createVNode(_component_VDivider, { class: "my-3" }),
              _cache[150] || (_cache[150] = _createElementVNode("div", {
                class: "sc-card-title",
                style: {"font-size":"0.95rem"}
              }, "电影发行日", -1)),
              _createVNode(_component_VSwitch, {
                modelValue: form.value.movie_release_fallback,
                "onUpdate:modelValue": _cache[65] || (_cache[65] = $event => ((form.value.movie_release_fallback) = $event)),
                label: "来源没给日期时，用 TMDB 发行日兜底",
                density: "compact",
                "hide-details": "",
                color: "primary",
                class: "mb-1"
              }, null, 8, ["modelValue"]),
              _cache[151] || (_cache[151] = _createElementVNode("div", { class: "sc-hint" }, " 豆瓣榜单类 RSS 只有片名、没有日期。关掉这个开关，这类电影会一律按「无日期」跳过 —— 刚上线数字版的片子也就订不到了。 ", -1)),
              _createVNode(_component_VRow, {
                dense: "",
                class: "mt-2"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCol, {
                    cols: "12",
                    sm: "6"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VTextField, {
                        modelValue: form.value.movie_release_grace_days,
                        "onUpdate:modelValue": _cache[66] || (_cache[66] = $event => ((form.value.movie_release_grace_days) = $event)),
                        modelModifiers: { number: true },
                        label: "发行后宽限天数（0 = 必须在未来）",
                        type: "number",
                        min: "0",
                        max: "90",
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
              _cache[152] || (_cache[152] = _createElementVNode("div", { class: "sc-hint" }, " 数字版上线之后站点上才有资源。留几天宽限，刚上映的片子才订得到； 老片的发行日远在过去，宽限期一过照样跳过。 ", -1)),
              _createVNode(_component_VDivider, { class: "my-3" }),
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(switchRows.filter((item) => item.key !== 'enabled'), (row) => {
                return (_openBlock(), _createElementBlock("div", {
                  key: row.key,
                  class: "sc-row"
                }, [
                  _createElementVNode("div", _hoisted_89, [
                    _createElementVNode("div", _hoisted_90, _toDisplayString(row.label), 1),
                    _createElementVNode("div", _hoisted_91, _toDisplayString(row.hint), 1)
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
              _createElementVNode("div", _hoisted_92, [
                _cache[147] || (_cache[147] = _createElementVNode("div", { class: "sc-row-main" }, [
                  _createElementVNode("div", { class: "sc-row-label" }, "清零今日写入计数（测试开关）"),
                  _createElementVNode("div", { class: "sc-row-hint" }, " 保存后把「今日已写入 N 条」清零，方便同一天反复测；保存即自动置回关闭。 ")
                ], -1)),
                _createVNode(_component_VSwitch, {
                  modelValue: form.value.reset_daily_counter,
                  "onUpdate:modelValue": _cache[67] || (_cache[67] = $event => ((form.value.reset_daily_counter) = $event)),
                  density: "compact",
                  "hide-details": "",
                  color: "warning"
                }, null, 8, ["modelValue"])
              ])
            ]))
          : _createCommentVNode("", true),
        (activeSection.value === 'autotoggle')
          ? (_openBlock(), _createElementBlock("div", _hoisted_93, [
              _cache[163] || (_cache[163] = _createElementVNode("div", { class: "sc-card-title" }, "播出日自动启停", -1)),
              _cache[164] || (_cache[164] = _createElementVNode("div", { class: "sc-hint" }, [
                _createTextVNode(" 宿主的「订阅刷新」每天会跑几十轮，把"),
                _createElementVNode("b", null, "全部"),
                _createTextVNode("订阅都拉进匹配循环； 两百条订阅里绝大多数当天并没有新集，纯属空转。 这里按 TMDB 播出表判断「今天有没有该搜的集」：有已播未入库的集 （或最近要播出）就保持订阅中，其余暂停。"),
                _createElementVNode("b", null, "只改状态，不写订阅、不碰下载记录。")
              ], -1)),
              _createElementVNode("div", _hoisted_94, [
                _cache[153] || (_cache[153] = _createElementVNode("div", { class: "sc-row-main" }, [
                  _createElementVNode("div", { class: "sc-row-label" }, "启用自动启停"),
                  _createElementVNode("div", { class: "sc-row-hint" }, "关闭时不会注册定时任务，也不会有任何订阅被改动")
                ], -1)),
                _createVNode(_component_VSwitch, {
                  modelValue: form.value.auto_toggle_enabled,
                  "onUpdate:modelValue": _cache[68] || (_cache[68] = $event => ((form.value.auto_toggle_enabled) = $event)),
                  density: "compact",
                  "hide-details": "",
                  color: "primary"
                }, null, 8, ["modelValue"])
              ]),
              _createElementVNode("div", _hoisted_95, [
                _cache[154] || (_cache[154] = _createElementVNode("div", { class: "sc-row-main" }, [
                  _createElementVNode("div", { class: "sc-row-label" }, "有改动时发通知"),
                  _createElementVNode("div", { class: "sc-row-hint" }, "只在真的暂停/恢复了订阅时推送一条摘要")
                ], -1)),
                _createVNode(_component_VSwitch, {
                  modelValue: form.value.auto_toggle_notify,
                  "onUpdate:modelValue": _cache[69] || (_cache[69] = $event => ((form.value.auto_toggle_notify) = $event)),
                  density: "compact",
                  "hide-details": "",
                  color: "primary"
                }, null, 8, ["modelValue"])
              ]),
              _createElementVNode("div", _hoisted_96, [
                _cache[155] || (_cache[155] = _createElementVNode("div", { class: "sc-row-main" }, [
                  _createElementVNode("div", { class: "sc-row-label" }, "连电影订阅一起管"),
                  _createElementVNode("div", { class: "sc-row-hint" }, " 电影没有播出日，改按 TMDB 发行日判：发行前暂停，发行后按上方「缺集保留天数」继续搜 ")
                ], -1)),
                _createVNode(_component_VSwitch, {
                  modelValue: form.value.auto_toggle_movie_enabled,
                  "onUpdate:modelValue": _cache[70] || (_cache[70] = $event => ((form.value.auto_toggle_movie_enabled) = $event)),
                  density: "compact",
                  "hide-details": "",
                  color: "primary"
                }, null, 8, ["modelValue"])
              ]),
              (form.value.auto_toggle_movie_enabled)
                ? (_openBlock(), _createBlock(_component_VRow, {
                    key: 0,
                    dense: "",
                    class: "mt-1"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VCol, {
                        cols: "12",
                        sm: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VTextField, {
                            modelValue: form.value.auto_toggle_movie_theatrical_offset_days,
                            "onUpdate:modelValue": _cache[71] || (_cache[71] = $event => ((form.value.auto_toggle_movie_theatrical_offset_days) = $event)),
                            modelModifiers: { number: true },
                            label: "只有影院日期时，往后推几天算数字发行",
                            type: "number",
                            min: "0",
                            max: "365",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": "",
                            suffix: "天"
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VCol, {
                        cols: "12",
                        sm: "6",
                        class: "d-flex align-center"
                      }, {
                        default: _withCtx(() => [...(_cache[156] || (_cache[156] = [
                          _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, " 影院在映期间下不到片，拿上映日开窗只会白搜。TMDB 没有数字/实体 发行日期时，按上映日 + 这个天数估算（默认 90）；补上真实日期后自动改用。 设 0 = 不估算，直接用上映日。 ", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }))
                : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_97, [
                _cache[157] || (_cache[157] = _createElementVNode("div", { class: "sc-row-main" }, [
                  _createElementVNode("div", { class: "sc-row-label" }, "用媒体库核对已入库"),
                  _createElementVNode("div", { class: "sc-row-hint" }, " 订阅的「已下载」只记宿主自己下过的集；从别处导入的库内剧集它不知道。 打开后先读媒体库快照（零请求），再在预算内逐条问媒体服务器，逐条之间有间隔。 ")
                ], -1)),
                _createVNode(_component_VSwitch, {
                  modelValue: form.value.auto_toggle_library_check,
                  "onUpdate:modelValue": _cache[72] || (_cache[72] = $event => ((form.value.auto_toggle_library_check) = $event)),
                  density: "compact",
                  "hide-details": "",
                  color: "primary"
                }, null, 8, ["modelValue"])
              ]),
              (form.value.auto_toggle_library_check)
                ? (_openBlock(), _createBlock(_component_VRow, {
                    key: 1,
                    dense: "",
                    class: "mt-1"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VCol, {
                        cols: "12",
                        sm: "6"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VTextField, {
                            modelValue: form.value.auto_toggle_library_probe_budget_seconds,
                            "onUpdate:modelValue": _cache[73] || (_cache[73] = $event => ((form.value.auto_toggle_library_probe_budget_seconds) = $event)),
                            modelModifiers: { number: true },
                            label: "每轮最多核对多少秒（0 = 只读快照）",
                            type: "number",
                            min: "0",
                            max: "3600",
                            density: "compact",
                            "hide-details": "",
                            variant: "outlined",
                            class: "mb-2",
                            hint: "到点就停，剩下的下次继续（它们的缺集按订阅记录算）",
                            "persistent-hint": ""
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
                            modelValue: form.value.auto_toggle_library_probe_interval,
                            "onUpdate:modelValue": _cache[74] || (_cache[74] = $event => ((form.value.auto_toggle_library_probe_interval) = $event)),
                            modelModifiers: { number: true },
                            label: "每条之间隔几秒",
                            type: "number",
                            min: "0",
                            max: "60",
                            step: "0.5",
                            density: "compact",
                            "hide-details": "",
                            variant: "outlined",
                            class: "mb-2",
                            hint: "串行 + 间隔，避免把媒体服务器打满",
                            "persistent-hint": ""
                          }, null, 8, ["modelValue"])
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }))
                : _createCommentVNode("", true),
              _createVNode(_component_VRow, {
                dense: "",
                class: "mt-1"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCol, {
                    cols: "12",
                    sm: "6"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VTextField, {
                        modelValue: form.value.auto_toggle_cron,
                        "onUpdate:modelValue": _cache[75] || (_cache[75] = $event => ((form.value.auto_toggle_cron) = $event)),
                        label: "判定时间（5 段式 cron）",
                        error: !autoToggleCronValid(),
                        "error-messages": autoToggleCronValid() ? [] : ['需要 5 段，例如 5 0 * * *'],
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
                        modelValue: form.value.auto_toggle_lookahead_days,
                        "onUpdate:modelValue": _cache[76] || (_cache[76] = $event => ((form.value.auto_toggle_lookahead_days) = $event)),
                        modelModifiers: { number: true },
                        label: "提前天数（0 = 只在播出当天）",
                        type: "number",
                        min: "0",
                        max: "30",
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
                        modelValue: form.value.auto_toggle_keep_days,
                        "onUpdate:modelValue": _cache[77] || (_cache[77] = $event => ((form.value.auto_toggle_keep_days) = $event)),
                        modelModifiers: { number: true },
                        label: "缺集保留天数",
                        type: "number",
                        min: "0",
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
                    sm: "6"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VTextField, {
                        modelValue: form.value.auto_toggle_best_version_keep_days,
                        "onUpdate:modelValue": _cache[78] || (_cache[78] = $event => ((form.value.auto_toggle_best_version_keep_days) = $event)),
                        modelModifiers: { number: true },
                        label: "洗版保留天数（等更好的版本）",
                        type: "number",
                        min: "0",
                        max: "365",
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
                      _createVNode(_component_VSelect, {
                        modelValue: form.value.auto_toggle_best_version_mode,
                        "onUpdate:modelValue": _cache[79] || (_cache[79] = $event => ((form.value.auto_toggle_best_version_mode) = $event)),
                        items: BEST_MODE_OPTIONS,
                        label: "洗版判定时机",
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
                        modelValue: form.value.auto_toggle_max_changes,
                        "onUpdate:modelValue": _cache[80] || (_cache[80] = $event => ((form.value.auto_toggle_max_changes) = $event)),
                        modelModifiers: { number: true },
                        label: "单次改动上限（0 = 不限）",
                        type: "number",
                        min: "0",
                        max: "2000",
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
              _cache[165] || (_cache[165] = _createElementVNode("div", { class: "sc-hint" }, " 缺集保留 = 已播出但还没下到的集，从这个日期起算几天内仍继续搜（PT 出种常有延迟）。 判定时间建议早于「订阅刷新」，默认 00:05；改 cron 后要重新保存配置才会重建任务。 ", -1)),
              _createVNode(_component_VDivider, { class: "my-3" }),
              _createElementVNode("div", _hoisted_98, [
                _createVNode(_component_VBtn, {
                  variant: "tonal",
                  color: "info",
                  size: "small",
                  "prepend-icon": "mdi-eye-outline",
                  loading: autoToggleBusy.value === 'preview',
                  disabled: loading.value || Boolean(autoToggleBusy.value),
                  onClick: loadAutoToggle
                }, {
                  default: _withCtx(() => [...(_cache[158] || (_cache[158] = [
                    _createTextVNode(" 只看不改（预览） ", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading", "disabled"]),
                _createVNode(_component_VBtn, {
                  variant: "flat",
                  color: "warning",
                  size: "small",
                  "prepend-icon": "mdi-toggle-switch-outline",
                  loading: autoToggleBusy.value === 'apply',
                  disabled: loading.value || Boolean(autoToggleBusy.value),
                  onClick: applyAutoToggle
                }, {
                  default: _withCtx(() => [...(_cache[159] || (_cache[159] = [
                    _createTextVNode(" 立即执行 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading", "disabled"]),
                _cache[160] || (_cache[160] = _createElementVNode("span", { class: "sc-hint" }, "预览只读不算库（不碰媒体服务器）；核对在「立即执行」里后台跑", -1))
              ]),
              (autoToggle.value?.last_run?.running)
                ? (_openBlock(), _createElementBlock("div", _hoisted_99, [
                    _createVNode(_component_VAlert, {
                      type: "info",
                      variant: "tonal",
                      density: "compact",
                      icon: false
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 后台正在执行（开始于 " + _toDisplayString(autoToggle.value.last_run.started_at || '刚刚') + "）…… 核对媒体库是按条串行的，跑完这里会自动刷新。 ", 1)
                      ]),
                      _: 1
                    })
                  ]))
                : _createCommentVNode("", true),
              (autoToggle.value)
                ? (_openBlock(), _createElementBlock("div", _hoisted_100, [
                    _createElementVNode("div", _hoisted_101, [
                      _createVNode(_component_VChip, {
                        size: "x-small",
                        variant: "flat",
                        color: "info"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("基准日 " + _toDisplayString(autoToggle.value.today), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VChip, {
                        size: "x-small",
                        variant: "flat",
                        color: "warning"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("待暂停 " + _toDisplayString(autoToggle.value.paused ?? 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VChip, {
                        size: "x-small",
                        variant: "flat",
                        color: "success"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("待恢复 " + _toDisplayString(autoToggle.value.resumed ?? 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VChip, {
                        size: "x-small",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("保持不动 " + _toDisplayString(autoToggle.value.kept ?? 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_VChip, {
                        size: "x-small",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("跳过 " + _toDisplayString(autoToggle.value.skipped ?? 0), 1)
                        ]),
                        _: 1
                      }),
                      (autoToggle.value.truncated)
                        ? (_openBlock(), _createBlock(_component_VChip, {
                            key: 0,
                            size: "x-small",
                            variant: "flat",
                            color: "error"
                          }, {
                            default: _withCtx(() => [...(_cache[161] || (_cache[161] = [
                              _createTextVNode(" 超出单次上限已截断 ", -1)
                            ]))]),
                            _: 1
                          }))
                        : _createCommentVNode("", true),
                      (autoToggle.value.library)
                        ? (_openBlock(), _createBlock(_component_VChip, {
                            key: 1,
                            size: "x-small",
                            variant: "tonal",
                            color: "info"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(" 库核对：快照 " + _toDisplayString(autoToggle.value.library.snapshot ?? 0) + " 条 / 下载记录 " + _toDisplayString(autoToggle.value.library.download ?? 0) + " 条 / 沿用 " + _toDisplayString(autoToggle.value.library.cached ?? 0) + " 条 / 实探 " + _toDisplayString(autoToggle.value.library.probed ?? 0) + " 条 / 待核对 " + _toDisplayString(autoToggle.value.library.deferred ?? 0) + " 条（" + _toDisplayString(libraryElapsedText.value) + "） ", 1)
                            ]),
                            _: 1
                          }))
                        : _createCommentVNode("", true),
                      (autoToggle.value.library && autoToggle.value.library.failed)
                        ? (_openBlock(), _createBlock(_component_VChip, {
                            key: 2,
                            size: "x-small",
                            variant: "tonal",
                            color: "warning",
                            title: autoToggle.value.library.error || ''
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(" 库核对失败 " + _toDisplayString(autoToggle.value.library.failed) + " 条：" + _toDisplayString(autoToggle.value.library.error || '问不出结论'), 1)
                            ]),
                            _: 1
                          }, 8, ["title"]))
                        : _createCommentVNode("", true)
                    ]),
                    _createElementVNode("div", _hoisted_102, [
                      _cache[162] || (_cache[162] = _createElementVNode("div", { class: "sc-row-main" }, [
                        _createElementVNode("div", { class: "sc-row-label" }, "连「保持不动」的条目一起列出"),
                        _createElementVNode("div", { class: "sc-row-hint" }, "排查「为什么这条还在搜」时打开")
                      ], -1)),
                      _createVNode(_component_VSwitch, {
                        modelValue: autoToggleShowAll.value,
                        "onUpdate:modelValue": _cache[81] || (_cache[81] = $event => ((autoToggleShowAll).value = $event)),
                        density: "compact",
                        "hide-details": "",
                        color: "primary"
                      }, null, 8, ["modelValue"])
                    ]),
                    (!autoToggleItems.value.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_103, " 当前没有需要改动的订阅。 "))
                      : _createCommentVNode("", true),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(autoToggleItems.value, (row) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: row.id,
                        class: "sc-preview-row"
                      }, [
                        _createElementVNode("div", _hoisted_104, [
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            variant: "flat",
                            color: ACTION_COLORS[row.action] || 'default'
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(ACTION_LABELS[row.action] || row.action), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"]),
                          _createElementVNode("b", null, _toDisplayString(row.name), 1),
                          (row.season)
                            ? (_openBlock(), _createElementBlock("span", _hoisted_105, "S" + _toDisplayString(row.season), 1))
                            : _createCommentVNode("", true),
                          _createElementVNode("span", _hoisted_106, _toDisplayString(row.state) + " → " + _toDisplayString(row.target), 1),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(row.reason_label || row.reason), 1)
                            ]),
                            _: 2
                          }, 1024),
                          (row.pending && row.pending.length)
                            ? (_openBlock(), _createElementBlock("span", _hoisted_107, _toDisplayString(pendingText(row)), 1))
                            : _createCommentVNode("", true),
                          (row.library_confirmed)
                            ? (_openBlock(), _createElementBlock("span", _hoisted_108, " 库核对补上 " + _toDisplayString(row.library_confirmed) + " 集 ", 1))
                            : _createCommentVNode("", true),
                          (row.basis)
                            ? (_openBlock(), _createElementBlock("span", _hoisted_109, _toDisplayString(RELEASE_KIND_LABELS[row.basis_kind] || '上映') + " " + _toDisplayString(row.basis), 1))
                            : (row.next_air)
                              ? (_openBlock(), _createElementBlock("span", _hoisted_110, "下集 " + _toDisplayString(row.next_air), 1))
                              : _createCommentVNode("", true)
                        ]),
                        _createElementVNode("div", _hoisted_111, _toDisplayString(row.detail), 1)
                      ]))
                    }), 128))
                  ]))
                : _createCommentVNode("", true)
            ]))
          : _createCommentVNode("", true),
        (activeSection.value === 'preview')
          ? (_openBlock(), _createElementBlock("div", _hoisted_112, [
              _createElementVNode("div", _hoisted_113, [
                _createVNode(_component_VIcon, {
                  icon: "mdi-eye-outline",
                  size: "16"
                }),
                _cache[168] || (_cache[168] = _createTextVNode(" 预览结果 ", -1)),
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
                  default: _withCtx(() => [...(_cache[166] || (_cache[166] = [
                    _createTextVNode("未写入 · 未消耗额度", -1)
                  ]))]),
                  _: 1
                }),
                _createElementVNode("div", _hoisted_114, [
                  _createVNode(_component_VBtn, {
                    variant: "tonal",
                    color: "info",
                    size: "small",
                    loading: busy.value === 'preview',
                    disabled: loading.value,
                    "prepend-icon": "mdi-eye-outline",
                    onClick: preview
                  }, {
                    default: _withCtx(() => [...(_cache[167] || (_cache[167] = [
                      _createTextVNode(" 开始预览 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading", "disabled"])
                ])
              ]),
              (!previewItems.value.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_115, [...(_cache[169] || (_cache[169] = [
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
                  _createElementVNode("div", _hoisted_116, [
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
                      ? (_openBlock(), _createElementBlock("span", _hoisted_117, "(" + _toDisplayString(row.year) + ")", 1))
                      : _createCommentVNode("", true),
                    (row.release_date)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_118, "放送 " + _toDisplayString(row.release_date), 1))
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
                      ? (_openBlock(), _createElementBlock("span", _hoisted_119, "评分 " + _toDisplayString(row.rating), 1))
                      : _createCommentVNode("", true)
                  ])
                ]))
              }), 128))
            ]))
          : _createCommentVNode("", true)
      ])
    ]),
    _createElementVNode("div", _hoisted_120, [
      _createVNode(_component_VBtn, {
        variant: "text",
        size: "small",
        onClick: _cache[82] || (_cache[82] = $event => (emit('close')))
      }, {
        default: _withCtx(() => [...(_cache[170] || (_cache[170] = [
          _createTextVNode("关闭", -1)
        ]))]),
        _: 1
      }),
      _createElementVNode("div", _hoisted_121, [
        _createVNode(_component_VBtn, {
          variant: "tonal",
          size: "small",
          loading: busy.value === 'run',
          disabled: loading.value,
          "prepend-icon": "mdi-radar",
          onClick: runOnce
        }, {
          default: _withCtx(() => [...(_cache[171] || (_cache[171] = [
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
          default: _withCtx(() => [...(_cache[172] || (_cache[172] = [
            _createTextVNode(" 保存配置 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "disabled"])
      ])
    ])
  ], 512))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-25babbac"]]);

export { Config as default };
