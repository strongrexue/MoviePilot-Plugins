<script setup>
import { ref } from 'vue'

/**
 * 默认打码、点眼睛可查看的凭据输入框。
 *
 * 说明：打码只改 `type`（显示层），`v-model` 里的值始终是真实内容——
 * 因此"看着是圆点直接保存"不会把星号写进配置。
 * 供后续 115 Cookie / 豆瓣 Cookie / Bot Token 等字段复用。
 */
const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  /** 底层输入类型（如 number）；查看时统一按 text 渲染 */
  inputType: { type: String, default: 'text' },
  /** 初始是否明文显示 */
  startRevealed: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])
const revealed = ref(props.startRevealed)
</script>

<template>
  <VTextField
    :model-value="modelValue"
    :label="label"
    :placeholder="placeholder"
    :type="revealed ? inputType : 'password'"
    density="compact"
    variant="outlined"
    hide-details
    autocomplete="off"
    autocorrect="off"
    autocapitalize="off"
    spellcheck="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #append-inner>
      <VIcon
        :icon="revealed ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
        size="18"
        class="tg-secret-eye"
        :title="revealed ? '隐藏' : '显示'"
        @click="revealed = !revealed"
      />
    </template>
  </VTextField>
</template>

<style scoped>
.tg-secret-eye { cursor: pointer; opacity: 0.7; }
.tg-secret-eye:hover { opacity: 1; }
</style>
