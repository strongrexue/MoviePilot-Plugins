/**
 * 插件默认配置（前端快照）。
 *
 * ⚠️ 键集合必须与后端 `core/constants.py` 的 `default_config()` **严格一致**。
 * 宿主 `update_config()` 是整份覆盖：任一侧多一个键或少一个键，保存配置时
 * 都会被静默清掉。`tests/v3/subscribecenter/test_subscribecenter_plugin.py`
 * 对此设了回归锁（test_default_config_key_set_matches_frontend）。
 */
export const configDefaults = {
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
  resubscribe_completed: true,
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
}

/** 返回默认配置的深拷贝（避免多处共享同一份可变对象）。 */
export function defaultConfig() {
  return JSON.parse(JSON.stringify(configDefaults))
}
