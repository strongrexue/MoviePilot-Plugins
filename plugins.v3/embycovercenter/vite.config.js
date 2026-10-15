import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'
import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * 联邦产物清理：删除 index.html 与主程序共享样式，避免污染宿主页面。
 * 同时压缩 remoteEntry.js 的行尾空白，保证构建产物稳定可比对。
 */
function cleanFederationArtifacts() {
  let outputDir
  return {
    name: 'clean-federation-artifacts',
    configResolved(config) {
      outputDir = resolve(config.root, config.build.outDir)
    },
    closeBundle() {
      if (!outputDir) return
      rmSync(resolve(outputDir, 'index.html'), { force: true })
      rmSync(resolve(outputDir, 'assets/__federation_shared_vuetify'), {
        recursive: true,
        force: true,
      })
      const remoteEntryPath = resolve(outputDir, 'assets/remoteEntry.js')
      if (existsSync(remoteEntryPath)) {
        const remoteEntry = readFileSync(remoteEntryPath, 'utf8').replace(/[ \t]+(?=\r?$)/gm, '')
        writeFileSync(remoteEntryPath, remoteEntry, 'utf8')
      }
    },
  }
}

export default defineConfig({
  plugins: [
    vue(),
    federation({
      name: 'EmbyCoverCenter',
      filename: 'remoteEntry.js',
      exposes: {
        './Config': './src/components/Config.vue',
        './Page': './src/components/Page.vue',
        './Dashboard': './src/components/Dashboard.vue',
        // MP 左侧「发现」分区整页入口的承载组件（由 get_sidebar_nav 注册）
        './AppPage': './src/components/AppPage.vue',
      },
      shared: {
        vue: { requiredVersion: false, generate: false, singleton: true },
        vuetify: { requiredVersion: false, generate: false, singleton: true },
        'vuetify/styles': { requiredVersion: false, generate: false, singleton: true },
      },
      format: 'esm',
    }),
    cleanFederationArtifacts(),
  ],
  build: {
    target: 'esnext',
    // 不压缩：产物体积依然很小（gzip 后十几 KB），换来的是浏览器里可直接读源码，
    // 排查"插件更新了但界面还是旧的"这类问题时要按字符串核对产物，压缩后无法核对。
    minify: false,
    cssCodeSplit: true,
    emptyOutDir: false,
  },
  css: {
    postcss: {
      plugins: [
        {
          postcssPlugin: 'internal:charset-removal',
          AtRule: {
            charset: atRule => {
              if (atRule.name === 'charset') atRule.remove()
            },
          },
        },
        {
          // 联邦插件不得把 Vuetify / MDI 的全局样式打进产物。
          // ⚠️ 过滤必须限定在 node_modules 的 vuetify/@mdi 源文件内：
          //    无差别删除含 .v-/.mdi- 选择器的规则，会连带吃掉插件代码里
          //    针对 Vuetify 组件内部的合法样式（v1.4.2~v1.4.5 封面分组卡片
          //    样式从未生效的根因）。
          postcssPlugin: 'vuetify-filter',
          Root(root) {
            const sourcePath = root.source?.input?.file?.replaceAll('\\', '/') || ''
            if (sourcePath.includes('/node_modules/vuetify/') ||
                sourcePath.includes('/node_modules/@mdi/')) {
              root.nodes = []
              return
            }
            if (sourcePath.includes('/node_modules/')) {
              root.walkRules(rule => {
                if (rule.selector &&
                    (rule.selector.includes('.v-') || rule.selector.includes('.mdi-'))) {
                  rule.remove()
                }
              })
            }
          },
        },
      ],
    },
  },
})
