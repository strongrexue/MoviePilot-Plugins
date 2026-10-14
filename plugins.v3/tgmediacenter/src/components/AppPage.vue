<script setup>
import { ref } from 'vue'
import Config from './Config.vue'
import Page from './Page.vue'
import { getPluginConfig, savePluginConfig } from './api'

/**
 * MP 左侧「发现」分区的整页入口（1.8.0）。
 *
 * 页面内容就是本插件的「运行详情 / 仪表盘」——直接复用 Page.vue，不另做一套
 * 页面；整页场景没有"关闭"语义，所以工具栏的「设置」按钮改为在这里弹出配置
 * 弹窗（与插件详情页同一份 Config.vue）。显示与否由后端 ``get_sidebar_nav()``
 * 依据配置项 ``discovery_page_enabled``（配置页顶部「发现页」开关）决定。
 *
 * 纪律（与项目其它页面一致）：
 * - 模板/脚本用到的变量全部在 script setup 声明 ref；
 * - 重入保护只留在按钮处理器，内部 fetch 无保护；
 * - 保存后重挂 Page（key 变化）重新拉一次运行详情，不本地推测状态。
 */
const props = defineProps({
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'TgMediaCenter' },
})

const settingsDialog = ref(false)
const loadingSettings = ref(false)
const savingSettings = ref(false)
const settingsConfig = ref({})
const pageKey = ref(0)
const snackbar = ref({ show: false, message: '', color: 'success' })

async function openSettings() {
  if (loadingSettings.value) return
  loadingSettings.value = true
  try {
    settingsConfig.value = await getPluginConfig(props.api, props.pluginId)
    settingsDialog.value = true
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '设置加载失败', color: 'error' }
  } finally {
    loadingSettings.value = false
  }
}

async function saveSettings(config) {
  if (savingSettings.value) return
  savingSettings.value = true
  try {
    await savePluginConfig(props.api, props.pluginId, config)
    settingsConfig.value = { ...(config || {}) }
    settingsDialog.value = false
    pageKey.value += 1
    snackbar.value = { show: true, message: '设置已保存', color: 'success' }
  } catch (error) {
    snackbar.value = { show: true, message: error?.message || '设置保存失败', color: 'error' }
  } finally {
    savingSettings.value = false
  }
}
</script>

<template>
  <main class="tg-app-page">
    <Page
      :key="`${props.pluginId}-${props.navKey}-${pageKey}`"
      :api="props.api"
      :plugin-id="props.pluginId"
      app-page
      @switch="openSettings"
    />

    <VDialog v-model="settingsDialog" max-width="1160" :persistent="savingSettings || loadingSettings">
      <VProgressLinear v-if="loadingSettings" indeterminate color="primary" />
      <Config
        v-if="!loadingSettings"
        :api="props.api"
        :plugin-id="props.pluginId"
        :initial-config="settingsConfig"
        @save="saveSettings"
        @close="settingsDialog = false"
      />
    </VDialog>

    <VSnackbar v-model="snackbar.show" :color="snackbar.color" timeout="5000">
      {{ snackbar.message }}
    </VSnackbar>
  </main>
</template>

<style scoped>
.tg-app-page { width: 100%; min-width: 0; max-width: 1800px; margin: 0 auto; padding: 16px; background: transparent; }
@media (max-width: 600px) { .tg-app-page { padding: 8px; } }
</style>
