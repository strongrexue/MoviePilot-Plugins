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
| **Bangumi** | ✅ 已实现 | 当季番剧；条目自带 subject id，经宿主换算成 TMDB |
| 豆瓣 RSS | ⬜ 未实现 | 需要自建 RSSHub 实例 |
| Simkl | ⬜ 未实现 | 需要 Simkl client_id |
| JustWatch | ⬜ 未实现 | 可选，只记日志 |

### Bangumi 源的两个实机结论

1. **只有 https://api.bgm.tv 可用** —— pi.bangumi.tv 与 gm.tv 实测均失败。
2. **/v0/subjects?air_date=... 的过滤被服务端忽略**（实测传「>=今天」仍返回全库
   29601 条、从 2029 年倒序），所以只能用 /calendar（当季番列表 + 本地按
   ir_date 过滤）。局限：只覆盖当季，季末切档前后可能漏下季刚定档的番。
3. **条目不带 popularity**，因此不参与「最低关注度」门槛 —— 这是有意的：
   当季番列表本身是策展的，用 TMDB 的关注度量纲去卡它没有意义。

**已实现的数据源只有 TMDB。** 在配置里打开 Bangumi / 豆瓣 / Simkl 不会报错，
但会在日志中明确记录「已启用但当前版本尚未实现，本次跳过」——不会静默无输出。

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

## 配置项

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `enabled` | `false` | 插件总开关 |
| `enable_tmdb` | `true` | 启用 TMDB |
| `enable_bangumi` | `false` | 启用 Bangumi（0.1.0 未实现） |
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
| `/run_once` | POST | 手动触发一次发现（与定时任务互斥） |
| `/mapping_cache` | GET | 查看身份映射缓存 |
| `/mapping_cache/fix` | POST | 人工修正一条身份映射 |

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
