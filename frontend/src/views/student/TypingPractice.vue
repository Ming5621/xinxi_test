<template>
  <div class="typing-page">
    <div class="page-header">
      <h1>打字练习</h1>
      <p>选择文章和模式后开始。上方为对照文章，下方为输入区</p>
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

    <div class="practice-bar content-card">
      <div class="bar-field article-field" v-if="!inClassTest">
        <span class="bar-label">文章</span>
        <el-select
          v-model="selectedId"
          class="article-select"
          filterable
          :disabled="typingActive || !texts.length"
          :loading="loading"
          placeholder="选择练习文章"
          no-data-text="暂无练习文章"
          no-match-text="没有匹配的文章"
          @change="onArticleChange"
        >
          <el-option
            v-for="item in texts"
            :key="item.id"
            :label="`${item.title}（${item.char_count} 字）`"
            :value="item.id"
          />
        </el-select>
      </div>
      <div class="bar-field class-field" v-else>
        <span class="bar-label">课堂测试</span>
        <span class="class-test-title">{{ classSession?.text_title }}</span>
        <el-tag type="warning" size="small">5 分钟 · 不可停止</el-tag>
      </div>

      <div class="bar-field" v-if="!inClassTest">
        <span class="bar-label">模式</span>
        <el-radio-group
          v-model="practiceMode"
          :disabled="typingActive"
          @change="onModeChange"
        >
          <el-radio-button value="free">自由练习</el-radio-button>
          <el-radio-button value="test">5分钟测试</el-radio-button>
        </el-radio-group>
        <span class="mode-hint">{{ practiceMode === 'free' ? '可随时暂停和停止' : '可随时停止并提交' }}</span>
      </div>

      <div class="bar-actions">
        <el-button
          v-if="!typingActive && !lastFinished"
          type="primary"
          :disabled="!selected"
          @click="startTyping"
        >
          开始打字
        </el-button>
        <template v-if="typingActive && practiceMode === 'free'">
          <el-button v-if="!panelPaused" @click="typingRef?.pause()">暂停</el-button>
          <el-button v-else type="primary" @click="typingRef?.resume()">继续</el-button>
          <el-button type="danger" @click="typingRef?.stop()">停止</el-button>
        </template>
        <el-button
          v-if="typingActive && practiceMode === 'test' && !inClassTest"
          type="danger"
          @click="typingRef?.stop()"
        >
          停止
        </el-button>
        <el-button v-if="lastFinished && !typingActive" @click="retryTyping">再来一次</el-button>
        <el-button @click="historyVisible = true">我的记录</el-button>
      </div>
    </div>

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
        :key="`${selected.id}-${practiceMode}-${sessionKey}-${inClassTest}`"
        :reference-text="selected.content"
        :mode="practiceMode"
        :time-limit="300"
        :allow-stop="!inClassTest"
        expanded
        hide-controls
        @started="onStarted"
        @finished="onFinished"
        @state="onPanelState"
        @complete="handleComplete"
      />
    </section>

    <section class="main-panel content-card empty" v-else>
      <p>{{ loading ? '正在加载文章…' : '暂无练习文章，请等待教师导入' }}</p>
    </section>

    <el-dialog v-model="historyVisible" title="我的打字记录" width="860px">
      <el-table :data="history" stripe size="small" v-loading="historyLoading" empty-text="暂无练习记录" max-height="420">
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
    </el-dialog>
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
const panelPaused = ref(false)
const lastFinished = ref(false)
const historyVisible = ref(false)

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
  if (selectedId.value && !texts.value.some((item) => item.id === selectedId.value)) {
    selectedId.value = texts.value[0]?.id ?? null
  }
  loading.value = false
}

function onArticleChange() {
  if (typingActive.value) return
  lastFinished.value = false
  lastResult.value = null
  sessionKey.value++
}

function onModeChange() {
  lastFinished.value = false
  lastResult.value = null
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
  lastFinished.value = false
}

function startTyping() {
  typingRef.value?.start()
}

function retryTyping() {
  lastFinished.value = false
  lastResult.value = null
  typingRef.value?.reset()
  sessionKey.value++
  setTimeout(() => typingRef.value?.start(), 50)
}

function onStarted() {
  typingActive.value = true
  lastResult.value = null
  lastFinished.value = false
  panelPaused.value = false
}

function onFinished() {
  typingActive.value = false
  panelPaused.value = false
}

function onPanelState(state) {
  panelPaused.value = !!state.paused
  if (state.finished) lastFinished.value = true
}

let sessionPollTimer = null

async function handleComplete(data) {
  typingActive.value = false
  lastFinished.value = true
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
  margin-bottom: 10px;
  flex-shrink: 0;
}

.typing-page {
  flex: 1;
  min-height: 0;
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-header {
  margin-bottom: 10px;
  flex-shrink: 0;
}

.page-header h1 {
  margin: 0 0 2px;
  font-size: 20px;
}

.page-header p {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}

.practice-bar {
  display: flex;
  align-items: center;
  gap: 16px 20px;
  flex-wrap: wrap;
  flex-shrink: 0;
  margin-bottom: 10px;
  padding: 12px 16px;
}

.bar-field {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.article-field {
  flex: 1 1 280px;
}

.bar-label {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.article-select {
  width: 100%;
  min-width: 220px;
}

.class-test-title {
  font-size: 14px;
  color: #111827;
}

.mode-hint {
  font-size: 12px;
  color: #9ca3af;
  white-space: nowrap;
}

.bar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  flex-shrink: 0;
}

.main-panel {
  flex: 1;
  min-width: 0;
  min-height: 0;
  margin-bottom: 0;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
  gap: 16px;
  margin-bottom: 10px;
  padding: 10px 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, #eef2ff, #ecfdf5);
  flex-shrink: 0;
}

.score-main {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.score-value {
  font-size: 32px;
  font-weight: 700;
  color: #4f46e5;
  line-height: 1;
}

.score-unit {
  font-size: 14px;
  color: #6b7280;
}

.score-detail {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #374151;
}

.score-remark {
  color: #6b7280;
}

.main-panel :deep(.typing-panel) {
  flex: 1;
  min-height: 0;
}
</style>
