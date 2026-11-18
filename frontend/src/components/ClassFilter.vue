<template>
  <el-select
    :model-value="modelValue"
    :placeholder="placeholder"
    :clearable="clearable"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-option v-for="c in classes" :key="c" :label="c" :value="c" />
  </el-select>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { classApi } from '@/api'

defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '全部班级' },
  clearable: { type: Boolean, default: true },
})
defineEmits(['update:modelValue'])

const classes = ref([])

async function loadClasses() {
  const res = await classApi.list()
  classes.value = res.classes || []
}

onMounted(() => {
  loadClasses()
  window.addEventListener('exam-classes-changed', loadClasses)
})

onUnmounted(() => {
  window.removeEventListener('exam-classes-changed', loadClasses)
})
</script>
