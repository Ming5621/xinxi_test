<template>
  <div class="typing-page">
    <div class="page-header">
      <h1>打字练习</h1>
      <p>选择一篇文章，开始练习</p>
    </div>

    <div class="content-card setup-card">
      <div class="setup-row">
        <label>选择文章</label>
        <el-select v-model="selectedId" placeholder="请选择文章" style="width: 100%" :disabled="typingActive" @change="onSelect">
          <el-option
            v-for="item in texts"
            :key="item.id"
            :label="item.title"
            :value="item.id"
          />
        </el-select>
      </div>

      <div class="setup-row">
        <label>练习模式</label>
        <el-radio-group v-model="practiceMode" :disabled="typingActive" @change="onModeChange">
          <el-radio-button value="free">自由练习</el-radio-button>
          <el-radio-button value="test">5分钟测试</el-radio-button>
        </el-radio-group>
        <span class="mode-hint" v-if="practiceMode === 'free'">可随时暂停和停止</span>
        <span class="mode-hint warn" v-else>开始后无法暂停或停止</span>
      </div>
    </div>

    <div class="content-card typing-area" v-if="selected">
      <TypingTest
        ref="typingRef"
        :key="`${selected.id}-${practiceMode}-${sessionKey}`"
        :reference-text="selected.content"
        :mode="practiceMode"
        :time-limit="300"
        @started="typingActive = true"
        @finished="typingActive = false"
        @complete="handleComplete"
      />
    </div>

    <div class="content-card empty" v-else>
      <p>请先选择一篇文章</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { typingApi } from '@/api'
import TypingTest from '@/components/TypingTest.vue'

const loading = ref(true)
const texts = ref([])
const selectedId = ref(null)
const practiceMode = ref('free')
const sessionKey = ref(0)
const typingRef = ref()

const selected = computed(() => texts.value.find((t) => t.id === selectedId.value))
const typingActive = ref(false)

async function loadTexts() {
  loading.value = true
  texts.value = await typingApi.texts()
  if (texts.value.length && !selectedId.value) {
    selectedId.value = texts.value[0].id
  }
  loading.value = false
}

function onSelect() {
  sessionKey.value++
}

async function onModeChange() {
  sessionKey.value++
}

async function handleComplete(data) {
  typingActive.value = false
  await typingApi.submit({
    text_id: selected.value.id,
    reference_text: selected.value.content,
    typed_text: data.typed_text,
    duration_seconds: data.duration_seconds,
    source: data.mode === 'test' ? 'test' : 'practice',
  })
  const modeLabel = data.mode === 'test' ? '5分钟测试' : '自由练习'
  ElMessage.success(`${modeLabel}完成：${data.level}，${data.wpm} 字/分钟`)
}

onMounted(loadTexts)
</script>

<style scoped>
.typing-page {
  max-width: 900px;
  margin: 0 auto;
}

.setup-card {
  margin-bottom: 16px;
}

.setup-row {
  margin-bottom: 16px;
}

.setup-row:last-child {
  margin-bottom: 0;
}

.setup-row label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
}

.mode-hint {
  margin-left: 12px;
  font-size: 13px;
  color: #9ca3af;
}

.mode-hint.warn {
  color: #f59e0b;
}

.typing-area {
  padding: 24px;
}

.empty {
  text-align: center;
  padding: 60px;
  color: #9ca3af;
}
</style>
