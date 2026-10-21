# 胖虎订阅中心（SubscribeCenter）

MoviePilot V3 插件。**只做三件事：发现 → 去重 → 写订阅。**

版本控制、洗版、下载优先级全部由 MoviePilot 后台订阅下载优先级规则接管，插件不介入。

---

## 当前进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| P0 | 插件骨架、配置、调度、异步桥接、结构化日志 | ✅ 0.1.0 |
| P1 | TMDB 数据源 + 订阅写入 + 身份 L1 直通 | ✅ 0.1.0 |
| P2 | 插件自有表（发现流水 / 映射缓存） | ⬜ |
| P3 | Vue 联邦前端（配置页 / 详情页 / 仪表盘） | ⬜ |
| P4 | Bangumi 源 | ⬜ |
| P5 | 豆瓣 RSS（RSSHub）+ 待确认列表 | ⬜ |
| P6 | Simkl Calendar | ⬜ |
| P7 | JustWatch（可选，默认关） | ⬜ |

> **0.1.0 只有后端。** 配置页/详情页/仪表盘尚未实现，但后端已可独立运行：
> 在宿主的插件配置接口里保存配置、用 `POST /api/v1/plugin/SubscribeCenter/run_once`
> 触发一次发现，或等每日 03:00 的定时任务。

## 数据源

| 源 | 状态 | 说明 |
|---|---|---|
| **TMDB** | ✅ 已实现 | 全球电影/剧集，自带 TMDB id（身份最可靠） |
| **AniList** | ✅ 已实现 | 番剧 + 国漫；官方 GraphQL，自带开播日、在播状态、集数与热度 |
| **豆瓣 RSS** | ✅ 已实现 | 经 RSSHub 的豆瓣路线；上映日期与豆瓣 ID 均可解析 |
| Simkl | ⬜ 未实现 | 需要 Simkl client_id |
| JustWatch | ⬜ 未实现 | 可选，只记日志 |

### 为什么是 AniList，而不是 Bangumi（1.0.0 的取舍）

实测（2026-10）三条硬数据：

1. `api.bgm.tv/calendar` 当季 **108 部**，拿 6 个知名国漫去对，**只有牧神记5 出现**
   —— 凡人修仙传 / 斗破苍穹 / 遮天 / 吞噬星空 / 完美世界全都不在；
2. AniList 全部覆盖，且 `countryOfOrigin: CN` 条目的 `title.native` **就是中文原名**；
3. AniList 的连载通道能按 `nextAiringEpisode`（下一集播出时间）判断窗口。

**Bangumi 因此降级为内部「标题翻译层」**：日番在 AniList 里是日文原名，而 TMDB
搜日文命中率为 0（实测 `ライフトレード` / `虚ろな十字架` 都是 0 条），
`HostTmdbResolver.bangumi_aliases` 会用 Bangumi 的 `name_cn` 换成中文名再搜。
它不再出现在数据源开关里。

### 豆瓣 RSS 的实机结论（0.7.0 / 0.8.0）

实测环境：RSSHub diygod/rsshub:latest，宿主容器可直连。

豆瓣路线分三类，**实测行为完全不同**（以此为准，别照旧文档写）：

| 类别 | 路线示例 | 有日期 | 有豆瓣 id | 插件如何处理 |
|---|---|---|---|---|
| **电影上映** | /douban/movie/coming | 有（精确到日） | 有 | 按时间窗口过滤，**最准，推荐** |
| **剧集**（含榜单） | /douban/tv/coming、/douban/list/tv_*、/douban/recommended/tv | 无 | 部分有 | 无日期 → 改用「TMDB 还有没有未播集」判定（等效追番） |
| **电影榜单** | /douban/list/movie_weekly_best | 无 | 有 | 无日期 → **跳过**（老片居多，订了浪费额度） |
| 已下线 | /douban/movie/ustop250、/douban/movie/new | — | — | 新版 RSSHub 已 404 |

实测 15 条路线（每条上限 10）：剧集类全部可用，电影榜单类会被跳过。

**为什么剧集类没有日期也能用**：正在连载的剧本来就没有「上映日」，它的
「是否即将有内容」由 TMDB 的剧集数据回答（见上面的季号裁决规则）。这比
时间窗口更准，也正是追番应有的行为。

**注意候选量**：/douban/list/tv_hot 单条就有 241 条，因此有每榜单上限
（douban_max_items_per_feed，默认 10）。配太多榜单会让每次运行要做的
TMDB 查询变多，首次运行会明显变慢（之后走映射缓存会快）。建议只开 2~4 个。

**想看数不冒充 popularity**：豆瓣想看数动辄上万，与 TMDB popularity 量纲
完全不同，塞进去会让关注度门槛形同虚设。按接入契约只放进 raw 供排查。

**「重映老片」会被年份校验挡掉（有意为之）**：实测电影类 15 条里 13 条能
搜到同名 TMDB 条目，但其中「疾速追杀」（2014）、「笑傲江湖2：东方不败」
（1992）、「戴帽子的猫」（2003）在豆瓣的上映日期是 2026 —— 那是**中国重映**。
电影走年份严格校验，这类会被跳过；而「生日快乐」（TMDB 2007 / 豆瓣 2026）
则是纯粹的同名假匹配，同样被挡掉。即：**只订 TMDB 年份与上映年份一致的电影**。

### Bangumi 源的两个实机结论

1. **只有 https://api.bgm.tv 可用** —— pi.bangumi.tv 与 gm.tv 实测均失败。
2. **/v0/subjects?air_date=... 的过滤被服务端忽略**（实测传「>=今天」仍返回全库
   29601 条、从 2029 年倒序），所以只能用 /calendar（当季番列表 + 本地按
   ir_date 过滤）。局限：只覆盖当季，季末切档前后可能漏下季刚定档的番。
3. **条目不带 popularity**，因此不参与「最低关注度」门槛 —— 这是有意的：
   当季番列表本身是策展的，用 TMDB 的关注度量纲去卡它没有意义。

**已实现的数据源：TMDB / AniList / 豆瓣 RSS。** 在配置里打开 Simkl / JustWatch
不会报错，但会在日志中明确记录「已启用但当前版本尚未实现，本次跳过」——
不会静默无输出。Bangumi 不再是数据源（见上文「为什么是 AniList」）。

---

## 数据源接入契约（新增源必须遵循）

**这是 0.6.0~0.6.7 返工 6 次换来的教训，写在这里防止重犯。**

### 核心原则：让 TMDB 裁决，不要让来源方的命名规则裁决

同一个「第 N 期/第 N 季」，在不同来源里含义可能完全相反：

| 内容类型 | Bangumi 写法 | TMDB 建模 | 正确做法 |
|---|---|---|---|
| 国产动画 | 牧神记5 | **单季多集**（第 1 季 110 集，第 105 集起） | 忽略「5」，订第 1 季 |
| 日番 | 边缘行者 2 | **严格分季**（第 2 季才是新内容） | 订第 2 季 |

任何解析标题决定季号的规则都必然在其中一半场景出错。正确做法是：
**把来源标题里的季号当「提示」，问 TMDB「你哪一季还有未播集」，由数据裁决。**

实现在 IdentityResolver._resolve_target_season +
HostTmdbResolver.resolve_target_season：

1. 列出 TMDB 所有季（排除第 0 季特别篇），找出**有未播集**的季；
2. 一个都没有 → 不可订（匹配到旧季/已完结）；
3. 提示季正好是其中之一 → 用它；
4. 只有一个季有未播集 → 用它；
5. 其余（多候选且提示对不上）→ 用默认季。

### 新源只需要做「发现」，不要做「身份判定」

新增一个源（豆瓣 RSS / Simkl / JustWatch …）只需实现
sources/ 下的一个适配器，产出 DiscoveredItem：

`python
DiscoveredItem(
    source=SOURCE_XXX,          # 源标识
    source_id=str(native_id),   # 本源内 id
    title=标题,                  # 用于搜索 TMDB
    media_type=movie / tv,
    release_date=YYYY-MM-DD,  # 窗口过滤的唯一依据
    year=YYYY,
    rating=评分或 None,          # 没有就 None，不要用别的字段冒充
    popularity=关注度或 None,    # 没有就 None（缺失时自动跳过关注度门槛）
    native_ids={xxx: native_id},  # 供宿主跨源换算
    special=is_special(title),  # 特别篇/OVA/番外要标出来
)
`

**以下一律不要自己做**，全部由源无关层统一处理：

| 职责 | 归属 | 原因 |
|---|---|---|
| 媒体身份解析（L1~L4） | IdentityResolver | 各源自己判会不一致 |
| 季号裁决 | 
esolve_target_season | 见上：必须由 TMDB 数据裁决 |
| 「是否已播完」判定 | 同上 | 订已完结的旧季纯属浪费 |
| 订阅去重（含季号） | SubscriptionWriter | 多源共用 |
| 每日上限 / dry-run | SubscriptionWriter | 多源共用 |
| 特别篇处理 | writer 按 special 标记 | 统一给出明确原因 |

### 三条硬性要求

1. **失败要抛异常**，不要静默返回空列表 —— 让流水线把该源标记为「失败」，
   而不是伪装成「今天没有新内容」。
2. **缺失的数值就填 None**，不要拿别的字段凑（真机事故：把 Bangumi 的
   
ating.total（投票数，个位数）当 popularity，会被关注度门槛整体误杀，
   等于该源静默失效）。
3. **窗口天数用本源的键**（	mdb_future_days / angumi_future_days …），
   流水线按源取窗口与评分门槛，不要共用一个值。

### 唯一真相来源

DiscoveredItem.writable 是「能不能写」的唯一判定，它同时校验
身份置信度（L1~L3）、非特别篇、还有未播内容。不要在各处分散判断 ——
真机事故正是「身份看起来可写」但「内容已播完」，结果仍被写入订阅。

### episode group：被压成单季的番剧（0.8.3）

有些番剧在 TMDB 被压成「一季多集连续编号」。真机案例《药屋少女的呢喃》：

    TMDB 220542: number_of_seasons=1, number_of_episodes=60
    第 1 季：60 集，第 49~60 集才是第 3 季（下一集 2026-10-23 第 52 集）

若按 season=1 订阅，宿主要去补前 48 集旧番（真机订阅记录
	otal_episode=60, lack_episode=33，等于把整部老番重扫一遍）。

但 TMDB 的 episode_group（type=6「Seasons」）里 **Season 3 = 12 集**
（2026-10-02 ~ 12-18，9 集未播）。因此本插件会：

1. 常规季里没有「第 N 季」时，去 episode group 找同序号的季；
2. **只有该季确实还有未播集**才采用（已播完的季不采用，避免白订）；
3. 订阅时同时传 season=3 与 episode_group=<id>，宿主便只追这 12 集。

真机实测（220542）：

| 条目 | 裁决 |
|---|---|
| 药屋少女的呢喃 第三季 | 可订，季=3，group=6782169d… |
| 药屋少女的呢喃 第二季 | 可订，季=1，无 group（该季已播完） |
| 牧神记5 | 可订，季=1，无 group（TMDB 无分组，行为不变） |

配置项 prefer_episode_group（默认开）。关掉则按整季订阅。

### 重新订阅已完成过的条目（0.8.5）

宿主把订阅标成「完成」时会移入 subscribehistory。用户诉求：从媒体库删掉
文件后希望能重新订阅，所以**默认不再按订阅历史拦截**（
esubscribe_completed
默认开）。真正「已经播完」的剧不会因此重复订阅 —— 它们会先被
「TMDB 已无未播内容」拦住。

### 流水记过就不再自动重订（1.13.6）

宿主的「这条订阅还在不在」只反映**当下**：用户把订阅删了，宿主就查不到了，
下一轮发现又会把它订回来。反复删、反复订，是这套自动化的老毛病。

1.13.6 起，写入前多查一道**插件自己的发现流水**：

| 情况 | 结果 |
| --- | --- |
| 流水里记着这部（`added` / `skipped_already_subscribed`） | 跳过，决策 `skipped_recorded`（「流水已记录」） |
| 流水里没有记录 | 正常订阅 |
| 「待确认」「窗口外」「评分不足」这类记录 | **不算**，照常继续判 |

只认「真的动过手」的两条决策：`added`（订上了）与
`skipped_already_subscribed`（宿主那边本来就有）。「待确认」「窗口外」「评分
不足」这些都没订过，不能因为它们出现过就永久拒绝 —— 否则一部片在窗口外被扫到
一次，就再也订不上了。

**解锁方式就是清空流水**：发现流水页右上角的「清空流水」（`POST
/history/clear`）。清掉之后，「流水记过」这条规则立刻失效，之前订过又被删掉的
作品会在下一轮重新被订阅。删掉单条记录同理。

开关是 `dedupe_by_history`（默认开）。键里带季号，第 1 季的记录不会挡住第 2 季。

### 结构哨兵（0.8.5）

	tests/v3/subscribecenter/test_host_structure.py 只做结构断言：HostTmdbResolver
必须提供 search / search_raw / convert_to_tmdb / 
esolve_target_season
等方法，HostSubscribeBackend.add 必须接受 episode_group。

写这个文件的原因：0.8.4 修 bug 时用「切片替换」改代码，把夹在中间的

esolve_target_season 与 convert_to_tmdb **整段删掉了**。单元测试全绿
（测试用的是假 resolver），真机表现却是「黑帮领地本该订第 2 季却订了第 1 季」。

## 工作方式

1. **首次运行强制 dry-run。** 不管配置怎么设，第一次跑只记录不写入，并在流水里
   标注。确认结果后，用 `POST /run_once` 或等下一次定时任务，之后按 `dry_run`
   配置执行。
2. **身份分级 L1–L4，L4 永不写入。**
   - L1：来源自带确定性 ID（TMDB / IMDb / TVDB / Bangumi / 豆瓣）→ 直接写入
   - L2：已确认的映射缓存 → 直接写入
   - L3：标题 + 年份精确搜索，**年份硬校验通过**才写入
   - L4：只有标题相似度 → **只进待确认列表，永不写入**
3. **每日写入上限**默认 30 条（可配，建议不超过 50）。
4. **写入前实时复查**宿主的活跃订阅**与订阅历史**：
   宿主的 `async_add()` 只按身份幂等、**不查订阅历史**，而订阅完成后记录会移入
   `SubscribeHistory`。漏掉这一步会把「已经拿到过」的剧当新片重订。

---

## 播出日自动启停

订阅到两百条量级后，真正撑爆负载的不是「发现」，而是**宿主的订阅刷新**：
`subscribe_mode = spider`（默认）下宿主每天随机跑 **32 轮** `subscribe_refresh`，
每轮把状态为 `R` / `P` 的**全部**订阅拉进匹配循环逐条搜站点。
两百条订阅里绝大多数当天并没有新集，等于每天空转 6400 次逐条检查。

这个功能按「今天到底有没有该搜的集」把订阅分成两堆，每天改一次状态：

| 情况 | 判定 | 动作 |
|---|---|---|
| 有已播但没入库的集，且最近一集距今 ≤ `auto_toggle_keep_days` | 还在等出种 | 保持 / 恢复 `R` |
| 最近 `auto_toggle_lookahead_days` 天内有集要播 | 要开搜了 | 保持 / 恢复 `R` |
| 全部已播已入库 | 这一季搜完了 | 暂停 `S` |
| 首集还没播（超出提前天数） | 还没到搜的时候 | 暂停 `S` |
| 缺集但已超保留天数，且窗口内没有新集 | 确实找不到，别耗了 | 暂停 `S` |

判定基准是插件时区下的**本地日期**，默认 `00:05` 跑，早于订阅刷新。

### 电影订阅（`auto_toggle_movie_enabled`，默认开）

电影没有「集」，也没有下一集播出日，唯一的时间锚点是 TMDB 的**发行日**，
所以单独一套判定：

| 情况 | 动作 |
|---|---|
| 还没到发行日（含提前天数） | 暂停 `S`，等出种 |
| 发行日 ~ 发行日 + `auto_toggle_keep_days` | 保持 / 恢复 `R` |
| 过了窗口还没入库 | 暂停 `S` |
| TMDB 没有任何可用发行日期 | 一动不动 |

两个关键细节：

- **基准日不是顶层 `release_date`。** 那是首映/院线日期，而订电影等的是
  WEB-DL（跟**数字发行** `type=4` 走）、洗版等的是原盘/REMUX
  （跟**实体发行** `type=5` 走），分别比首映日晚几周到几个月。拿首映日当
  基准，电影订阅会正好在真正出种的那几周被判「窗口已过」而暂停。
- **不看「已入库」。** 洗版订阅入库后宿主会故意保持 `R` 等 `priority=100`
  的资源（`completion.py` + `priority.py`），`note=[1]` 只说明下过一个版本。
  拿「已入库」当停止信号，洗版电影会永远搜下去。


### 洗版订阅（`auto_toggle_best_version_mode` / `auto_toggle_best_version_keep_days`）

开了洗版（含**按分集洗版**）的订阅，判定口径不一样 ——「下了 1080」不等于
「不用再搜」：

- 宿主对洗版订阅**入库后不归档**，而是继续找 `priority` 更高的资源
  （`priority.py` 的 `get_best_version_interested_episodes`）；只有
  `episode_priority` 里 `priority == 100` 才算洗到头；
- 「洗到顶没有」按 `episode_priority` 算，**不看 `note`**。

**什么时候按洗版口径判**由 `auto_toggle_best_version_mode` 决定：

| 取值 | 行为 | 适用 |
|---|---|---|
| `after_finale`（默认） | 本季**已完结**（TMDB 播出表里没有晚于今天的集）后才按洗版判：没洗到顶就继续 `R`，最多 `auto_toggle_best_version_keep_days` 天（默认 90）；播出期照普通订阅判 | 绝大多数人 |
| `always` | 播出期也算「没洗到顶 = 还要搜」 | 想全程蹲洗版的人，代价是这些订阅基本不会被暂停 |

为什么默认 `after_finale`：宿主在播出期只下「首个可用版本」，真正的洗版
（原盘/REMUX/BD）是季终之后才陆续有资源。播出期就按洗版判，等于让所有洗版
订阅长期 `R`，与「按播出日暂停」的初衷正好相反。


### 日历和判定的关系

日历页（`/calendar`、`/calendar/day`）回答的是「哪天有更新」，自动启停回答的是
「今天该不该搜」—— 两个问题，但**日期口径必须一致**，否则会出现「日历上今天
上映、订阅却还在等发行日」这种自相矛盾的画面：

- **电影的日历条目用发行日**：普通订阅取数字发行（type=4），洗版取实体发行
  （type=5），拿不到发行记录才退回 TMDB 顶层 `release_date`。与判定完全同源，
  条目上会标「数字发行 / 实体发行」。
- **今日列表带「今天会搜 / 今天不搜（原因）」**：数据来自 `auto_toggle_plan()`，
  和「只看不改（预览）」是同一份判定。查历史 / 未来日期时不标 —— 那时的
  「今天会不会搜」没有意义。
- 不给月度网格做判定：200 条 × 31 天的全量判定没必要，翻月只修正日期口径。

### 缺集是怎么算出来的（`auto_toggle_library_check`）

先要说清一件事：**宿主的「已下载」只记它自己下过的集**（`Subscribe.note`，
唯一写入者是 `completion.py`）。媒体库导入、手动下载、删掉重订都不会写它，
所以对这类订阅，插件只能拿「播出表减去 `note`」倒推缺集 —— 结果就是
「你库里明明有 180 集，它报缺 180 集」。

处理的顺序（并集，只会**减少**误报缺集，不会因此误暂停）：

| 数据源 | 成本 | 什么时候用 |
|---|---|---|
| `Subscribe.note` | 0 | 永远 |
| 媒体库快照 `MediaServerItem.seasoninfo` | 一次 SQL | 打开核对开关就并进来 |
| 实时探针 `DownloadChain().get_no_exists_info` | 每条 2 次媒体服务器请求 | 快照没盖住、且真有已播未入库的集 |

探针是**串行**的，每条之间等 `auto_toggle_library_probe_interval`（默认 1.5 秒），
整轮最多花 `auto_toggle_library_probe_budget_seconds`（默认 300 秒）。到点就停，
剩下的标「待核对」，下一轮接着来。**没有跨天缓存**：有已播未入库的集就每轮重新核对
（待核对集为空时根本不发请求）。

**探针只在「立即执行」里跑，预览永远不发请求。** 理由是真机踩过：把核对塞进
HTTP 请求里同步跑，几分钟没有响应，网关直接 502。所以现在：

- 「只看不改（预览）」= 读 `note` + 读媒体库快照 + 沿用上一轮的核对结果，**零请求**；
- 「立即执行」= 后台线程里跑完整流程（探针 + 改状态），请求立刻返回，
  前端轮询 `last_run.running` 显示「后台执行中」；
- 上一轮还在跑（30 分钟内）或「发现任务」正在跑时，拒绝重复执行。

上一版插件把 200 条一次性并发问过去，把用户的 NAS 打挂了 —— 这就是为什么这里是
串行 + 间隔 + 时间预算，而且预算默认只够核对几十条。**预算设 0 = 只读快照，一个
请求都不发**。

界面上：缺集是推测的会标「推测」，并显示「库核对补上 N 集」；汇总行显示本轮
「快照 N 条 / 实探 M 条 / 待核对 K 条 / 沿用 N 条」以及耗时。

### 流水里的「重新订阅 / 加入订阅」

发现流水每条记录都有稳定键（`来源:ID`，没有确定性身份的退回 `来源:标题:年份`）：

- **已订阅过的**给「重新订阅」，其余给「加入订阅」；没有确定性身份（L4 待确认）
  的按钮直接不显示。
- 走 `/history/subscribe`，**故意绕开**窗口/评分/日限额/流水去重 —— 用户点名要订的
  东西不该被插件的门槛拦住。
- 订阅还在时**只回报「订阅中」**（附带宿主里的真实状态，如「已暂停」），
  绝不改它的状态：用户可能就是想让它暂停着。
- 真的写成功后**补一条流水**，所以「流水记过就不再自动重订」对这次手动操作同样生效。
- `episode_group` 会一起落库并回放 —— 番剧手动补订阅才不会订错季。

**点海报**可以新标签打开宿主的媒体详情页（`#/media?media_source=…&media_id=…&type=…`）。
只有拿到确定性身份的海报才可点。

### 三条安全约束（都踩过坑才知道要写）

1. **暂停只能写 `S`。** 宿主 `policy.get_states_for_search("R")` 返回的是 `"R,P"` ——
   `P` 是「待定（信息待进一步更新）」，**仍然会被搜索**；只有 `S` 被搜索链路排除
   （`search.py` 里 `current.state == "S" and not allow_paused_search`）。
2. **绝不用 `Subscribe.note` 存标记。** 那是宿主自己的「已下载集号」清单，
   `completion.py` 与洗版判定都靠它；往里写东西会让进度、完成判定全乱。
   接管记录存在插件自己的数据里（`auto_toggle` → `owned`）。
3. **只动自己暂停过的订阅。** 用户手动暂停的（`S` 且不在接管表里）一律不碰；
   自己暂停过的若被用户手动改回 `R`，则视为「用户接管」，立刻放弃这条，
   之后不再自动暂停它 —— 自动化与手动操作不能互相覆盖。

### 已知边界

- **电影按发行日**，且不参与「缺集」逻辑：没有集的概念，只看发行窗口。
- **洗版订阅用更长的保留窗口**（`auto_toggle_best_version_keep_days`，默认 90 天）：
  洗版等的是「更好的版本」，季终后 3 天就停等于白开洗版。
- `P`（待定）的订阅不参与：宿主还在补元数据，状态交给宿主。
- 没有 TMDB 播出表的（无 ID、取季失败）一律不动，不做猜测。
- 把**全部**订阅都暂停时，宿主的 `get_subscribed_sites()` 会返回空集合，
  而这个空集合的语义是「所有站点」—— 订阅刷新仍会抓一遍全站 RSS，
  只是不再逐条匹配。所以别指望「全暂停 = 零流量」。
- 洗版订阅在**季终后**按 `episode_priority` 的 `priority == 100` 判「不用再搜」
  （`auto_toggle_best_version_mode=always` 时播出期也按这套判）；播出期按
  `note` 判，与普通订阅一致。
- 「全部已播已入库」是暂停（`S`），不是标记完成：宿主的完成归档只在 `R`/`P`
  的匹配流程里发生，暂停后就轮不到它归档了。日历不受影响（日历本身包含 `S`），
  但这些条目会继续留在订阅列表里、不会自己进订阅历史。

---

## 排除规则（黑名单，1.14.0）

目标：**不想被自动订阅到的题材，别订**。以「同性剧」为例 —— 它不是 TMDB 类型
（见下），所以拆成「排除类型」和「排除题材」两个区来配。

只拦**自动发现**这一条线：命中的条目不写订阅，也不会被记成「订过」（清空流水
也解不开）。**已有订阅不受影响**，流水里的「重新订阅」按钮也不受限制。

### 排除类型（`blacklist_genre_movie` / `blacklist_genre_tv`）

按 TMDB genre id 精确匹配，电影与剧集分开配（两边类型表本来就不一样）。
条目自带 `genre_ids` 时直接比对；豆瓣 RSS 只有 `2026 / 韩国 / 恐怖 剧情` 这种中文串、
AniList 只有英文类型名 —— 两者都按 `core/blacklist.py` 的 `GENRE_ALIASES` 反查成 id。

> **别勾「剧情（18）」**：几乎每部片子都带这个类型，勾了整个源都会被拦掉。

### 排除题材（`blacklist_presets` / `blacklist_words`）

**内置预设默认一条都不生效**，勾选后才开始拦 —— 装插件的人不该被别人的口味静默
筛掉节目。目前 6 个预设：同性倾向、耽美 BL、百合 GL、综艺真人秀、脱口秀访谈、短剧。
勾选后界面会把「它到底匹配哪些词」摊开显示。

自定义词一行一个：

| 写法 | 含义 |
|---|---|
| `同性` | 中文按**包含**匹配（能命中「同性恋」） |
| `BL` | 英文按**整词**匹配（不会命中 `BLADE`） |
| `韩国 同性` | 空格分隔 = **同时包含**（只拦韩国同性题材） |
| `regex:^\[.+?\]` | 正则 |
| `case:Studio` | 区分大小写 |

### 三层过滤与代价

| 层 | 时机 | 代价 |
|---|---|---|
| 标题 / 原名 | 身份解析**之前** | 0 请求 |
| 来源题材串（豆瓣 `category`、AniList genres+tags） | 身份解析**之前** | 0 请求 |
| TMDB keyword | 只对「已过全部过滤、即将写入」的条目 | 每条 +1 请求（`blacklist_tmdb_keywords`，默认关） |

纯文本层必须排在解析之前：被拦的条目不该再花一次 TMDB 请求去解析身份
（参考 doubancenter 也在同一位置拦）。查关键词失败**放行**（fail-open）——
宁可漏拦一条，也不能因为网络抖动错杀一批。

### 为什么「同性」要单独走题材

TMDB 的 genre 表里**没有「同性」这个词**（电影 19 类、剧集 16 类，最接近的是「爱情」）。
`Shounen Ai` / `Yaoi` / `Boys Love` 也都不是 TMDB 官方类型。能拦住同性剧的只有：

1. 豆瓣 RSS `category` 里的中文字样（`剧情 同性`）—— 免费、最准；
2. 标题 / 原名里的词；
3. TMDB keyword（`lgbt` / `gay` / `homosexual` …）—— 要额外请求。

### 命中之后

- 流水里记一条 `skipped_blacklist`，原因写明命中哪一层、哪个词
  （如「命中排除题材（题材）：同性」）；
- **不算「订过」**：黑名单是规则，不是历史，清空流水不会因此解锁；
- 配置页有「试一下」：填片名 / 题材串，当场告诉你会不会被拦、命中哪条规则 ——
  黑名单是静默生效的，配完必须能自测，否则没人知道节目是被谁拦的。

---

## 配置项

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `enabled` | `false` | 插件总开关 |
| `enable_tmdb` | `true` | 启用 TMDB |
| `enable_anilist` | `true` | 启用 AniList（番剧 + 国漫） |
| `anilist_future_days` | `3` | AniList 发现窗口（天） |
| `anilist_min_popularity` | `1000` | AniList 最低热度（量纲与 TMDB 不同） |
| `anilist_include_donghua` | `true` | 包含国产动画（countryOfOrigin=CN） |
| `enable_bangumi` | `false` | 已废弃：Bangumi 降级为标题翻译层，不再作为源 |
| `enable_douban_rss` | `false` | 启用豆瓣 RSS（0.1.0 未实现） |
| `enable_simkl` | `false` | 启用 Simkl（0.1.0 未实现） |
| `enable_justwatch` | `false` | 启用 JustWatch（0.1.0 未实现） |
| `tmdb_future_days` | `30` | TMDB 发现窗口（天） |
| `min_rating_tmdb` | `6.0` | TMDB 最低评分 |
| `daily_limit` | `30` | 每日写入上限 |
| `dry_run` | `false` | 只记录不写入（首次运行仍强制一次） |
| `cron` | `0 3 * * *` | 每日执行时间，5 段式 cron |
| `timezone` | `Asia/Shanghai` | 时区 |
| `notify` | `false` | 是否发送运行摘要通知 |
| `discovery_page_enabled` | `false` | 是否在「发现」分区显示侧栏入口 |
| `auto_toggle_enabled` | `false` | 启用播出日自动启停 |
| `auto_toggle_cron` | `5 0 * * *` | 判定时间（5 段式 cron），建议早于订阅刷新 |
| `auto_toggle_lookahead_days` | `0` | 提前几天开始搜（0 = 只在播出当天） |
| `auto_toggle_keep_days` | `3` | 已播未入库的集保留几天（PT 出种有延迟）；电影的「发行后继续搜几天」也用它 |
| `auto_toggle_best_version_keep_days` | `90` | 洗版订阅的保留天数（等更好的版本，别按 3 天停） |
| `auto_toggle_best_version_mode` | `after_finale` | 洗版判定时机：`after_finale` 季终后才按洗版判，`always` 播出期也算 |
| `auto_toggle_movie_enabled` | `true` | 是否连电影订阅一起管（按 TMDB 发行日判） |
| `auto_toggle_max_changes` | `0` | 单次最多改多少条（0 = 不限，恢复优先于暂停） |
| `auto_toggle_notify` | `false` | 有实际改动时发通知 |
| `auto_toggle_library_check` | `false` | 用媒体库核对真正入库了多少集（连媒体服务器，有开销） |
| `auto_toggle_library_probe_budget_seconds` | `300` | 每轮核对最多花多少秒（`0` = 只读快照，零请求） |
| `auto_toggle_library_probe_interval` | `1.5` | 每条核对之间等几秒（串行，别把媒体服务器打满） |
| `dedupe_by_history` | `true` | 发现流水记过（订过）的不再自动重订；清空流水即解锁 |
| `blacklist_enabled` | `false` | 排除规则（黑名单）总开关 |
| `blacklist_genre_movie` | `[]` | 排除的电影类型（TMDB genre id，别勾「剧情 18」） |
| `blacklist_genre_tv` | `[]` | 排除的剧集类型（同上） |
| `blacklist_presets` | `[]` | 启用的内置题材预设 key（默认空：不勾就不生效） |
| `blacklist_words` | `""` | 自定义题材词，一行一个（空格 AND / `regex:` / `case:`） |
| `blacklist_match_title` | `true` | 是否匹配片名 / 原名 |
| `blacklist_match_tags` | `true` | 是否匹配来源题材串（豆瓣 category、AniList genres+tags） |
| `blacklist_tmdb_keywords` | `false` | 是否额外查 TMDB 关键词（每条 +1 请求） |

**修改 `cron` 后必须重新保存配置**才会重建定时任务（cron 在注册时读取）。

---

## TMDB 窗口的已知限制（重要）

宿主的 `TmdbChain.tmdb_discover` 对电影拼 `release_date.gte`、对剧集拼
`first_air_date.gte`，**两处都没有上界**，也不暴露 `region` 与 `with_release_type`。

因此本插件：

1. 用 `sort_by` 按日期**升序**排（`primary_release_date.asc` / `first_air_date.asc`）；
2. 把 `release_date` 传今天，把历史条目挡在服务端之外；
3. **在本地按上界过滤**，只保留「今天 ~ 今天 + N 天」内的条目。

**代价**：拿不到「中国大陆院线定档」这种精确地区口径，结果会偏欧美、口径偏宽。
本地窗口过滤只能收紧时间，收不紧地区。这是宿主接口的限制，不是实现缺陷。

---

## 后端 API

路径前缀由宿主补全为 `/api/v1/plugin/SubscribeCenter`，鉴权 `bear`。

| 端点 | 方法 | 用途 |
|---|---|---|
| `/status` | GET | 运行状态、各源情况、今日写入计数、首次运行标记 |
| `/history` | GET | 分页流水，支持 `decision` / `source` / `keyword` 筛选 |
| `/history/clear` | POST | 清空发现流水（同时解锁「流水记过就不再自动重订」） |
| `/history/subscribe` | POST | 从一条流水手动补订阅（`{key}`；绕开窗口/评分/额度/流水去重） |
| `/run_once` | POST | 手动触发一次发现（与定时任务互斥） |
| `/mapping_cache` | GET | 查看身份映射缓存 |
| `/mapping_cache/fix` | POST | 人工修正一条身份映射 |
| `/auto_toggle` | GET | 按播出日算一遍，**只算不写**（自动启停的预览） |
| `/auto_toggle/apply` | POST | 执行自动启停（暂停 / 恢复订阅状态） |
| `/blacklist` | GET | 排除规则元数据（内置题材预设 + TMDB 类型中文名） |
| `/blacklist/test` | POST | 自测一条内容会不会被拦、命中哪条规则（`{title, tags, media_type}`） |

---

## 开发

宿主源码与插件仓需同级（官方推荐布局）：

```text
workspace/
├── MoviePilot/            # 宿主源码 + .venv
└── MoviePilot-Plugins/    # 本仓库
```

```bash
# 用宿主 venv 跑测试（推荐：宿主模块真实可用）
PYTHONPATH=../MoviePilot ../MoviePilot/.venv/bin/python -m pytest tests/v3/subscribecenter

# Windows
set PYTHONPATH=..\MoviePilot && ..\MoviePilot\.venv\Scripts\python.exe -m pytest tests/v3/subscribecenter

# 无宿主时也能跑（conftest 会打最小桩，纯逻辑测试全部有效）
python -m pytest tests/v3/subscribecenter

# 发布门禁
python .github/scripts/check_plugin_versions.py package.v3.json
python .github/scripts/check_federation_css.py     # 有前端产物后才需要
```

目标宿主基线：**MoviePilot v3.1.6**（tag `820b60e0`）。所有宿主契约结论都对该版本源码核验过，
详见 `docs/`（如已随插件仓分发）与插件内各模块的 docstring。

---

## 发版注意

- `plugin_version` 必须是**类级字符串字面量** —— 门禁用 AST 提取它。
- `plugin_version`、`package.v3.json` 的 `version`、`history` 首项三者必须一致。
- `dist/` 属于发布产物**必须提交**（有前端之后）；CI 只跑门禁和打包，**不构建前端**。
- 前端改动发版后需**整页硬刷新（Ctrl+Shift+R）**：`remoteEntry.js` 无哈希、
  宿主加载器不追加缓存参数、SPA 只在页面加载时拉取一次远程组件。
