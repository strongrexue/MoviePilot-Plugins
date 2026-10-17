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
  tmdb_future_days: 30,
  bangumi_future_days: 30,
  min_rating_tmdb: 6.0,
  min_rating_bangumi: 6.0,
  min_rating_douban: 6.0,
  min_rating_simkl: 6.0,
  min_popularity: 10.0,
  // ---------------- 豆瓣 RSS 源列表
  douban_rss_sources: [],
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
  // ---------------- 一次性执行
  onlyonce: false,
}

/** 返回默认配置的深拷贝（避免多处共享同一份可变对象）。 */
export function defaultConfig() {
  return JSON.parse(JSON.stringify(configDefaults))
}
