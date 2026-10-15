/**
 * 前端构建版本。
 *
 * 用途：与后端 `/status` 返回的 `plugin_version` 比对。
 * 联邦组件的入口文件名固定（`remoteEntry.js`，无哈希）、加载器也不加缓存参数，
 * 因此「插件已更新但浏览器仍用旧组件」是常态。界面上一旦发现两边版本不一致，
 * 就直接提示用户硬刷新，避免对着旧界面排查新问题。
 *
 * ⚠️ 发版时必须与本插件 `plugin_version` 同步（有单测校验，见 tests/v3/embycovercenter）。
 */
export const FRONTEND_VERSION = '1.4.1'
