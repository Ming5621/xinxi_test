<template>
  <div class="rich-editor">
    <div class="toolbar">
      <el-button size="small" :disabled="disabled || reading" @click="fileInput.click()">插入图片</el-button>
      <el-button size="small" :disabled="disabled" @click="insert('\n```python\n# 在这里输入代码\n```\n')">插入代码块</el-button>
      <el-checkbox v-model="preview">预览</el-checkbox>
      <span>图片限 2 MB；代码块首行可修改语言</span>
      <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden :disabled="disabled" @change="addImage" />
    </div>
    <el-input ref="input" :model-value="modelValue" type="textarea" :rows="rows" :placeholder="placeholder" :disabled="disabled" @update:model-value="$emit('update:modelValue', $event)" />
    <QuestionContent v-if="preview" class="preview" :content="modelValue" />
  </div>
</template>
<script setup>
import { ref, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import QuestionContent from './QuestionContent.vue'
const props = defineProps({ modelValue: { type: String, default: '' }, placeholder: String, rows: { type: Number, default: 3 }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const fileInput = ref(null)
const input = ref(null)
const preview = ref(false)
const reading = ref(false)
async function insert(text) {
  if (props.disabled) return
  const area = input.value?.textarea
  const start = area?.selectionStart ?? props.modelValue.length
  const end = area?.selectionEnd ?? start
  emit('update:modelValue', props.modelValue.slice(0, start) + text + props.modelValue.slice(end))
  await nextTick()
  area?.focus()
  area?.setSelectionRange(start + text.length, start + text.length)
}
async function addImage(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (!file || props.disabled) return
  if (!['image/png', 'image/jpeg', 'image/gif', 'image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024) {
    ElMessage.warning('请选择不超过 2 MB 的 PNG、JPEG、GIF 或 WebP 图片')
    return
  }
  reading.value = true
  try {
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
    await insert(`\n![图片](${data})\n`)
    preview.value = true
  } catch { ElMessage.error('图片读取失败，请重新选择') }
  finally { reading.value = false }
}
</script>
<style scoped>
.rich-editor { width: 100%; min-width: 0; margin-bottom: 12px; }
.toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 6px; }
.toolbar span { color: #6b7280; font-size: 12px; }
.preview { margin-top: 8px; border: 1px solid #e5e7eb; padding: 12px; background: white; border-radius: 6px; }
</style>
