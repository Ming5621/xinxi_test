<template>
  <div class="typing-test">
    <div class="typing-stats">
      <div class="stat-item">
        <span class="stat-value">{{ liveWpm }}</span>
        <span class="stat-label">字/分钟</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ liveAccuracy }}%</span>
        <span class="stat-label">准确率</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ formatTime(timeLeft) }}</span>
        <span class="stat-label">剩余时间</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ typedText.length }}/{{ referenceText.length }}</span>
        <span class="stat-label">进度</span>
      </div>
    </div>

    <div class="reference-box" ref="refBox">
      <span
        v-for="(char, i) in referenceChars"
        :key="i"
        class="ref-char"
        :class="charClass(i)"
      >{{ char === ' ' ? '\u00A0' : char }}</span>
    </div>

    <el-input
      ref="inputRef"
      v-model="typedText"
      type="textarea"
      :rows="4"
      :disabled="finished"
      placeholder="请在此输入上方文字..."
      @input="onInput"
      @keydown="onKeydown"
    />

    <div class="typing-actions">
      <el-button v-if="!started && !finished" type="primary" size="large" @click="startTest">
        开始打字
      </el-button>
      <el-button v-if="started && !finished" type="success" size="large" @click="finishTest">
        完成
      </el-button>
      <el-button v-if="finished" size="large" @click="resetTest">重新练习</el-button>
    </div>

    <div v-if="result" class="result-panel" :style="{ borderColor: resultColor }">
      <div class="result-level" :style="{ color: resultColor }">{{ result.level }}</div>
      <div class="result-detail">
        速度 <strong>{{ result.wpm }}</strong> 字/分钟 ·
        准确率 <strong>{{ result.accuracy }}%</strong> ·
        正确 <strong>{{ result.correct_chars }}</strong> 字
      </div>
      <div class="result-desc">{{ result.level_desc }}</div>
      <el-tag v-if="result.passed" type="success">已达课标要求</el-tag>
      <el-tag v-else type="warning">继续加油练习</el-tag>
    </div>

    <div v-if="showStandards" class="standards-panel">
      <h4>初中打字标准参考</h4>
      <div class="level-bars">
        <div v-for="lv in standards" :key="lv.level" class="level-bar">
          <span class="lv-name" :style="{ color: lv.color }">{{ lv.level }}</span>
          <span class="lv-wpm">≥{{ lv.min_wpm }} 字/分</span>
          <span class="lv-desc">{{ lv.desc }}</span>
        </div>
      </div>
      <p class="accuracy-hint">准确率要求：≥ 95%（义务教育信息科技课标）</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps({
  referenceText: { type: String, required: true },
  timeLimit: { type: Number, default: 120 },
  showStandards: { type: Boolean, default: true },
  autoStart: { type: Boolean, default: false },
})

const emit = defineEmits(['complete'])

const typedText = ref('')
const started = ref(false)
const finished = ref(false)
const timeLeft = ref(props.timeLimit)
const startTime = ref(0)
const elapsed = ref(0)
const result = ref(null)
const inputRef = ref()
let timer = null

const standards = [
  { level: '卓越', min_wpm: 40, color: '#7c3aed', desc: '远超课标要求' },
  { level: '优秀', min_wpm: 30, color: '#10b981', desc: '达到课标基础达标' },
  { level: '良好', min_wpm: 20, color: '#3b82f6', desc: '高于中考基本要求' },
  { level: '达标', min_wpm: 10, color: '#f59e0b', desc: '达到中考信息技术要求' },
  { level: '未达标', min_wpm: 0, color: '#ef4444', desc: '需继续练习' },
]

const referenceChars = computed(() => props.referenceText.split(''))

const liveStats = computed(() => {
  const typed = typedText.value
  const ref = props.referenceText
  let correct = 0
  for (let i = 0; i < typed.length; i++) {
    if (typed[i] === ref[i]) correct++
  }
  const acc = typed.length ? Math.round((correct / typed.length) * 100) : 100
  const mins = elapsed.value > 0 ? elapsed.value / 60 : 0
  const wpm = mins > 0 ? Math.round((correct / mins) * 10) / 10 : 0
  return { correct, accuracy: acc, wpm }
})

const liveWpm = computed(() => started.value ? liveStats.value.wpm : 0)
const liveAccuracy = computed(() => started.value ? liveStats.value.accuracy : 100)

const resultColor = computed(() => {
  if (!result.value) return '#4f46e5'
  const lv = standards.find((s) => s.level === result.value.level)
  return lv?.color || '#4f46e5'
})

function charClass(i) {
  const typed = typedText.value
  if (i >= typed.length) return i === typed.length ? 'current' : 'pending'
  if (typed[i] === referenceChars.value[i]) return 'correct'
  return 'wrong'
}

function formatTime(s) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function startTest() {
  started.value = true
  finished.value = false
  result.value = null
  typedText.value = ''
  timeLeft.value = props.timeLimit
  startTime.value = Date.now()
  timer = setInterval(() => {
    elapsed.value = (Date.now() - startTime.value) / 1000
    timeLeft.value = Math.max(0, props.timeLimit - Math.floor(elapsed.value))
    if (timeLeft.value <= 0) finishTest()
  }, 200)
  nextTick(() => inputRef.value?.focus())
}

function onInput() {
  if (!started.value) startTest()
  if (typedText.value.length >= props.referenceText.length) {
    finishTest()
  }
}

function onKeydown(e) {
  if (e.key === 'Tab') e.preventDefault()
}

function finishTest() {
  if (finished.value) return
  clearInterval(timer)
  finished.value = true
  elapsed.value = (Date.now() - startTime.value) / 1000

  const stats = liveStats.value
  const level = standards.find((s) => stats.wpm >= s.min_wpm) || standards[standards.length - 1]
  const passed = stats.wpm >= 10 && stats.accuracy >= 95

  result.value = {
    wpm: stats.wpm,
    accuracy: stats.accuracy,
    correct_chars: stats.correct,
    error_chars: typedText.value.length - stats.correct,
    total_chars: props.referenceText.length,
    level: level.level,
    level_desc: level.desc,
    passed,
  }

  emit('complete', {
    typed_text: typedText.value,
    duration_seconds: elapsed.value,
    ...result.value,
  })
}

function resetTest() {
  clearInterval(timer)
  typedText.value = ''
  started.value = false
  finished.value = false
  result.value = null
  elapsed.value = 0
  timeLeft.value = props.timeLimit
}

watch(() => props.referenceText, () => resetTest())

onMounted(() => {
  if (props.autoStart) startTest()
})

onUnmounted(() => clearInterval(timer))

defineExpose({ resetTest, getResult: () => result.value, getTypedText: () => typedText.value })
</script>

<style scoped>
.typing-test {
  max-width: 800px;
  margin: 0 auto;
}

.typing-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.stat-item {
  background: white;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.stat-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: #4f46e5;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 13px;
  color: #9ca3af;
}

.reference-box {
  background: #1e1b4b;
  color: #e0e7ff;
  border-radius: 12px;
  padding: 24px;
  font-size: 20px;
  line-height: 2;
  letter-spacing: 2px;
  margin-bottom: 16px;
  min-height: 100px;
  font-family: 'PingFang SC', 'Microsoft YaHei', monospace;
}

.ref-char {
  transition: color 0.1s;
}

.ref-char.pending { color: #6366f1; opacity: 0.5; }
.ref-char.current { color: #fbbf24; background: rgba(251, 191, 36, 0.2); border-bottom: 2px solid #fbbf24; }
.ref-char.correct { color: #34d399; }
.ref-char.wrong { color: #f87171; background: rgba(248, 113, 113, 0.2); }

.typing-actions {
  text-align: center;
  margin: 20px 0;
}

.result-panel {
  background: white;
  border-radius: 16px;
  padding: 24px;
  text-align: center;
  border: 2px solid;
  margin-bottom: 20px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
}

.result-level {
  font-size: 36px;
  font-weight: 800;
  margin-bottom: 8px;
}

.result-detail {
  font-size: 16px;
  color: #374151;
  margin-bottom: 8px;
}

.result-desc {
  font-size: 14px;
  color: #9ca3af;
  margin-bottom: 12px;
}

.standards-panel {
  background: #f9fafb;
  border-radius: 12px;
  padding: 20px;
}

.standards-panel h4 {
  margin-bottom: 12px;
  color: #374151;
}

.level-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.level-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.lv-name { font-weight: 600; width: 50px; }
.lv-wpm { color: #6b7280; width: 90px; }
.lv-desc { color: #9ca3af; }

.accuracy-hint {
  margin-top: 12px;
  font-size: 13px;
  color: #6b7280;
}
</style>
