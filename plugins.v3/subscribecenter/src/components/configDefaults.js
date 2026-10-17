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
  enable_bangumi: false,
  enable_douban_rss: false,
  enable_simkl: false,
  enable_justwatch: false,
  // ---------------- 发现窗口与阈值
  tmdb_future_days: 3,
  bangumi_future_days: 3,
  min_rating_tmdb: 6.0,
  min_rating_bangumi: 6.0,
  min_rating_douban: 6.0,
  min_rating_simkl: 6.0,
  min_popularity: 15.0,
  //: Bangumi 是否按季拆分订阅（默认关：国产动画多为单季多集）
  bangumi_split_season: false,
  //: 是否只保留指定原始语言的条目
  filter_original_language: true,
  tmdb_original_languages: 'zh,ja,ko,en',
  // ---------------- 豆瓣 RSS 源列表
  douban_rss_sources: [],
  douban_max_items_per_feed: 10,
  douban_future_days: 3,
  douban_min_want: 0,
  // ---------------- Simkl
  simkl_client_id: '',
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
  config_version: 3,
  // ---------------- 一次性执行
  onlyonce: false,
}

/** 返回默认配置的深拷贝（避免多处共享同一份可变对象）。 */
export function defaultConfig() {
  return JSON.parse(JSON.stringify(configDefaults))
}
