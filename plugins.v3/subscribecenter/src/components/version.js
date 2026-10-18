/**
 * 前端组件版本号。
 *
 * ⚠️ 必须与后端 `SubscribeCenter.plugin_version` 一致。
 *
 * 为什么单独放一个文件：`remoteEntry.js` 文件名固定无哈希，宿主加载器也不追加缓存参数，
 * 浏览器只在页面加载时拉取一次远程组件。因此"插件更新了但界面还是旧的"是常态，
 * 唯一能确认当前浏览器到底加载了哪一版的办法，就是在组件里把这个号显示出来、
 * 并与后端 `/status` 返回的 plugin_version 比对；不一致就提示硬刷新。
 */
export const FRONTEND_VERSION = '1.8.0'
