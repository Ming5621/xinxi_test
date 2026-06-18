<template>
  <div class="typing-page">
    <div class="page-header">
      <h1>打字练习</h1>
      <p>左侧选择文章和模式，右侧开始练习</p>
    </div>

    <el-alert
      v-if="classSession && !inClassTest"
      type="warning"
      :closable="false"
      show-icon
      class="class-test-alert"
      :title="`课堂打字测试进行中：${classSession.title}`"
    >
      <template #default>
        <p>教师 {{ classSession.teacher_name }} 发起了 5 分钟打字测试，文章：{{ classSession.text_title }}</p>
        <el-button type="primary" size="small" style="margin-top: 8px" @click="joinClassTest">立即参加</el-button>
      </template>
    </el-alert>

    <div class="typing-layout">
      <!-- 左侧：选项目 -->
      <aside class="sidebar content-card" :class="{ locked: inClassTest }">
        <section v-if="inClassTest" class="sidebar-section class-test-info">
          <h3>课堂测试</h3>
          <p>{{ classSession?.title }}</p>
          <el-tag type="warning" size="small">5 分钟 · 不可暂停</el-tag>
        </section>

        <section class="sidebar-section" v-if="!inClassTest">
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

        <section class="sidebar-section" v-if="!inClassTest">
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
        <div class="score-card" v-if="lastResult">
          <div class="score-main">
            <span class="score-value">{{ lastResult.score }}</span>
            <span class="score-unit">分</span>
          </div>
          <div class="score-detail">
            <el-tag effect="dark" :color="levelColor(lastResult.level)">{{ lastResult.level }}</el-tag>
            <span>{{ lastResult.wpm }} 字/分</span>
            <span>准确率 {{ lastResult.accuracy }}%</span>
            <span class="score-remark">{{ lastResult.remark }}</span>
          </div>
        </div>
        <TypingTest
          ref="typingRef"
          :key="`${selected.id}-${practiceMode}-${sessionKey}`"
          :reference-text="selected.content"
          :mode="practiceMode"
          :time-limit="300"
          expanded
          @started="typingActive = true; lastResult = null"
          @finished="typingActive = false"
          @complete="handleComplete"
        />
      </section>

      <section class="main-panel content-card empty" v-else>
        <p>请先在左侧选择一篇文章</p>
      </section>
    </div>

    <div class="content-card history-card">
      <h3>我的打字记录</h3>
      <el-table :data="history" stripe size="small" v-loading="historyLoading" empty-text="暂无练习记录">
        <el-table-column prop="text_title" label="文章" min-width="160" />
        <el-table-column label="模式" width="100">
          <template #default="{ row }">{{ modeLabel(row.source) }}</template>
        </el-table-column>
        <el-table-column label="评分" width="80">
          <template #default="{ row }"><strong>{{ row.score }}</strong> 分</template>
        </el-table-column>
        <el-table-column label="速度" width="100">
          <template #default="{ row }">{{ row.wpm }} 字/分</template>
        </el-table-column>
        <el-table-column label="准确率" width="90">
          <template #default="{ row }">{{ row.accuracy }}%</template>
        </el-table-column>
        <el-table-column label="等级" width="90">
          <template #default="{ row }">
            <el-tag size="small" :color="levelColor(row.level)" effect="dark">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { typingApi } from '@/api'
import TypingTest from '@/components/TypingTest.vue'

const loading = ref(true)
const texts = ref([])
const selectedId = ref(null)
const practiceMode = ref('free')
const sessionKey = ref(0)
const typingRef = ref()
const classSession = ref(null)
const inClassTest = ref(false)

const selected = computed(() => texts.value.find((t) => t.id === selectedId.value))
const typingActive = ref(false)
const lastResult = ref(null)
const history = ref([])
const historyLoading = ref(false)

const levelColors = {
  卓越: '#7c3aed', 优秀: '#10b981', 良好: '#3b82f6', 达标: '#f59e0b', 未达标: '#ef4444',
}

function levelColor(level) {
  return levelColors[level] || '#6b7280'
}

function formatDate(value) {
  return new Date(value).toLocaleString('zh-CN')
}

async function loadHistory() {
  historyLoading.value = true
  try {
    history.value = await typingApi.myRecords()
  } finally {
    historyLoading.value = false
  }
}

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

function modeLabel(source) {
  if (source === 'class_test') return '课堂测试'
  if (source === 'test') return '5分钟测试'
  return '自由练习'
}

async function checkClassSession() {
  classSession.value = await typingApi.activeSession()
  if (!classSession.value && inClassTest.value) {
    inClassTest.value = false
    practiceMode.value = 'free'
  }
}

function joinClassTest() {
  if (!classSession.value) return
  inClassTest.value = true
  selectedId.value = classSession.value.text_id
  practiceMode.value = 'test'
  sessionKey.value++
  lastResult.value = null
}

let sessionPollTimer = null

async function handleComplete(data) {
  typingActive.value = false
  const payload = {
    text_id: selected.value.id,
    reference_text: selected.value.content,
    typed_text: data.typed_text,
    duration_seconds: data.duration_seconds,
    source: data.mode === 'test' ? 'test' : 'practice',
  }
  if (inClassTest.value && classSession.value) {
    payload.typing_session_id = classSession.value.id
  }
  const result = await typingApi.submit(payload)
  lastResult.value = result
  const modeLabelText = inClassTest.value ? '课堂测试' : (data.mode === 'test' ? '5分钟测试' : '自由练习')
  ElMessage.success(`${modeLabelText}完成：${result.level}，评分 ${result.score} 分`)
  if (inClassTest.value) {
    inClassTest.value = false
    practiceMode.value = 'free'
    await checkClassSession()
  }
  await loadHistory()
}

onMounted(async () => {
  await loadTexts()
  await loadHistory()
  await checkClassSession()
  sessionPollTimer = setInterval(checkClassSession, 8000)
})

onUnmounted(() => {
  if (sessionPollTimer) clearInterval(sessionPollTimer)
})
</script>

<style scoped>
.class-test-alert {
  margin-bottom: 16px;
}

.class-test-info p {
  margin: 6px 0;
  font-size: 13px;
  color: #6b7280;
}

.sidebar.locked .text-item:not(.active) {
  display: none;
}

.typing-page {
  max-width: none;
  margin: 0;
  min-height: calc(100vh - 132px);
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

.score-card {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 16px;
  padding: 18px 22px;
  border-radius: 12px;
  background: linear-gradient(135deg, #eef2ff, #ecfdf5);
}

.score-main {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.score-value {
  font-size: 42px;
  font-weight: 700;
  color: #4f46e5;
  line-height: 1;
}

.score-unit {
  font-size: 16px;
  color: #6b7280;
}

.score-detail {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #374151;
}

.score-remark {
  color: #6b7280;
}

.history-card {
  margin-top: 20px;
}

.history-card h3 {
  margin: 0 0 16px;
  font-size: 16px;
}
</style>
