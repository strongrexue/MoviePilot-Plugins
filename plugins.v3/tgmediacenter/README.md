# TG媒体中心

MoviePilot V3 插件，聚合六项能力：

1. **TG 核心凭证**：Telethon 个人账号登录（StringSession）、对话列表缓存、转发冷却与保活。
2. **115 网盘**：Cookie 登录、空间配额、分享链接转存、磁力 / eD2k 离线下载（自实现 Web 接口，无额外依赖）。
3. **自定义豆瓣源**：想看 RSS 与自定义榜单 / 片单 RSS 订阅，走宿主 RSS 解析与订阅链。
4. **TG 资源监控**：实时监听 TG 频道，消息净化后由宿主识别引擎解析，仅推送缺失集。
5. **历史消息缓存**：回抓频道历史消息建本地索引，供订阅补全检索。
6. **TG 通用转发**：两级匹配规则（关键词 / 触发器）与内容转换后转发。

## 依赖与复用

- 额外依赖仅 `telethon`；RSS、识别、媒体库查询、通知、代理均复用宿主能力。
- 自有数据表通过 `plugin_declarative_base()` + `get_database_models()` 由宿主建表。

## 界面

Vue 联邦远程组件，暴露 `./Config`、`./Page`、`./Dashboard` 三个入口。

## 本地开发

```bash
pnpm install
pnpm dev      # vite build --watch，配合宿主 PLUGIN_LOCAL_REPO_PATHS + PLUGIN_AUTO_RELOAD 联调
pnpm build    # 先清理 dist/assets 旧产物，再产出新的联邦产物
```

`build` 会先执行 `clean`：因为 `emptyOutDir` 为 false，不清理会堆积旧哈希产物，
最终被打进发布包。

构建后必须通过联邦 CSS 门禁：

```bash
python ../../../.github/scripts/check_federation_css.py
```

## 进度

- **P0 骨架**（`1.0.0`）：仓库结构、元数据、联邦构建链、API 层与请求归属。
- **P1 TG 核心凭证**（`1.1.0`）：Telethon 运行时（独立线程事件循环）、登录向导与两步验证、
  StringSession 持久化、对话列表缓存、代理继承宿主设置。
  - 配置页「TG 凭证」面板：状态徽章 → API 凭证 → 登录向导 → 刷新对话列表。
  - 接口：`/status`、`/telegram/send_code`、`/telegram/sign_in`、`/telegram/logout`、
    `/telegram/dialogs`、`/telegram/refresh_dialogs`。
- 待实现：115 网盘（P2）、自定义豆瓣源（P3）、TG 资源监控（P4）、历史消息缓存（P5）、
  TG 通用转发（P6）、打磨（P7）。

## 版本

当前 `1.1.1`。版本号需与 `package.v3.json` 的 `version` 及 `history` 最新键保持一致。
