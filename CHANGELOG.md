# 更新日志

本文件按**实施阶段**记录进度、对应版本与里程碑 tag，用于阶段级回退与追溯。

## 版本与 tag 约定

| 层 | 命名 | 谁来维护 | 用途 |
|---|---|---|---|
| 阶段里程碑 tag | `stage-p0` … `stage-p7` | **人工**（本文件登记） | 阶段级回退：`git checkout stage-p4` |
| 发布 tag | `TgMediaCenter_v<版本>` | **CI 自动**（release.yml 会删除重建） | MoviePilot 安装指定版本 |
| 提交 | 常规 commit | 人工 | 阶段内小改动回退：`git revert <sha>` |

> 注意：CI 创建的 `TgMediaCenter_v*` tag 在**重跑发布时会先删除再重建**（可能移动），
> 因此**不要把它当作稳定的回退锚点**，回退请用 `stage-p*` 或具体 commit SHA。

### 版本号策略

- `1.0.0`：骨架（P0）。
- 每完成一个阶段 bump minor：P1 → `1.1.0`，P2 → `1.2.0`，…，P7 → `1.7.0`。
- bump 版本时三处必须同步：插件类 `plugin_version`、`package.v3.json` 的 `version` 与
  `history` 中最新版本的键（`check_plugin_versions.py` 会校验）。

### 回退操作示例

```bash
# 查看某阶段内容
git checkout stage-p3

# 从某个文件/目录恢复到某阶段状态
git checkout stage-p3 -- plugins.v3/tgmediacenter/src

# 撤销某次提交（保留历史，安全）
git revert <sha>

# 某阶段整体作废、退回该阶段之前
git revert --no-commit stage-p3..stage-p4 && git commit
```

---

## 阶段进度

| 阶段 | 内容 | 版本 | tag | 状态 |
|---|---|---|---|---|
| P0 | 插件骨架：仓库结构、元数据、Vue 联邦构建链、API 层与请求归属、显示名与图标 | `1.0.0` | `stage-p0` | ✅ 已完成（MP 加载验证通过） |
| P1 | TG 核心凭证：Telethon 接入、登录向导、StringSession 持久化、对话列表缓存 | `1.1.0` | `stage-p1` | ✅ 已完成 |
| P2 | 115 网盘：Cookie 登录、状态配额、分享转存、离线下载、推送队列 | `1.2.0` | `stage-p2` | ⏳ 待开始 |
| P3 | 自定义豆瓣源：RssHelper 拉取、规则过滤、宿主订阅创建、去重表 | `1.3.0` | `stage-p3` | ⏳ 待开始 |
| P4 | TG 资源监控：事件接入、聚合净化、MetaVideo 识别、缺集匹配、推送决策 | `1.4.0` | `stage-p4` | ⏳ 待开始 |
| P5 | 历史消息缓存：建表、增量 / 范围同步、检索、统计 | `1.5.0` | `stage-p5` | ⏳ 待开始 |
| P6 | TG 通用转发：两级匹配规则、内容转换、置顶、转发冷却 | `1.6.0` | `stage-p6` | ⏳ 待开始 |
| P7 | 打磨：限流退避、通知接入、测试、真实加载验证、README | `1.7.0` | `stage-p7` | ⏳ 待开始 |

---

## v1.1.1（P1 修复）

真机验证发现的两个缺陷修复：

- **前端**：`ConfigTgPane.vue` 未声明 `code` / `password` 两个响应式变量，
  点击「登录」时抛 `ReferenceError: code is not defined`，导致验证码已收到却登录不上。
- **后端**：`TelegramRuntime.telethon_available` 以 `@property` 暴露，在**类上**访问得到的是
  property 对象而非布尔值，塞进响应模型后 `/status` 校验失败（表现为四个状态徽章全部显示否定态，
  误报"telethon 未安装"）。改为静态方法，并新增回归测试。

顺带加固：

- `status()` 逐项兜底，任何子项查询失败不再让整个状态接口失败。
- 未保存凭证时，前端给出可操作提示（"请先点击保存配置"），而不是让人猜。
- 登录成功后自动拉取对话列表。

## v1.1.0（P1 TG 核心凭证）

新增能力：

- **TG 运行时**（`core/runtime.py`）：独立守护线程跑专属 asyncio 事件循环，同步侧经
  `run_coroutine_threadsafe` 投递协程；客户端在 loop 内创建与连接；`start()` / `stop()`
  幂等且线程安全；telethon 缺失或凭证不全时降级，不打断插件加载。
- **登录向导**：`发送验证码 → 提交验证码 → （如需）两步验证密码` 三步流程，覆盖
  验证码错误 / 过期、密码错误、手机号无效等可预期失败（HTTP 400 + 友好提示）。
- **会话持久化**：成功后导出 StringSession 存入插件配置；`status` 接口只返回是否已保存，
  **不回显会话内容**。
- **对话列表缓存**：`iter_dialogs` 拉取群组 / 频道 / 用户并归一，存入插件结构化数据；
  供后续监控与转发规则的频道下拉使用。
- **代理继承**：读取宿主 `settings.PROXY`（http / socks5，含用户名密码）转成 Telethon
  参数，插件不设独立代理配置。
- **保活**：周期性探活，掉线自动重连。
- **前端**：配置页新增「TG 凭证」面板（状态徽章、账号信息、API 凭证表单、登录向导、
  对话列表刷新）。

验收：

- 两道官方面禁通过；`vite build` 成功（63 模块）；`compileall` 语法检查通过。
- 纯逻辑自检（代理解析 / 掩码 / 对话归一）全部通过。
- 待真实加载验证：登录向导端到端、对话列表刷新。

## v1.0.0（P0 骨架）

- 建立符合官方 MoviePilot-Plugins 规范的独立仓库结构。
- 插件主类 `TgMediaCenter`：生命周期、Vue 联邦渲染声明、默认配置、API / 模型钩子。
- 前端构建链：Vite 5 + `@originjs/vite-plugin-federation`，含 PostCSS 全局样式过滤与
  `closeBundle` 产物清理，暴露 `./Config`、`./Page`、`./Dashboard` 三个入口。
- 复用豆瓣中心验证过的 `api.js`（pluginPath + envelope 容错 + 超时）与
  `useRequestScope`（请求归属管理）。
- 引入官方版本门禁、联邦 CSS 门禁与 Release 工作流；`.gitattributes` 统一 LF。
- 验收：两道官方面禁通过、`vite build` 成功、MP 加载验证通过。
