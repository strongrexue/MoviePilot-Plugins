# MoviePilot-Plugins（个人插件仓库）

独立维护的 MoviePilot V3 插件仓库，目录结构与官方 `MoviePilot-Plugins` 保持一致，
可直接作为「自定义插件仓库」添加到 MoviePilot。

## 插件列表

| 插件 ID | 名称 | 版本 | 说明 |
|---|---|---|---|
| `TgMediaCenter` | TG媒体中心 | 1.0.0 | Telegram 资源监控 / 历史消息缓存 / 115 网盘 / 自定义豆瓣源 / TG 通用转发 |

对应的插件源码位于 `plugins.v3/<插件ID小写>/`，测试位于 `tests/v3/<插件ID小写>/`，
索引元数据写入 `package.v3.json`。

## 安装

在 MoviePilot 中把本仓库地址添加为自定义插件仓库，然后在插件市场中安装
`TG媒体中心`。索引条目已声明 `release: true`，安装时使用本仓库 GitHub Release
中的压缩包。

## 目录结构

```text
MoviePilot-Plugins/
├── plugins.v3/tgmediacenter/     # 插件源码（Vue 联邦前端产物在 dist/assets/）
├── tests/v3/tgmediacenter/       # 插件测试
├── package.v3.json               # V3 插件索引
├── icons/                        # 插件图标
└── .github/                      # 发布工作流与门禁脚本
```

## 开发约定

- 目录名必须是插件类名的小写形式；主类必须定义在该目录的 `__init__.py`。
- 三处版本必须一致：插件类 `plugin_version`、`package.v3.json` 的 `version`、
  `history` 中最新版本的键。
- 前端为 Vue 联邦远程组件，构建产物 `dist/assets/` 随源码提交；本地开发用
  `pnpm install && pnpm dev`（监听构建）。
- 提交前运行门禁：

```bash
python .github/scripts/check_plugin_versions.py package.v3.json
python .github/scripts/check_federation_css.py
```

## 发布

`package.v3.json` 变更推送到 `main` 分支后，`.github/workflows/release.yml`
会自动打包并创建 Release，Tag 格式 `TgMediaCenter_v<版本>`，产物
`tgmediacenter_v<版本>.zip`。

## 设计文档

工程结构设计与决策记录见仓库外部文档《TG媒体中心-工程结构设计.md》。
