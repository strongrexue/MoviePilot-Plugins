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

**已实现的数据源只有 TMDB。** 在配置里打开 Bangumi / 豆瓣 / Simkl 不会报错，
但会在日志中明确记录「已启用但当前版本尚未实现，本次跳过」——不会静默无输出。

---

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
