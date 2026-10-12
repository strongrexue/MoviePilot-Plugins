<script setup>
import { computed, onMounted, ref } from 'vue'
import ConfigTgPane from './config/ConfigTgPane.vue'
import { useConfigForm } from './config/useConfigForm'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'TgMediaCenter' },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close'])

const config = useConfigForm({
  api: () => props.api,
  pluginId: () => props.pluginId,
  initialConfig: () => props.initialConfig,
  emit,
})

const modules = [
  { key: 'tg', title: 'TG 凭证', icon: 'mdi-send-lock-outline', desc: '登录向导、冷却与保活、对话列表' },
  { key: 'pan115', title: '115 网盘', icon: 'mdi-cloud-outline', desc: '登录态、目标目录、批量提交' },
  { key: 'douban', title: '豆瓣源', icon: 'mdi-rss', desc: '想看 RSS 与自定义榜单规则' },
  { key: 'monitor', title: '资源监控', icon: 'mdi-radar', desc: '监听频道、推送目标、仅缺集' },
  { key: 'cache', title: '消息缓存', icon: 'mdi-database-outline', desc: '缓存频道、同步与检索' },
  { key: 'forward', title: '通用转发', icon: 'mdi-share-outline', desc: '两级匹配、置顶与内容转换' },
]

const activeModule = ref(modules[0].key)
const current = computed(() => modules.find(item => item.key === activeModule.value) || modules[0])

onMounted(config.loadConfig)
</script>

<template>
  <div class="tg-config">
    <VCard flat class="tg-card">
      <VCardItem class="tg-header">
        <template #prepend>
          <VAvatar color="primary" variant="tonal" size="44" rounded="lg">
            <VIcon icon="mdi-send-circle-outline" size="24" />
          </VAvatar>
        </template>
        <VCardTitle class="text-h6">TG媒体中心</VCardTitle>
        <VCardSubtitle class="text-caption">{{ current.desc }}</VCardSubtitle>
        <template #append>
          <VSwitch
            v-model="config.form.enabled"
            color="success"
            hide-details
            inset
            :label="config.form.enabled ? '已启用' : '已停用'"
          />
        </template>
      </VCardItem>
      <VDivider />
      <div class="tg-body">
        <nav class="tg-nav">
          <VList density="comfortable" nav class="py-2">
            <VListItem
              v-for="item in modules"
              :key="item.key"
              :active="activeModule === item.key"
              color="primary"
              rounded="lg"
              @click="activeModule = item.key"
            >
              <template #prepend><VIcon :icon="item.icon" /></template>
              <VListItemTitle>{{ item.title }}</VListItemTitle>
            </VListItem>
          </VList>
        </nav>
        <section class="tg-content">
          <VProgressLinear v-if="config.loading" indeterminate color="primary" height="2" class="mb-3" />
          <VAlert v-if="config.error" type="warning" variant="tonal" density="compact" class="mb-3">
            {{ config.error }}
          </VAlert>

          <ConfigTgPane
            v-if="activeModule === 'tg'"
            :api="props.api"
            :plugin-id="props.pluginId"
            :config="config"
          />
          <VAlert v-else type="info" variant="tonal" density="comfortable">
            「{{ current.title }}」配置面板待实现（见设计文档对应模块）。
          </VAlert>
        </section>
      </div>
      <VDivider />
      <VCardActions>
        <VSpacer />
        <VBtn variant="text" @click="emit('close')">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="config.saveConfig">
          保存配置
        </VBtn>
      </VCardActions>
    </VCard>
  </div>
</template>

<style scoped>
.tg-config { width: min(1120px, calc(100vw - 48px)); max-width: 100%; padding: 8px; }
.tg-card {
  width: 100%;
  height: min(860px, calc(100dvh - 48px));
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.tg-header { flex: 0 0 auto; padding: 14px 18px; }
.tg-body { flex: 1 1 auto; min-height: 0; display: flex; }
.tg-nav {
  width: 160px;
  flex: 0 0 160px;
  border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgba(var(--v-theme-on-surface), 0.02);
}
.tg-content { flex: 1 1 auto; min-width: 0; min-height: 0; overflow-y: auto; padding: 16px; }
@media (max-width: 760px) {
  .tg-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }
  .tg-body { flex-direction: column; }
  .tg-nav {
    width: 100%;
    flex: 0 0 auto;
    border-right: none;
    border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    overflow-x: auto;
  }
}
</style>
