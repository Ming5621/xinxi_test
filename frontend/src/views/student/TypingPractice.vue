<template>
  <div class="typing-page">
    <div class="page-header">
      <h1>打字练习</h1>
      <p>左侧选择文章和模式，右侧开始练习</p>
    </div>

    <div class="typing-layout">
      <!-- 左侧：选项目 -->
      <aside class="sidebar content-card">
        <section class="sidebar-section">
          <h3>选择文章</h3>
          <div class="text-list" v-loading="loading">
            <button
              v-for="item in texts"
              :key="item.id"
              type="button"
              class="text-item"
              :class="{ active: selectedId === item.id }"
              :disabled="typingActive"
              @click="selectText(item.id)"
            >
              <span class="text-title">{{ item.title }}</span>
              <span class="text-meta">{{ item.content.length }} 字</span>
            </button>
            <p v-if="!loading && !texts.length" class="text-empty">暂无练习文章</p>
          </div>
        </section>

        <section class="sidebar-section">
          <h3>练习模式</h3>
          <el-radio-group
            v-model="practiceMode"
            class="mode-group"
            :disabled="typingActive"
            @change="onModeChange"
          >
            <el-radio-button value="free">自由练习</el-radio-button>
            <el-radio-button value="test">5分钟测试</el-radio-button>
          </el-radio-group>
          <p class="mode-hint" v-if="practiceMode === 'free'">可随时暂停和停止</p>
          <p class="mode-hint warn" v-else>开始后无法暂停或停止</p>
        </section>
      </aside>

      <!-- 右侧：参考文章 + 打字区 -->
      <section class="main-panel content-card" v-if="selected">
        <TypingTest
          ref="typingRef"
          :key="`${selected.id}-${practiceMode}-${sessionKey}`"
          :reference-text="selected.content"
          :mode="practiceMode"
          :time-limit="300"
          expanded
          @started="typingActive = true"
          @finished="typingActive = false"
          @complete="handleComplete"
        />
      </section>

      <section class="main-panel content-card empty" v-else>
        <p>请先在左侧选择一篇文章</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
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

function selectText(id) {
  if (typingActive.value || selectedId.value === id) return
  selectedId.value = id
  sessionKey.value++
}

function onModeChange() {
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
  max-width: none;
  margin: 0;
  height: calc(100vh - 132px);
  display: flex;
  flex-direction: column;
}

.typing-layout {
  flex: 1;
  display: flex;
  gap: 20px;
  min-height: 0;
}

.sidebar {
  width: 280px;
  flex-shrink: 0;
  margin-bottom: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
}

.sidebar-section h3 {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  margin: 0 0 12px;
}

.text-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.text-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s, background 0.2s;
}

.text-item:hover:not(:disabled) {
  border-color: #c7d2fe;
  background: #eef2ff;
}

.text-item.active {
  border-color: #4f46e5;
  background: #eef2ff;
}

.text-item:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.text-title {
  font-size: 14px;
  font-weight: 500;
  color: #111827;
}

.text-meta {
  font-size: 12px;
  color: #9ca3af;
}

.text-empty {
  font-size: 13px;
  color: #9ca3af;
  margin: 0;
}

.mode-group {
  display: flex;
  width: 100%;
}

.mode-group :deep(.el-radio-button) {
  flex: 1;
}

.mode-group :deep(.el-radio-button__inner) {
  width: 100%;
}

.mode-hint {
  margin: 10px 0 0;
  font-size: 13px;
  color: #9ca3af;
}

.mode-hint.warn {
  color: #f59e0b;
}

.main-panel {
  flex: 1;
  min-width: 0;
  margin-bottom: 0;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.empty {
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 15px;
}
</style>
