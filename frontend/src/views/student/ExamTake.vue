<template>
  <div class="exam-take" v-loading="loading">
    <div class="exam-header" v-if="exam">
      <div class="exam-info">
        <h2>{{ exam.title }}</h2>
        <span class="question-progress">第 {{ currentIndex + 1 }} / {{ questions.length }} 题</span>
      </div>
      <div class="exam-timer" :class="{ warning: timeLeft < 300 }">
        <el-icon><Timer /></el-icon>
        <span>{{ formatTime(timeLeft) }}</span>
      </div>
    </div>

    <el-progress
      v-if="questions.length"
      :percentage="Math.round(((currentIndex + 1) / questions.length) * 100)"
      :stroke-width="6"
      :show-text="false"
      color="#4f46e5"
      style="margin-bottom: 20px"
    />

    <div class="question-area" v-if="currentQuestion">
      <div class="question-card">
        <div class="question-header">
          <el-tag :type="typeTag[currentQuestion.type]" size="small">
            {{ typeLabel[currentQuestion.type] }}
          </el-tag>
          <span class="question-score">{{ currentQuestion.score }} 分</span>
        </div>

        <template v-if="currentQuestion.type === 'typing'">
          <p class="typing-hint">请在下方输入框中录入以下文字（限时 {{ currentQuestion.typing_config?.time_limit || 120 }} 秒）</p>
          <TypingTest
            :reference-text="currentQuestion.content"
            :time-limit="currentQuestion.typing_config?.time_limit || 120"
            :max-score="currentQuestion.score"
            :typing-config="currentQuestion.typing_config"
            mode="test"
            :skip-confirm="true"
            disable-retry
            @complete="onTypingComplete(currentQuestion.id, $event)"
          />
          <div class="typing-result" v-if="answerMeta[currentQuestion.id]">
            <el-tag type="success" effect="dark">{{ answerMeta[currentQuestion.id].level }}</el-tag>
            <span>{{ answerMeta[currentQuestion.id].wpm }} 字/分</span>
            <span>准确率 {{ answerMeta[currentQuestion.id].accuracy }}%</span>
            <span v-if="answerMeta[currentQuestion.id].score != null">评分 {{ answerMeta[currentQuestion.id].score }} 分</span>
          </div>
        </template>

        <template v-else>
        <div class="question-content">{{ currentQuestion.content }}</div>

        <div class="options" v-if="currentQuestion.type === 'choice'">
          <div
            v-for="opt in choiceOptions(currentQuestion)"
            :key="opt.value"
            class="option-item"
            :class="{ selected: answers[currentQuestion.id] === opt.value }"
            @click="selectAnswer(currentQuestion.id, opt.value)"
          >
            <span class="option-letter">{{ opt.letter }}</span>
            <span class="option-text">{{ opt.text }}</span>
          </div>
        </div>

        <div class="options" v-else>
          <div
            v-for="opt in ['正确', '错误']"
            :key="opt"
            class="option-item judge-option"
            :class="{ selected: answers[currentQuestion.id] === opt }"
            @click="selectAnswer(currentQuestion.id, opt)"
          >
            <el-icon v-if="opt === '正确'" color="#10b981"><CircleCheck /></el-icon>
            <el-icon v-else color="#ef4444"><CircleClose /></el-icon>
            <span>{{ opt }}</span>
          </div>
        </div>
        </template>
      </div>

      <div class="question-nav">
        <el-button type="button" :disabled="currentIndex === 0" @click.left="goPrev">
          <el-icon><ArrowLeft /></el-icon> 上一题
        </el-button>
        <div class="nav-dots">
          <span
            v-for="(q, i) in questions"
            :key="q.id"
            class="dot"
            :class="{ active: i === currentIndex, answered: isAnswered(q) }"
            @click.left="goToQuestion(i)"
          />
        </div>
        <el-button
          v-if="currentIndex < questions.length - 1"
          type="primary"
          native-type="button"
          @click.left="goNext"
        >
          下一题 <el-icon><ArrowRight /></el-icon>
        </el-button>
        <!-- 仅响应鼠标左键；切题后主动失焦，避免滚轮/空格误触提交 -->
        <el-button
          v-else
          type="success"
          native-type="button"
          :loading="submitting"
          class="submit-exam-btn"
          @click.left="handleSubmit"
        >
          提交试卷 <el-icon><Check /></el-icon>
        </el-button>
      </div>
    </div>

    <el-empty
      v-else-if="!loading && exam && !questions.length"
      description="未获取到考试题目，请返回考试大厅重新进入"
    />

    <div class="answer-sheet" v-if="questions.length">
      <h4>答题卡</h4>
      <div class="sheet-grid">
        <span
          v-for="(q, i) in questions"
          :key="q.id"
          class="sheet-item"
          :class="{ active: i === currentIndex, answered: isAnswered(q) }"
          @click.left="goToQuestion(i)"
        >{{ i + 1 }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { examApi } from '@/api'
import TypingTest from '@/components/TypingTest.vue'

const route = useRoute()
const router = useRouter()
const examId = Number(route.params.id)

const loading = ref(true)
const exam = ref(null)
const questions = ref([])
const answers = ref({})
const answerMeta = ref({})
const currentIndex = ref(0)
const timeLeft = ref(0)
const sessionStartTime = ref(null)
const submitting = ref(false)
const draftKey = `exam_draft_${examId}`
let timer = null

const currentQuestion = computed(() => questions.value[currentIndex.value])

const typeLabel = { choice: '选择题', judge: '判断题', typing: '打字题' }
const typeTag = { choice: '', judge: 'warning', typing: 'success' }

function getRemainingSeconds(durationMinutes, startTime) {
  if (!startTime) return durationMinutes * 60
  const elapsed = Math.floor((Date.now() - new Date(startTime).getTime()) / 1000)
  return Math.max(0, durationMinutes * 60 - elapsed)
}

function saveDraft() {
  sessionStorage.setItem(draftKey, JSON.stringify({
    answers: answers.value,
    answerMeta: answerMeta.value,
    currentIndex: currentIndex.value,
  }))
}

function loadDraft() {
  try {
    const raw = sessionStorage.getItem(draftKey)
    if (!raw) return
    const draft = JSON.parse(raw)
    answers.value = draft.answers || {}
    answerMeta.value = draft.answerMeta || {}
    currentIndex.value = draft.currentIndex || 0
  } catch {
    sessionStorage.removeItem(draftKey)
  }
}

function isAnswered(q) {
  if (q.type === 'typing') return !!answerMeta.value[q.id]
  return !!answers.value[q.id]
}

/** 兼容 "A. 文本" / "A.文本" / 纯文本 等多种选项格式 */
function choiceOptions(question) {
  const letters = ['A', 'B', 'C', 'D']
  const raw = Array.isArray(question.options) ? question.options : []
  return raw.map((opt, i) => {
    const text = String(opt ?? '')
    const m = text.match(/^\s*([A-Da-d])[.、．:：\s]\s*(.*)$/)
    if (m) {
      return { letter: m[1].toUpperCase(), value: m[1].toUpperCase(), text: m[2] || text }
    }
    const letter = letters[i] || String(i + 1)
    return { letter, value: letter, text }
  })
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function selectAnswer(qId, value) {
  answers.value[qId] = value
}

function onTypingComplete(qId, data) {
  answers.value[qId] = data.typed_text
  answerMeta.value[qId] = {
    duration_seconds: data.duration_seconds,
    wpm: data.wpm,
    accuracy: data.accuracy,
    correct_chars: data.correct_chars,
    level: data.level,
    score: data.score,
    remark: data.remark,
  }
}

onMounted(async () => {
  try {
    const session = await examApi.start(examId)
    sessionStartTime.value = session.start_time
    const [examData, qs] = await Promise.all([
      examApi.get(examId),
      examApi.questions(examId).catch(() => []),
    ])
    exam.value = examData
    // 优先专用题目接口；若为空则回退到详情中的题目（不含答案）
    const fromQuestionsApi = Array.isArray(qs) ? qs : []
    const fromExamDetail = Array.isArray(examData?.questions) ? examData.questions : []
    questions.value = fromQuestionsApi.length ? fromQuestionsApi : fromExamDetail
    if (!questions.value.length) {
      ElMessage.error('未获取到考试题目，请确认考试已发布且包含题目')
      router.push('/student')
      return
    }
    loadDraft()
    timeLeft.value = getRemainingSeconds(examData.duration_minutes, session.start_time)
    timer = setInterval(() => {
      timeLeft.value = getRemainingSeconds(examData.duration_minutes, sessionStartTime.value)
      if (timeLeft.value <= 0) {
        clearInterval(timer)
        autoSubmit()
      }
    }, 1000)
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '加载考试失败'
    ElMessage.error(typeof msg === 'string' ? msg : '加载考试失败')
    router.push('/student')
  } finally {
    loading.value = false
  }
})

watch([answers, answerMeta, currentIndex], saveDraft, { deep: true })

onUnmounted(() => clearInterval(timer))

/** 切题后去掉按钮焦点，防止「下一题」变成「提交」后滚轮/空格误触发 */
function blurActive() {
  nextTick(() => {
    const el = document.activeElement
    if (el instanceof HTMLElement) el.blur()
  })
}

function goPrev() {
  if (currentIndex.value > 0) currentIndex.value -= 1
  blurActive()
}

function goNext() {
  if (currentIndex.value < questions.value.length - 1) currentIndex.value += 1
  blurActive()
}

function goToQuestion(i) {
  currentIndex.value = i
  blurActive()
}

async function autoSubmit() {
  ElMessage.warning('考试时间到，系统自动提交！')
  await doSubmit()
}

async function handleSubmit(evt) {
  // 忽略非主键点击、中键滚轮按下等
  if (evt && typeof evt.button === 'number' && evt.button !== 0) return
  try {
    // 先失焦，避免确认框默认按钮被滚轮/空格误点
    blurActive()
    const unanswered = questions.value.filter((q) => !isAnswered(q))
    const boxOpts = {
      type: unanswered.length > 0 ? 'warning' : 'info',
      confirmButtonText: '确认提交',
      cancelButtonText: '继续答题',
      closeOnClickModal: false,
      closeOnPressEscape: true,
      autofocus: false,
      distinguishCancelAndClose: true,
    }
    if (unanswered.length > 0) {
      await ElMessageBox.confirm(
        `还有 ${unanswered.length} 道题未作答，确定提交吗？`,
        '提交确认',
        boxOpts
      )
    } else {
      await ElMessageBox.confirm('确定提交试卷吗？提交后不可修改。', '提交确认', boxOpts)
    }
    await doSubmit()
  } catch {
    // 用户取消
  }
}

async function doSubmit() {
  if (submitting.value) return
  submitting.value = true
  try {
    const payload = {
      answers: Object.entries(answers.value).map(([question_id, student_answer]) => ({
        question_id: Number(question_id),
        student_answer,
        answer_meta: answerMeta.value[question_id] || null,
      })),
    }
    const result = await examApi.submit(examId, payload)
    clearInterval(timer)
    sessionStorage.removeItem(draftKey)
    ElMessage.success(`提交成功！得分: ${result.total_score}/${result.max_score}`)
    router.push('/student/results')
  } catch {
    // 错误由拦截器提示
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.exam-take {
  max-width: 900px;
  margin: 0 auto;
}

.typing-hint {
  color: #6b7280;
  font-size: 14px;
  margin-bottom: 16px;
}

.typing-result {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
  padding: 14px 18px;
  background: #ecfdf5;
  border-radius: 10px;
  font-size: 14px;
  color: #065f46;
}

.exam-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  padding: 20px 24px;
  border-radius: 12px;
  margin-bottom: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.exam-info h2 {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.question-progress {
  color: #6b7280;
  font-size: 14px;
}

.exam-timer {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 24px;
  font-weight: 700;
  color: #4f46e5;
  font-variant-numeric: tabular-nums;
}

.exam-timer.warning {
  color: #ef4444;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  50% { opacity: 0.6; }
}

.question-card {
  background: white;
  border-radius: 12px;
  padding: 28px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  margin-bottom: 16px;
}

.question-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.question-score {
  color: #f59e0b;
  font-weight: 600;
}

.question-content {
  font-size: 17px;
  line-height: 1.8;
  margin-bottom: 24px;
  color: #111827;
}

.options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.option-item:hover {
  border-color: #a5b4fc;
  background: #f5f3ff;
}

.option-item.selected {
  border-color: #4f46e5;
  background: #eef2ff;
}

.option-letter {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: #4f46e5;
  flex-shrink: 0;
}

.option-item.selected .option-letter {
  background: #4f46e5;
  color: white;
}

.judge-option {
  justify-content: center;
  font-size: 16px;
  font-weight: 500;
}

.question-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: white;
  padding: 16px 24px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  margin-bottom: 16px;
}

.nav-dots {
  display: flex;
  gap: 6px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #e5e7eb;
  cursor: pointer;
  transition: all 0.2s;
}

.dot.answered { background: #a5b4fc; }
.dot.active { background: #4f46e5; transform: scale(1.3); }

.answer-sheet {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.answer-sheet h4 {
  margin-bottom: 12px;
  font-size: 14px;
  color: #6b7280;
}

.sheet-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sheet-item {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.sheet-item.answered {
  background: #eef2ff;
  border-color: #a5b4fc;
  color: #4f46e5;
}

.sheet-item.active {
  background: #4f46e5;
  border-color: #4f46e5;
  color: white;
}

.submit-exam-btn {
  /* 降低被页面滚动连带误触的概率 */
  scroll-margin: 80px;
}
</style>
