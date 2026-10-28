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
- **13 套封面风格（布局）**：扇形展开 / 斜线分割 / 旋转 / 旋转堆叠 / 极简 /
  海报墙 / 经典堆叠 / 经典平铺 / 经典平铺(动态) / 聚焦C佬 / 荣耀视界（以上来自 ChillPoster）/
  暗场右文 / 分类横幅（自研），配套素材随包分发；
  每个布局导出 `get_schema()`（分组 + 字段：range 滑块 / select / color / font / boolean / text / file）
  与 `render()`，配置页参数表单**完全按 schema 自动生成**，新增布局无需改前端。
- **暗场右文**：不需要自备底图——直接用媒体库自己的背景图（没有则用首张海报）当场景，
  左侧保持清晰、向右渐变为压暗的失焦暗场，文字压在暗侧。参考图的「人物被场景光打亮」
  那种一体感运行时贴图做不出来，这个布局复刻的是它的**构图语法**：左亮右暗、主视觉占左 6 成、
  右侧文字带、标题落在画面 38% 高度。素材本身左暗右亮时会自动水平镜像（`auto_mirror`）。
- **分类横幅**：参考图的「分区可调」版式——金属渐变主标题 + 标题下光带（亮斑位置可调）+
  副标题 + 中英标语 + 左下题材标签 + 右侧竖排出血书法水印 + 圆角双层描边，每个元素独立定位。
  圆角与描边默认就是**最高档**（半径 80 / 粗细 8，`frame_radius` / `frame_border_width`）。
  标题下的光带是一条**连续的双高斯光带**（中心发白、向外平滑衰减，横向半宽按参考图逐档拟合：
  `>90%` 1.2% 宽 / `>50%` 3.2% 宽），不是等亮的横杠；中心亮度/颜色、灯带高度、亮斑位置都可调。
  默认水印锚点在 85%（右侧竖排、可再往外调出血）。
  **主标题 / 副标题 / 标语 / 题材标签各自带开关**（`title_enabled` / `subtitle_enabled` /
  `slogan_enabled` / `tags_enabled`，默认全开），和「灯带」「水印」一样可以单独关掉某一块，
  不用整段删字段。「英文名」分组自 1.6.27 起正名为「副标题」。
  两种底图来源（`bg_source`）：`keyart`（上传的分类主视觉，可**按媒体库**分别指定）、
  `library`（媒体库自身背景图）。底图完全可选：不传主视觉、库也没有背景图时用首张海报兜底，
  **不要求用户自备母版图**。`auto_mirror`（文案「素材镜像」）对两种来源都生效：
  **开启就水平翻转、关闭就用原图**（不判断画面哪边更亮），默认关闭。
  **不做统一调色**：没有色相偏移、溢光、暗角、颗粒那套「调色与质感」组件（1.6.26 起整组下线），
  底图什么样就什么样；只保留「底图调整」分组的 `scene_brightness` / `scene_contrast` /
  `scene_saturation` 三个开关，默认都是 1.0（= 完全不动），需要时再往上调。
  压暗改由「特效与装饰」分组的通用渐变遮罩提供（`mask_enabled` / `mask_color` /
  `mask_opacity` / `mask_coverage` / `mask_direction`，遮罩颜色默认黑色，支持水平左黑右亮、
  水平右黑左亮、垂直下黑上亮、垂直上黑下亮四个方向），与「极简」布局共用同一套
  `create_smart_mask()`；**遮罩默认开启**（浓度 180、范围 66%），底部遮罩单独可调
  （`bottom_scrim_color` / `bottom_scrim_strength`，即「底部遮罩颜色 / 底部遮罩浓度」），
  默认 **0 = 不压**。
  底图**不做锐化**（1.6.27 起去掉底图智能锐化），需要更清晰请直接上更高分辨率的成品图。
  **内置 16 个分类库的整套文案**（1.6.32 起）：儿童 / 国漫 / 国产剧 / 港台剧 / 日韩剧 /
  欧美剧 / 日番 / 欧美漫 / 综艺 / 纪录片 / 动画电影 / 华语电影 / 日韩电影 / 外语电影 /
  纪录影片 / 演唱会，每个库都带英文名、中文标语、英文标语、题材标签，其中 7 个还带
  **竖排书法水印**与**右下角引文**。字典在 `service/library_names.py` 的 `LIBRARY_COPY`
  （前端 `useCoverDesigner.js` 有一份同样的库名副本，改的时候两边一起改）。
  标语字段**留空就自动用本库的内置文案**，预设模板因此不用为每个库各存一份；
  副标题同理走「手填 → 该库英文名 → 库名」。
  题材标签四级来源（`tags_source`）：**默认 `builtin`（内置分类文案）**，其次 `auto`
  （Emby `Genres`）、`manual`（手填 `tags_text`）、`library`（按库映射 `tags_per_library`）；
  高优先级为空时逐级回退，所以手填内容随时可以盖掉自动结果。
  **「书法水印」与「右下角引文」是两个独立开关、默认都关**（`watermark_enabled` /
  `quote_enabled`）：水印锚点默认 85%（右侧竖排、可再往外调出血），引文落在右下角
  （`quote_x` / `quote_y` 默认 95 / 92，正文字号 `quote_size` 22、出处跟在正文后面）。
  主视觉通过配置页「主视觉文件」字段直接上传（`/keyart/upload`）或删除（`/keyart/delete`），
  落在数据目录 `keyart/`。
  **1.6.23 铺开的 6 套「分类横幅 · xx」预设已收成一套「分类横幅」**：升级时按内容指纹自动
  回收没改过的旧预设（改过参数或改过名的原样保留）。
- **分辨率与画质不压缩**：`canvas_preset` 默认 `auto`，**只有真的拿主视觉当底图的布局**
  （分类横幅且 `bg_source=keyart`）才按**主视觉原图尺寸**出图（3840×2160 的成品就出 3840×2160），
  其余预设一律 1920×1080；也可强制 1080p / 1440p / 2160p 或自定义（单边上限 4096，奇数边自动取偶）。
  主视觉**比 1080p 还小**时，`auto` 会按比例把画布托到 1920×1080 起步（1.6.28 起）：否则画布跟着
  小原图走，Emby 把封面铺满时必然放大数倍，表现就是「自己上传的底图应用后糊、媒体库背景图不糊」。
  1.6.30 起再加一道闸：配置里残留的 `keyart_file`（在分类横幅上传过、之后切到别的预设）不再影响
  画布 —— 那些布局用的是 Emby 下发的海报（最高 1000px），画布被撑到 4K 就等于放大三四倍，
  这也是「换个预设应用后也糊」的原因。取图侧 `BACKDROP_MAX_HEIGHT` 提到 2160、
  质量 95，避免服务器先把素材压小；输出 JPEG 默认 `output_quality=95` 且关闭色度抽样，
  只有显式调低才降质。
- **预览与自动封面共用一套文字**：库名取 `Users/{uid}/Views`，副标题按
  「按库手填英文名 → 内置词典 → 库名」回退；预览与自动封面都走同一个
  `cover_auto._subtitle_for()`，所以手动预览也能看到副标题。
- **随机抽取是真随机**：`mode=random` 时**不走素材短缓存**（缓存 key 不含随机因子，
  命中就等于把上一次的素材原样还回去），且素材数量不足以抽样时也会 `random.shuffle`
  打散顺序（小库不会永远取第一张）；`mode=latest` 仍保留 120s 短缓存，因为它是确定性的。
- **预览与应用是同一张图**：点「渲染并应用」时若当前预览图就是同一套参数渲出来的，
  前端直接把预览图当 `image_data` 上传，不再让后端重渲一次（1.6.32 起）。
  否则在「随机抽取」模式下后端会重新抽素材，应用上去的图与预览必然不是同一张；
  `mode=latest` 不受影响。想刻意换图就再点一次「生成预览」。
- **默认模板带预览缩略图**：12 个内置模板预设（`.json`）+ 对应 `.jpg` 缩略图随包分发，
  首次初始化拷入数据目录。**升级时内置预设会原地更新**（`upgrade_shipped_templates()`）：
  数据目录里的 `.json` 指纹命中某个历史发行版、或已是最新版但缩略图与随包版本字节不一致，
  就整体覆盖成随包版本（老装机「预设缩略图没变」就是这个原因）；用户改过配置或改过名的跳过。
  「暗场右文」预设自 1.6.26 起下线（布局模块保留，需要时可自建模板继续用），
  升级时按内容指纹自动回收没改过的旧预设。
- **设计素材端点放行匿名读取**：`/asset/font/{name}` 与 `/asset/template/{filename}` 用于浏览器
  `<img>` 直接加载（无法携带 Authorization 头）；二者只是设计素材，不含敏感信息。
- **备份版本可视化**：备份管理里每个版本显示封面缩略图（`/cover_backup/thumb` 生成 120 高
  JPEG data URI），恢复确认弹窗同步展示待恢复封面。

## 界面

Vue 联邦远程组件，暴露 `./Config`、`./Page`、`./Dashboard`、`./AppPage` 四个入口；
`AppPage` 为「发现」分区整页入口，由后端 `get_sidebar_nav()` **跟随「启用」开关**决定
（启用即注册、停用即移除，没有独立的发现页开关）。

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
