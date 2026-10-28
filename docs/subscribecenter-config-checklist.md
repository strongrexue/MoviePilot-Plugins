# 胖虎订阅中心 · 配置清单（国产剧 + 番剧 + 院线新片 向）

> 适用场景：以**国产剧 / 番剧国创 / 院线新片**为主，美剧日剧韩剧为辅，不看冷门，资源以 PT 为主。
> 目标：把每天 30 条额度花在「真的会看、PT 真的有资源」的条目上。

---

## 1. 一页速查

| 项 | 设成 | 说明 |
|---|---|---|
| TMDB 源 `enable_tmdb` | **关（false）** | 电影档期由豆瓣 `movie_coming` 覆盖，美剧由 `tv_american` 覆盖 |
| AniList 源 `enable_anilist` | **开（true）** | 番剧当季表 + 国创 |
| AniList 含国漫 `anilist_include_donghua` | **开（true）** | 国创只有 AniList 覆盖得住 |
| Bangumi 源 `enable_bangumi` | **关（false）** | 只当标题翻译层用，不当源 |
| 豆瓣榜单 `enable_douban_rss` | **开（true）** | 主力源 |
| 每个榜单取前 N 条 `douban_max_items_per_feed` | **20**（现 30） | 榜单按名次排，前 20 已覆盖绝大多数 |
| 豆瓣想看门槛 `douban_min_want` | **300** | 只对 coming 类生效（榜单类没有想看数，缺失即放行） |
| 豆瓣评分门槛 `min_rating_douban` | **6.0**（不变） | 榜单类无评分的条目会放行，不会误杀 |
| 每日额度 `daily_limit` | **30**（不变） | 有 30 条足够消化 |
| 身份解析并发 `resolve_concurrency` | **8**（不变） | 再高容易触发 TMDB 限流 |
| 电影发行日兜底 `movie_release_fallback` | **开（true）** | 走 TMDB **依赖**，关掉 TMDB 源不影响它 |
| 电影宽限 `movie_release_grace_days` | **7**（不变） | 数字版上线后才有种 |
| 番剧压季精确订阅 `prefer_episode_group` | **开（true）** | 治「一季 60 集」的番剧订错集 |
| 五大平台首播源 | **待开发** | 上线后再关豆瓣 `tv_coming`（见第 5 节） |

---

## 2. 数据源开关（逐个说清取舍）

### 2.1 关掉 TMDB 源 `enable_tmdb = false`

你已有的覆盖：

| 需求 | 谁覆盖 |
|---|---|
| 院线新片档期 | 豆瓣 `movie_coming`（带精确上映日期） |
| 美剧 | 豆瓣 `tv_american`（开播日期由 resolver 查 TMDB 补） |
| 国产剧 | 豆瓣 `tv_domestic` / 新片榜 / 口碑周榜 |
| 番剧 / 国创 | AniList |

关掉后仅失去三点，都不是必需：
1. **零标题匹配风险**（TMDB 源自带 id，`sources/tmdb.py:25` 不做标题匹配）；
2. **不依赖 RSSHub 的备份**——豆瓣全线依赖 RSSHub，它挂了豆瓣全灭，TMDB 源是唯一直连备份；
3. **全球库覆盖**（冷门外语片豆瓣没条目时 TMDB 有）。

> **容易误解的一点**：关掉 TMDB **源**之后，`movie_release_fallback`（用 TMDB 补电影发行日）、identity 解析、番剧季集查询**照常工作**——那些走的是 TMDB **依赖**，两回事。

### 2.2 AniList

| 键 | 值 | 说明 |
|---|---|---|
| `enable_anilist` | true | |
| `anilist_include_donghua` | true | 国创默认开 |
| `anilist_future_days` | 3 | 番剧定档密集，窗口不用长 |
| `anilist_min_popularity` | 1000 | AniList 热度量纲与 TMDB 完全不同，别抄 TMDB 的 15 |
| `min_rating_anilist` | 6.0 | AniList 权重分普遍低一档 |

### 2.3 Bangumi：保持关闭

`enable_bangumi = false`。它的价值是**标题翻译**（日文原名 → 中文名），不是发现源。

---

## 3. 豆瓣榜单：开哪些、取多少

### 3.1 你现在的状态（默认值就是「即将」两条开着）

`core/constants.py:175-288` 里 14 条路线的出厂状态：

| 路线 | 出厂 | 建议 | 理由 |
|---|---|---|---|
| `/douban/movie/coming` 豆瓣电影-即将上映 | **开** | **保持开** | 电影档期唯一来源，唯一带精确日期的路线 |
| `/douban/tv/coming` 豆瓣剧集-即将播出 | **开** | **现在先留着，平台源上线后关** | **它没有日期**（`douban_rss.py:161-162`），价值会被平台源完全覆盖 |
| `/douban/list/tv_domestic` 豆瓣 - 近期热门国产剧 | 开 | 开 | 国产剧主力 |
| `/douban/list/show_domestic` 豆瓣 - 近期热门国内综艺 | 开 | **可关** | 综艺在 MP 里没有集数概念，订了也只是空转 |
| `/douban/list/tv_animation` 豆瓣 - 近期热门动画 | 开 | **可关** | 与 AniList 重复，且番剧用 AniList 更准 |
| `/douban/list/movie_real_time_hotest` 豆瓣 - 实时热门电影 | 开 | 开 | 已上映热门，配合 7 天宽限能捞到刚上数字版的 |
| `/douban/list/movie_hot` 豆瓣 - 新片榜 | 开 | 开 | 最近上映的新片（30 条），比「豆瓣热门」更贴订阅目的 |
| `/douban/list/movie_weekly_best` 豆瓣 - 一周口碑电影榜 | 关 | 开 | 高分电影，值得洗版 |
| `/douban/list/tv_japanese` 豆瓣 - 近期热门日剧 | 关 | 看你 | 五大平台不覆盖日剧，只能靠它 |
| `/douban/list/tv_korean` 豆瓣 - 近期热门韩剧 | 关 | 看你 | 同上 |
| `/douban/list/tv_american` 豆瓣 - 近期热门美剧 | 关 | **开**（替代 TMDB 源的关键） | 关掉 TMDB 源后美剧只靠它 |
| `/douban/list/tv_documentary` 豆瓣 - 近期热门纪录片 | 关 | 慎开 | 多为完结片，订了立刻「没有新集」 |

> **1.15.0 起出厂榜单已按实测换血**：删掉 4 条零独有路线（`tv_real_time_hotest`、
> `recommended/tv`、`tv_chinese_best_weekly`、`tv_global_best_weekly`），综艺榜从
> 已 503 的 `tv_variety` 换成 `show_domestic`，新增 `movie_hot`（新片榜）。
> 升级时会自动迁移：同名路线上的开关/条数/窗口/想看门槛原样搬过来，
> 被删的路线的设置丢弃，你自己加的额外 RSS 保留。

### 3.2 每个榜单取几条

`douban_max_items_per_feed = 20`（单条路线也可以用 `max_items` 单独覆盖，0 = 用全局值）。

依据：`constants.py:384` 的实测注释——`/douban/list/tv_hot` 单条路线就有 **241 条**，不限量会把额度吃光。

**重合提醒**：`tv_domestic` 与 `show_domestic`（综艺）基本不重合；原先那三条国产剧热门榜（`tv_real_time_hotest` / `tv_domestic` / `tv_chinese_best_weekly`）在 1.15.0 里删掉了两条零独有的，现在只剩 `tv_domestic`，不必再纠结取舍。

---

## 4. 三把闸门（为什么这么设）

流水线顺序（`core/pipeline.py:687`）：

```
源内去重 → 黑名单 → 身份解析 → 过滤（跨源去重/评分/关注度/窗口）→ 额度 → 写入
```

| 闸门 | 键 | 建议值 | 作用 |
|---|---|---|---|
| 评分 | `min_rating_douban` | 6.0 | 榜单类没评分的条目会放行（`filter_by_rating` 对 `None` 不拦） |
| 关注度/想看 | `douban_min_want` | **300** | 专治「只在小规模点映」的电影，这类 PT 基本 0 资源 |
| 窗口 | `douban_future_days` | 3（coming 类可单独设 30） | 榜单类没有日期，窗口对它无效 |
| 额度 | `daily_limit` | 30 | 按关注度降序花（`pipeline.py:568`），重复不占额度 |

> **`douban_min_want = 300` 为什么只影响电影**：只有 coming 类路线带「想看：27357」这种字段，榜单类没有 → 缺失即放行。所以它天然只拦电影，不会误杀国产剧。

---

## 5. 两个阶段

### 阶段一：现在就能做（不含平台源）

1. 关 TMDB 源：`enable_tmdb = false`
2. 开 `movie_real_time_hotest` / `movie_hot`（出厂已开）/ `movie_weekly_best` / `tv_american`
3. 视需要关 `show_domestic` / `tv_animation` / `tv_documentary`（综艺无集数、与 AniList 重复、纪录片多已完结）
4. `douban_max_items_per_feed = 20`、`douban_min_want = 300`
5. AniList 确认：`enable_anilist = true` + `anilist_include_donghua = true`
6. **保留** `tv_coming`（平台源还没上线，先别关）

### 阶段二：平台首播源上线后

1. 关 `tv_coming`（`enabled = false`）——它没日期，被平台源完全覆盖
2. `movie_coming` 留着：平台源可覆盖，但豆瓣这条带「想看」数，质量信号更好；两条同时开也行，跨源合并会去重
3. 平台源按平台单独开关，先只开腾讯 + 爱奇艺，跑一周看 TMDB 命中率

---

## 6. 保存与验证

**保存顺序**：一次改完再点保存（宿主 `update_config()` 是整份覆盖，中途保存不会丢，但会多跑一轮）。

**验证三步**：

1. 手动点「立即运行一次」；
2. 看运行摘要的 `sources` 区块（`pipeline.py:120-128`）：`tmdb` 应该消失或 `skipped`，`douban_rss` 条数应为几百；
3. 看「待确认」列表：如果还有 `tmdb` 来源的条目，说明开关没生效（配置没保存成功）。

**看漏没漏**：连续观察一周「已订阅」的新增。国产剧/番剧每天 0–3 条是正常值（`config_migrations` 里记着实测：TMDB 窗口 3 天时一周约 4 条）。

---

## 7. 十个坑（按踩到概率排序）

1. **RSSHub 挂了你全灭**：豆瓣全线走 `rsshub_domain`，公共实例经常限流。建议自建，或至少准备一个备用域名。
2. **`tv_hot` 241 条**：不限量会把额度吃光（`constants.py:384` 原话）。
3. **豆瓣榜单没有日期**：剧集靠「TMDB 还有没有未播集」判定，所以**只要还在播就会被当候选**，量大属正常。
4. **电影点映噪音**：豆瓣 coming 会把小规模点映片列进来，靠 `douban_min_want = 300` 挡。
5. **关掉 TMDB 源 ≠ 不依赖 TMDB**：identity 解析、发行日兜底、番剧季集查询都还要 TMDB。
6. **AniList 热度量纲**：别把 TMDB 的 15 抄过来，AniList 冷门番 500–2000、主流 2 万–5 万。
7. **番剧季号错位**：国产动画常被 TMDB 建模成「1 季 110 集」，`prefer_episode_group = true` 才能只追当季那 12 集。
8. **自动启停与人打架**：如果你还装了「订阅助手增强版」并开了「增强暂停」，会与本插件的「播出日自动启停」互相改状态。**只留一个**。
9. **`filter_original_language`**：默认只留 `zh,ja,ko,en`。关掉 TMDB 源后影响面变小，但豆瓣条目仍会过这道筛。
10. **额度是全局的**：`daily_limit = 30` 是「写入订阅」的条数，不是「拉取」条数；拉取几百条是正常的，不代表要订几百部。

---

## 8. 回滚

想把 TMDB 源换回来：`enable_tmdb = true` 即可，其余配置不用动（跨源合并会按「定档日期更早、其次评分更高」自动取优，`pipeline.py:250-255`）。

想临时停掉自动订阅又保留配置：关 `enabled`（总开关），不要删配置。

---

## 9. 你那 15 条榜单逐个定档（2026-10-28 实测）

实测环境：`http://192.168.50.134:1200`，每条 `?format=json&limit=100`。15 条全部可用，共 **339 条**，跨榜单去重后 **279 条**。

**关键实测结论**：豆瓣榜单类条目的字段只有 `content_html / title`（部分带 `url / id`），**没有评分、没有想看数、没有日期**。所以：

- `min_rating_douban` 对豆瓣源**等于没设**（评分缺失即放行）；
- `douban_future_days` 对榜单类**无效**（没有日期可判）；
- `douban_min_want` 只有两条 coming 有效——而且**剧集那条目前解析不到**（见 9.3 的 bug）。

### 9.1 重合度实测：4 条路线「零独有」

| 路线 | 条数 | 与他榜重复 | 独占 |
|---|---|---|---|
| `tv_real_time_hotest` 实时热门电视 | 10 | 10 | **0** |
| `recommended/tv` 定档新剧推荐 | 20 | 20 | **0** |
| `tv_chinese_best_weekly` 华语口碑榜 | 10 | 10 | **0** |
| `tv_global_best_weekly` 全球口碑榜 | 10 | 10 | **0** |
| `tv_domestic` 国产剧 | 50 | 20 | 30 |
| `tv_american` 美剧 | 50 | 10 | 40 |
| `tv_animation` 动画 | 39 | 4 | 35 |
| `tv_japanese` 日剧 | 31 | 6 | 25 |
| `show_domestic` 国内综艺 | 26 | 2 | 24 |
| `tv_korean` 韩剧 | 24 | 9 | 15 |
| `movie/coming` 电影即将上映 | 20 | 0 | 20 |
| `tv_documentary` 纪录片 | 19 | 5 | 14 |
| `tv/coming` 剧集即将播出 | 10 | 1 | 9 |
| `movie_real_time_hotest` 实时热门电影 | 10 | 3 | 7 |
| `movie_weekly_best` 电影口碑榜 | 10 | 3 | 7 |

**那 4 条零独有的路线，关掉一条内容都不会少**，只省下每条一次的 TMDB 解析。

另有两条内置默认不可用/不适配：
- `/douban/list/tv_variety`（老的「近期热门综艺」）**已 503**，1.15.0 起出厂直接用 `show_domestic`；
- `/douban/list/movie_hot`（豆瓣 - 新片榜，30 条）已作为出厂榜单（1.15.0），是 `movie/coming` 的好补充。

### 9.2 建议配置

**方案 A · 精简（7 条，候选约 130 条/天）**

| 路线 | 每榜取 | 想看门槛 | 说明 |
|---|---|---|---|
| `movie/coming` | 全部（20） | 1000 | 院线新片，唯一精确日期 |
| `tv/coming` | 全部（10） | 3000 | 平台源上线后再关 |
| `tv_domestic` | 30 | — | 国产剧主力 |
| `tv_animation` | 20 | — | AniList 为主，这条作补充 |
| `tv_american` | 30 | — | 关掉 TMDB 源后美剧唯一入口 |
| `movie_real_time_hotest` | 全部（10） | — | 刚上数字版 |
| `movie_weekly_best` | 全部（10） | — | 高分片洗版 |

**方案 B · 全都要（9 条）**：A + `tv_japanese` 20 + `tv_korean` 20。

**建议关闭（4 条）**：`tv_real_time_hotest`、`recommended/tv`、`tv_chinese_best_weekly`、`tv_global_best_weekly`（零独有）。
**慎开（2 条）**：`show_domestic`（综艺在 MP 里没有集数概念，且 TMDB 常查不到 → 进「待确认」）、`tv_documentary`（多为完结片，订了立刻「没有新集」）。要开就把 `max_items` 压到 10。

### 9.3 一个必须修的 bug

`sources/douban_rss.py:53` 的正则是 `_WANT_COUNT = re.compile(r"想看[：:]\s*([\d,]+)")`，但 **`/douban/tv/coming` 的文案是「想看人数：21035」**，中间多了「人数」两个字 → 实测 **10 条里 0 条解析到**，剧集那条的想看门槛**完全失效**（缺失即放行）。

对比实测：

| 路线 | 现有正则 | 放宽成 `想看(?:人数)?[：:]` |
|---|---|---|
| `movie/coming` | 20/20 | 20/20 |
| `tv/coming` | **0/10** | 10/10 |
| `tv_domestic` / `tv_american` | 0/50 | 0/50（榜单类本来就没有） |

修法一行：`re.compile(r"想看(?:人数)?[：:]\s*([\d,]+)")`。**这一条等你发话再改。**

### 9.4 额度与顺序（容易被忽略）

- 排序键是「关注度降序」（`pipeline.py:295` `selection_sort_key`），而豆瓣条目 popularity 全是 `None → 0`，**全部并列**，于是实际顺序退回「榜单在配置里的先后」。
- 也就是：**越靠前的榜单越先花掉当天 30 条额度**。想优先订口碑片，得把口碑榜往前放——但当前 UI 没有上移/下移按钮，只能靠「关掉别的榜单」间接实现（这也算关掉冗余榜的额外收益）。
- 已订阅过的条目不会重复占额度，所以额度主要被「首次运行」和「新上榜」消耗。

---

## 附：本文档修正的两处说法

1. 我此前说「豆瓣默认榜单里没有 coming 列表」——**错的**。`constants.py:176-191` 里 `movie_coming` 和 `tv_coming` 出厂就是 `enabled: True`，只是豆瓣总开关 `enable_douban_rss` 默认关，所以你打开总开关后它们就已经在跑了。
2. 我此前说「关掉 TMDB 源后电影发现基本归零」——**只在没开 `movie_coming` 时成立**。你两条 coming 都开着，所以电影档期有覆盖。
