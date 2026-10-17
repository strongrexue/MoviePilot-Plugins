<script setup>
/**
 * 「发现」分区侧栏整页入口的承载组件。
 *
 * 整页模式下没有"关闭"语义：直接复用 Page 并置 appPage=true 隐藏关闭按钮；
 * 用 navKey 拼 :key 保证切换入口时强制重挂载（否则 Vue 沿用旧实例，数据不刷新）。
 */
import { ref } from 'vue'
import Page from './Page.vue'
import Config from './Config.vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'SubscribeCenter' },
})

const pageKey = ref(0)
const settingsDialog = ref(false)

function openSettings() {
  settingsDialog.value = true
}

function afterSave() {
  settingsDialog.value = false
  // 配置保存后重挂载 Page，让它重新拉状态
  pageKey.value += 1
}
</script>

<template>
  <div class="sc-app-page">
    <Page
      :key="`${props.pluginId}-${props.navKey}-${pageKey}`"
      :api="api"
      :plugin-id="pluginId"
      app-page
      @switch="openSettings"
    />

    <!-- 弹窗尺寸必须与插件管理页的「设置」看齐：
     写死 760 会让发现页里的设置窗口明显偏小（真机反馈）。 -->
    <VDialog
      v-model="settingsDialog"
      width="min(1120px, 94vw)"
      max-width="min(1120px, 94vw)"
      scrollable
    >
      <VCard>
        <VCardTitle class="d-flex align-center">
          <span>胖虎订阅中心 · 设置</span>
          <VSpacer />
          <VBtn icon="mdi-close" variant="text" size="small" @click="settingsDialog = false" />
        </VCardTitle>
        <VCardText>
          <Config :api="api" :plugin-id="pluginId" @save="afterSave" @close="settingsDialog = false" />
        </VCardText>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.sc-app-page {
  padding: 8px;
}
</style>
