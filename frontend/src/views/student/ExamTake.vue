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
          <el-tag :type="typeTag(currentQuestion.type)" size="small">
            {{ typeLabel(currentQuestion.type) }}
          </el-tag>
          <span class="question-score">{{ currentQuestion.score }} 分</span>
        </div>

        <template v-if="currentQuestion.type === 'typing'">
          <p class="typing-hint">请在下方输入框中录入以下文字（限时 {{ currentQuestion.typing_config?.time_limit || 120 }} 秒）</p>
          <TypingTest
            :reference-text="currentQuestion.content"
            :time-limit="currentQuestion.typing_config?.time_limit || 120"
            :show-standards="false"
            @complete="onTypingComplete(currentQuestion.id, $event)"
          />
        </template>

        <template v-else>
        <div class="question-content">{{ currentQuestion.content }}</div>

        <div class="options" v-if="currentQuestion.type === 'choice'">
          <div
            v-for="opt in currentQuestion.options"
            :key="opt"
            class="option-item"
            :class="{ selected: answers[currentQuestion.id] === opt[0] }"
            @click="selectAnswer(currentQuestion.id, opt[0])"
          >
            <span class="option-letter">{{ opt[0] }}</span>
            <span class="option-text">{{ opt.slice(3) }}</span>
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
        <el-button :disabled="currentIndex === 0" @click="currentIndex--">
          <el-icon><ArrowLeft /></el-icon> 上一题
        </el-button>
        <div class="nav-dots">
          <span
            v-for="(q, i) in questions"
            :key="q.id"
            class="dot"
            :class="{ active: i === currentIndex, answered: isAnswered(q) }"
            @click="currentIndex = i"
          />
        </div>
        <el-button v-if="currentIndex < questions.length - 1" type="primary" @click="currentIndex++">
          下一题 <el-icon><ArrowRight /></el-icon>
        </el-button>
        <el-button v-else type="success" @click="handleSubmit">
          提交试卷 <el-icon><Check /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="answer-sheet">
      <h4>答题卡</h4>
      <div class="sheet-grid">
        <span
          v-for="(q, i) in questions"
          :key="q.id"
          class="sheet-item"
          :class="{ active: i === currentIndex, answered: answers[q.id] }"
          @click="currentIndex = i"
        >{{ i + 1 }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
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
let timer = null

const currentQuestion = computed(() => questions.value[currentIndex.value])

const typeLabel = { choice: '选择题', judge: '判断题', typing: '打字题' }
const typeTag = { choice: '', judge: 'warning', typing: 'success' }

function isAnswered(q) {
  if (q.type === 'typing') return !!answerMeta.value[q.id]
  return !!answers.value[q.id]
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
  }
}

onMounted(async () => {
  const [examData, qs] = await Promise.all([
    examApi.get(examId),
    examApi.questions(examId),
  ])
  exam.value = examData
  questions.value = qs
  timeLeft.value = examData.duration_minutes * 60
  loading.value = false

  timer = setInterval(() => {
    timeLeft.value--
    if (timeLeft.value <= 0) {
      clearInterval(timer)
      autoSubmit()
    }
  }, 1000)
})

onUnmounted(() => clearInterval(timer))

async function autoSubmit() {
  ElMessage.warning('考试时间到，系统自动提交！')
  await doSubmit()
}

async function handleSubmit() {
  const unanswered = questions.value.filter((q) => !isAnswered(q))
  if (unanswered.length > 0) {
    await ElMessageBox.confirm(
      `还有 ${unanswered.length} 道题未作答，确定提交吗？`,
      '提交确认',
      { type: 'warning' }
    )
  } else {
    await ElMessageBox.confirm('确定提交试卷吗？提交后不可修改。', '提交确认', { type: 'info' })
  }
  await doSubmit()
}

async function doSubmit() {
  const payload = {
    answers: Object.entries(answers.value).map(([question_id, student_answer]) => ({
      question_id: Number(question_id),
      student_answer,
      answer_meta: answerMeta.value[question_id] || null,
    })),
  }
  const result = await examApi.submit(examId, payload)
  clearInterval(timer)
  ElMessage.success(`提交成功！得分: ${result.total_score}/${result.max_score}`)
  router.push('/student/results')
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
</style>
