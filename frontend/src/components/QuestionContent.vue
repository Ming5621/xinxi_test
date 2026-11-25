<template>
  <div class="rich-question">
    <template v-for="(part, index) in parts" :key="index">
      <img v-if="part.type === 'image'" :src="part.src" :alt="part.alt || '题目图片'" loading="lazy" />
      <div v-else-if="part.type === 'code'" class="code-block"><small v-if="part.language">{{ part.language }}</small><pre><code>{{ part.text }}</code></pre></div>
      <span v-else>{{ part.text }}</span>
    </template>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { parseQuestionContent } from '@/utils/questionContent'
const props = defineProps({ content: { type: String, default: '' } })
const parts = computed(() => parseQuestionContent(props.content))
</script>
<style scoped>
.rich-question { white-space: pre-wrap; overflow-wrap: anywhere; min-width: 0; max-width: 100%; }
img { display: block; max-width: 100%; max-height: 480px; object-fit: contain; margin: 8px 0; }
.code-block { background: #111827; color: #f3f4f6; border-radius: 8px; padding: 12px; margin: 8px 0; white-space: normal; }
small { color: #9ca3af; }
pre { overflow-x: auto; white-space: pre; margin: 6px 0; tab-size: 4; }
code { font-family: Consolas, monospace; }
</style>
