# 胖虎封面中心

MoviePilot V3 插件（`EmbyCoverCenter`），面向 Emby / Jellyfin，提供：

1. **媒体库封面生成**：读取媒体库素材（背景图 / 海报），用模板 + 字体 + 布局合成封面，
   生成后可应用到媒体库封面，也支持直接上传本地成品图替换。
2. **封面备份 / 恢复**：把现有媒体库封面批量导出为备份套件，可整体或按库恢复。
3. **自动封面任务**：定时任务 + Emby 入库 webhook（复用宿主 `EventType.WebhookMessage`）
   触发对应媒体库封面刷新。
4. **Emby 任务中心**：查看 / 管理 Emby 服务端计划任务，编辑触发器、立即运行、停止。
5. **通知**：统一走 MoviePilot 通知渠道（`post_message`），不自建通知通道。

## 实现要点

- **媒体服务器访问复用宿主模块透传**：`MediaServerHelper().get_services()` 取得模块实例后，
  用 `get_data(url)` / `post_data(url, data, headers)` 读写（URL 内的 `[HOST]` / `[APIKEY]`
  由宿主模块替换），不维护独立凭据、不复制宿主模块实例。封面写入固定使用 base64 body。
- **宿主透传不提供 DELETE**：任务中心的「停止任务」用 `RequestUtils.delete_res` 补齐；
  服务器地址与密钥仍取自宿主 `MediaServerHelper.get_configs()`，不另存凭据。
- **路径前缀按类型区分**：Emby 用 `emby/…`，Jellyfin 用根路径（宿主模块同款约定）。
- **不声明额外依赖（无 `pyproject.toml`）**：只使用宿主环境自带的 `Pillow`；这样在**离线/无外网**
  的 MoviePilot 主机上更新插件时不会被"安装依赖"环节卡住（若声明依赖，MP 会尝试联网安装，
  失败会清理插件目录导致更新失败）。荣耀视界的透视变换已用纯 Python 高斯消元实现，不依赖 numpy。
- **渲染在宿主同进程**：布局脚本按需加载（不在模块导入期执行），避免导入副作用与分身污染；
  引擎缓存挂在实例上，不放进进程级单例。
- **字体不随插件分发**：中文字体请自行上传（配置页「封面设计 → 字体」），未上传时回退到
  PIL 默认字体（中文会显示为方块）。这样可避免把有版权的字体打进发布包。
- **11 套封面风格（布局）来自 ChillPoster**：扇形展开 / 斜线分割 / 旋转 / 旋转堆叠 / 极简 /
  海报墙 / 经典堆叠 / 经典平铺 / 经典平铺(动态) / 聚焦C佬 / 荣耀视界，配套素材随包分发；
  每个布局导出 `get_schema()`（分组 + 字段：range 滑块 / select / color / font / boolean / text）
  与 `render()`，配置页参数表单**完全按 schema 自动生成**，新增布局无需改前端。
- **默认模板带预览缩略图**：11 个内置模板预设（`.json`）+ 对应 `.jpg` 缩略图随包分发，
  首次初始化只补缺失地拷入数据目录。
- **设计素材端点放行匿名读取**：`/asset/font/{name}` 与 `/asset/template/{filename}` 用于浏览器
  `<img>` 直接加载（无法携带 Authorization 头）；二者只是设计素材，不含敏感信息。
- **备份版本可视化**：备份管理里每个版本显示封面缩略图（`/cover_backup/thumb` 生成 120 高
  JPEG data URI），恢复确认弹窗同步展示待恢复封面。

## 界面

Vue 联邦远程组件，暴露 `./Config`、`./Page`、`./Dashboard`、`./AppPage` 四个入口；
`AppPage` 为「发现」分区整页入口，由后端 `get_sidebar_nav()` 按配置项
`discovery_page_enabled` 决定是否注册。

## 开发与发版

### 版本号四处同步

每次发版，下面四处必须同时改为同一版本号，否则 CI 门禁会失败、单测也会爆：

1. `__init__.py` 的 `plugin_version`（**必须是类级字符串字面量**，门禁用 AST 提取）；
2. `package.v3.json` 的 `version` 字段；
3. `package.v3.json` 的 `history` 最新键（如 `"v1.0.0": "..."`，置顶且语义版本降序）；
4. `src/components/version.js` 的 `FRONTEND_VERSION`。

门禁脚本 `.github/scripts/check_plugin_versions.py` 会校验目录、版本一致性与 `history` 顺序；
单测 `tests/v3/embycovercenter/test_plugin.py` 也会断言这几处相等。

### 前端改动必须重建 dist

前端是 Vue 联邦远程组件，`vite` 配置 `emptyOutDir: false`，所以 `npm run build`
**先 clean 清理 `dist/assets` 旧产物**再产出新联邦产物。不清理会堆积带旧哈希的产物，
最终被打进发布包、前端永不更新。

```bash
pnpm install
pnpm dev      # vite build --watch，配合宿主 PLUGIN_LOCAL_REPO_PATHS + PLUGIN_AUTO_RELOAD 联调
pnpm build    # 先 clean 再产出联邦产物
```

构建后必须通过联邦 CSS 门禁（作用域样式泄露校验）：

```bash
python ../../../.github/scripts/check_federation_css.py
```

### 发布流程与 CI 行为

`.github/workflows/release.yml`（"Plugin Release"）在 **push 到 `main` 且改动
`package.v3.json`**（或 `package.json` / `package.v2.json`）时触发，也可手动
`workflow_dispatch`。流程：

1. 先跑两个门禁：`check_plugin_versions.py` + `check_federation_css.py`；
2. 只处理各 package 文件里 `release == true` 的条目，按其 `version` 打包
   `embycovercenter_v<版本>.zip`（zip 的是插件目录，排除 `__pycache__`）；
3. 建 / 更新 tag `<插件ID>_v<版本>`（如 `EmbyCoverCenter_v1.0.0`）与同名 Release，
   发布说明取自 `history["v<版本>"]`。

- **触发条件是 `package*.json` 有改动**：只推源码 / README 而不动 `package.v3.json` 时
  **不会出包**——发版必须改版本号（或手动 dispatch）。
- **同版本重跑会替换**：Release 已存在时先删旧 Release 与 tag 再重建（幂等，可安全重发）。
- **插件目录自上次 tag 起无改动则跳过打包**，只更新发布说明。
- 图标两份都要更新：索引仓库 `icons/embycovercenter.png`（列表用）+ 插件目录内
  `plugins.v3/embycovercenter/embycovercenter.png`（随包发布）。

### 图标必须写完整 URL

`package.v3.json` 的 `icon` 与 `__init__.py` 的 `plugin_icon` **都写完整 https URL**
（`https://raw.githubusercontent.com/strongrexue/MoviePilot-Plugins/main/icons/embycovercenter.png`）。

根因：宿主前端 `PluginCard.vue` 加载图标时，若值不是 http 开头则请求本地
`./plugin_icon/<文件名>`，该路径在多数自建部署下 404；只有完整 URL 走图片代理才稳定。
且 nginx 对图片给 `expires 1y; immutable`，**换图不换 URL 基本无效**。

### 前端更新后必须硬刷新

联邦入口固定叫 `remoteEntry.js`（无哈希），宿主加载器也不追加缓存参数，SPA 只在
**页面加载时**拉取一次远程组件。因此更新带前端改动的版本后，必须整页硬刷新
（`Ctrl + Shift + R`）。

排查"插件是否真的更新"先查容器内落盘文件：

```bash
docker exec <容器名> sh -c \
  "grep -o 'plugin_version = \"[^\"]*\"' /app/app/plugins/embycovercenter/__init__.py; \
   grep -o \"FRONTEND_VERSION = '[^']*'\" /app/app/plugins/embycovercenter/src/components/version.js"
```

两处应与你安装的版本一致；若本就是旧版本，说明**插件根本没更新**（与浏览器缓存无关）。

## 进度

- **M1 骨架**（`1.0.0`）：仓库结构、市场元数据、联邦构建链（四个入口）、插件 API 注册
  （`/ping`、`/status`）、媒体服务器发现、配置读写。
- **M2 Emby 任务中心**（`1.1.0`）：任务列表（分类分组 / 运行中置顶 / 隐藏与禁用任务兜底）、
  触发器编辑（每天 / 每周 / 按间隔 / 服务器启动时）、立即运行、停止；详情页新增任务面板。
- **M3 封面渲染引擎**（`1.2.0`）：`PosterEngine`（布局按需加载、静态 JPEG + 动态 APNG、数量角标）、
  内置布局与 schema 驱动表单、媒体库与素材读取、字体 / 模板资源管理与模板预览缩略图、
  `/preview` 与 `/apply`（生成后应用 / 直接上传成品图两条来源）、原生资源端点。
- **M3 扩充**（`1.3.0`）：完整搬入 ChillPoster 的 **11 套封面风格**与配套素材（扇形展开 /
  斜线分割 / 旋转 / 旋转堆叠 / 极简 / 海报墙 / 经典堆叠 / 经典平铺 / 经典平铺(动态) /
  聚焦C佬 / 荣耀视界）；schema 改为「分组 + 滑块」；配置页改版为「基础设置 / 封面设计」
  两个分区（左调参、右固定预览），修复下拉框 `[object Object]`。
- **M4+**：自动封面任务与 webhook 触发、备份恢复、通知接入。详见设计文档。
