<script setup>
/**
 * 单个布局参数字段的渲染器：按 schema 的 type 生成控件。
 *
 * 直接修改传入的 `config` 对象（同一个 reactive 实例），避免为每个字段做 v-model 代理。
 */
const props = defineProps({
  item: { type: Object, required: true },
  config: { type: Object, required: true },
  fonts: { type: Array, default: () => [] },
})

/** select 的 options 统一成 {title, value}，避免 Vuetify 渲染成 [object Object]。 */
function selectItems() {
  return (props.item.options || []).map(option => ({
    title: option.label !== undefined ? option.label : option.title,
    value: option.value,
  }))
}
</script>

<template>
  <!-- 滑块 -->
  <div v-if="item.type === 'range'" class="ec-slider">
    <div class="ec-slider-head">
      <span>{{ item.label }}</span>
      <b>{{ config[item.key] }}</b>
    </div>
    <VSlider
      v-model="config[item.key]"
      :min="item.min !== undefined && item.min !== null ? item.min : 0"
      :max="item.max !== undefined && item.max !== null ? item.max : 100"
      :step="item.step || 1"
      density="compact"
      hide-details
      color="primary"
      thumb-label
    />
  </div>
  <!-- 下拉 -->
  <VSelect
    v-else-if="item.type === 'select'"
    v-model="config[item.key]"
    :items="selectItems()"
    :label="item.label"
    density="compact"
    variant="outlined"
    hide-details
  />
  <!-- 字体 -->
  <VSelect
    v-else-if="item.type === 'font'"
    v-model="config[item.key]"
    :items="fonts"
    :label="item.label"
    density="compact"
    variant="outlined"
    hide-details
  />
  <!-- 开关 -->
  <VSwitch
    v-else-if="item.type === 'boolean'"
    v-model="config[item.key]"
    :label="item.label"
    color="primary"
    hide-details
    inset
    density="compact"
  />
  <!-- 颜色：色块 + 文本框（整行，避免两列里被挤扁） -->
  <div v-else-if="item.type === 'color'" class="ec-color">
    <label class="ec-color-swatch" :style="{ background: config[item.key] || '#000000' }">
      <input
        type="color"
        class="ec-color-input"
        :value="config[item.key] || '#000000'"
        @input="config[item.key] = $event.target.value"
      />
    </label>
    <VTextField
      v-model="config[item.key]"
      :label="item.label"
      density="compact"
      variant="outlined"
      hide-details
    />
  </div>
  <!-- 数字 / 文本 -->
  <VTextField
    v-else
    v-model="config[item.key]"
    :label="item.label"
    :type="item.type === 'number' ? 'number' : 'text'"
    density="compact"
    variant="outlined"
    hide-details
  />
</template>

<style scoped>
.ec-slider {
  grid-column: 1 / -1;
}
.ec-slider-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 2px;
  opacity: 0.85;
}
.ec-color {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}
.ec-color-swatch {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  overflow: hidden;
  cursor: pointer;
  display: block;
}
.ec-color-input {
  width: 100%;
  height: 100%;
  border: none;
  padding: 0;
  background: transparent;
  cursor: pointer;
}
</style>
