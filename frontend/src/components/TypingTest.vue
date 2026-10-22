<template>
  <div class="typing-panel" :class="{ expanded, 'hide-controls': hideControls }">
    <div class="status-bar" v-if="started">
      <span>{{ liveWpm }} 字/分</span>
      <span>准确率 {{ liveAccuracy }}%</span>
      <span v-if="mode === 'test'">剩余 {{ formatTime(timeLeft) }}</span>
      <span v-else>用时 {{ formatTime(elapsed) }}</span>
      <span v-if="paused" class="paused-tag">已暂停</span>
    </div>

    <div class="article-box" ref="articleRef">
      <span
        v-for="(char, i) in referenceChars"
        :key="i"
        class="char"
        :class="charClass(i)"
      >{{ char === ' ' ? '\u00A0' : char }}</span>
    </div>

    <div class="input-wrap">
      <textarea
        ref="inputRef"
        v-model="typedText"
        class="input-box"
        :disabled="!started || finished || paused"
        :placeholder="started ? '请开始输入...' : '开始后在此输入'"
        @input="onInput"
        @keydown="onKeydown"
      />
    </div>

    <div class="actions" v-if="!hideControls">
      <template v-if="!started && !finished">
        <el-button type="primary" size="large" @click="start">开始</el-button>
      </template>

      <template v-if="mode === 'free' && started && !finished">
        <el-button v-if="!paused" @click="pause">暂停</el-button>
        <el-button v-else type="primary" @click="resume">继续</el-button>
        <el-button type="danger" @click="stop">停止</el-button>
      </template>

      <template v-if="mode === 'test' && allowStop && started && !finished">
        <el-button type="danger" @click="stop">停止</el-button>
      </template>

      <template v-if="finished">
        <div class="result-brief">
          <strong>{{ result.level }}</strong> · {{ result.wpm }} 字/分 · 准确率 {{ result.accuracy }}%
          <span v-if="result.score != null"> · 评分 {{ result.score }} 分</span>
        </div>
        <el-button v-if="!disableRetry" @click="reset">再来一次</el-button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted, watch, nextTick } from 'vue'
import { ElMessageBox } from 'element-plus'

const props = defineProps({
  referenceText: { type: String, required: true },
  mode: { type: String, default: 'free' }, // free | test
  timeLimit: { type: Number, default: 300 },
  skipConfirm: { type: Boolean, default: false },
  allowStop: { type: Boolean, default: false },
  expanded: { type: Boolean, default: false },
  maxScore: { type: Number, default: 100 },
  disableRetry: { type: Boolean, default: false },
  typingConfig: { type: Object, default: null },
  hideControls: { type: Boolean, default: false },
})

const emit = defineEmits(['complete', 'started', 'finished', 'state'])

const typedText = ref('')
const started = ref(false)
const finished = ref(false)
const paused = ref(false)
const timeLeft = ref(props.timeLimit)
const elapsed = ref(0)
const startTime = ref(0)
const pausedDuration = ref(0)
const pauseStart = ref(0)
const result = ref(null)
const inputRef = ref()
const articleRef = ref()
let timer = null

const standards = [
  { level: '卓越', min_wpm: 40 },
  { level: '优秀', min_wpm: 30 },
  { level: '良好', min_wpm: 20 },
  { level: '达标', min_wpm: 10 },
  { level: '未达标', min_wpm: 0 },
]

const referenceChars = computed(() => props.referenceText.split(''))

const liveStats = computed(() => calcStats(typedText.value, props.referenceText, getActiveElapsed()))

const liveWpm = computed(() => (started.value && !paused.value) ? liveStats.value.wpm : 0)
const liveAccuracy = computed(() => started.value ? liveStats.value.accuracy : 100)

function emitState() {
  emit('state', {
    started: started.value,
    finished: finished.value,
    paused: paused.value,
    mode: props.mode,
  })
}

function getActiveElapsed() {
  if (!started.value) return 0
  const now = paused.value ? pauseStart.value : Date.now()
  return (now - startTime.value - pausedDuration.value) / 1000
}

function calcStats(typed, reference, seconds) {
  const ref = reference.trim()
  const input = typed.trim()
  let correct = 0
  const maxLen = Math.max(ref.length, input.length)
  for (let i = 0; i < maxLen; i++) {
    const refChar = i < ref.length ? ref[i] : ''
    const typedChar = i < input.length ? input[i] : ''
    if (refChar && typedChar && refChar === typedChar) {
      correct += 1
    }
  }
  const refLen = ref.length || 1
  const acc = Math.round((correct / refLen) * 1000) / 10
  const mins = seconds > 1 ? seconds / 60 : 0
  const wpm = mins > 0 ? Math.round((correct / mins) * 10) / 10 : 0
  return { correct, accuracy: acc, wpm }
}

const HIGH_GRADES = ['良好', '优秀', '卓越']

function resolveLevel(wpm, accuracy) {
  const cfg = props.typingConfig || {}
  const minAccuracy = cfg.min_accuracy ?? 95
  const bySpeed = standards.find((s) => wpm >= s.min_wpm) || standards[standards.length - 1]
  if (accuracy < minAccuracy && HIGH_GRADES.includes(bySpeed.level)) {
    return standards.find((s) => s.level === '达标' && wpm >= s.min_wpm) || standards[standards.length - 1]
  }
  return bySpeed
}

function calcScore(wpm, accuracy, maxScore) {
  const cfg = props.typingConfig || {}
  const minAccuracy = cfg.min_accuracy ?? 95
  const minWpm = cfg.min_wpm ?? 10
  if (accuracy < 80) return Math.round(maxScore * 0.2 * 10) / 10
  if (accuracy < minAccuracy) return Math.round(maxScore * 0.4 * (accuracy / minAccuracy) * 10) / 10
  if (wpm >= 40) return maxScore
  if (wpm >= 30) return Math.round(maxScore * 0.9 * 10) / 10
  if (wpm >= 20) return Math.round(maxScore * 0.75 * 10) / 10
  if (wpm >= minWpm) return Math.round(maxScore * 0.6 * 10) / 10
  return Math.round(maxScore * (wpm / minWpm) * 0.4 * 10) / 10
}

function charClass(i) {
  const typed = typedText.value
  if (!started.value) return 'idle'
  if (i >= typed.length) return i === typed.length ? 'current' : 'idle'
  return typed[i] === referenceChars.value[i] ? 'ok' : 'err'
}

function formatTime(s) {
  const sec = Math.floor(s)
  const m = Math.floor(sec / 60)
  const r = sec % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}

function tick() {
  elapsed.value = getActiveElapsed()
  if (props.mode === 'test') {
    timeLeft.value = Math.max(0, props.timeLimit - Math.floor(elapsed.value))
    if (timeLeft.value <= 0) finish()
  }
}

async function start() {
  if (props.mode === 'test' && !props.skipConfirm) {
    const message = props.allowStop
      ? '5分钟测试开始后可随时停止并提交当前成绩，时间到也会自动结束。确定开始吗？'
      : '测试开始后无法暂停或停止，时间到自动结束。确定开始吗？'
    try {
      await ElMessageBox.confirm(message, '开始测试', {
        type: 'warning',
        confirmButtonText: '开始',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }

  started.value = true
  finished.value = false
  paused.value = false
  result.value = null
  typedText.value = ''
  timeLeft.value = props.timeLimit
  startTime.value = Date.now()
  pausedDuration.value = 0
  timer = setInterval(tick, 200)
  emit('started')
  emitState()
  nextTick(() => inputRef.value?.focus())
}

function pause() {
  if (props.mode !== 'free' || !started.value || finished.value) return
  paused.value = true
  pauseStart.value = Date.now()
  emitState()
}

function resume() {
  if (!paused.value) return
  pausedDuration.value += Date.now() - pauseStart.value
  paused.value = false
  emitState()
  nextTick(() => inputRef.value?.focus())
}

function stop() {
  if (props.mode === 'free' || (props.mode === 'test' && props.allowStop)) {
    finish()
  }
}

function onInput() {
  if (props.mode === 'free' && typedText.value.length >= props.referenceText.length) {
    finish()
  }
  // 仅在对照区内滚动，避免带动整页把「提交」按钮滚到指针下误触
  nextTick(() => {
    const box = articleRef.value
    const current = box?.querySelector('.char.current')
    if (!box || !current) return
    const boxRect = box.getBoundingClientRect()
    const charRect = current.getBoundingClientRect()
    if (charRect.top < boxRect.top || charRect.bottom > boxRect.bottom) {
      const delta = charRect.top - boxRect.top - boxRect.height / 2 + charRect.height / 2
      box.scrollTop += delta
    }
  })
}

function onKeydown(e) {
  if (e.key === 'Tab') e.preventDefault()
}

function finish() {
  if (finished.value) return
  clearInterval(timer)
  finished.value = true
  elapsed.value = getActiveElapsed()

  const stats = calcStats(typedText.value, props.referenceText, elapsed.value)
  const level = resolveLevel(stats.wpm, stats.accuracy)
  const score = calcScore(stats.wpm, stats.accuracy, props.maxScore)

  result.value = {
    wpm: stats.wpm,
    accuracy: stats.accuracy,
    correct_chars: stats.correct,
    level: level.level,
    level_desc: '',
    passed: stats.wpm >= 10 && stats.accuracy >= 95,
    score,
    remark: `${level.level}（${stats.wpm} 字/分，准确率 ${stats.accuracy}%）`,
  }

  emit('complete', {
    typed_text: typedText.value,
    duration_seconds: elapsed.value,
    mode: props.mode,
    ...result.value,
  })
  emit('finished')
  emitState()
}

function reset() {
  clearInterval(timer)
  typedText.value = ''
  started.value = false
  finished.value = false
  paused.value = false
  result.value = null
  elapsed.value = 0
  timeLeft.value = props.timeLimit
  pausedDuration.value = 0
  emit('finished')
  emitState()
}

watch(() => [props.referenceText, props.mode], () => {
  if (props.disableRetry && finished.value) return
  reset()
})

onUnmounted(() => clearInterval(timer))

defineExpose({ reset, start, pause, resume, stop, started, finished, paused, result })
</script>

<style scoped>
.typing-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.typing-panel.expanded {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  gap: 12px;
}

.status-bar {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #6b7280;
  padding: 4px 0;
  flex-shrink: 0;
}

.typing-panel.expanded .status-bar {
  font-size: 15px;
}

.status-bar span { font-variant-numeric: tabular-nums; }
.paused-tag { color: #f59e0b; font-weight: 600; }

.article-box {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 20px 24px;
  font-size: 18px;
  line-height: 2;
  letter-spacing: 1px;
  min-height: 140px;
  max-height: 280px;
  overflow-x: hidden;
  overflow-y: auto;
  overflow-wrap: anywhere;
  color: #374151;
}

.typing-panel.expanded .article-box {
  flex: 1 1 0;
  min-height: 0;
  max-height: none;
  padding: 16px 20px;
  font-size: 22px;
  line-height: 1.9;
  letter-spacing: 0.5px;
}

.char.idle { color: #9ca3af; }
.char.current { color: #111827; background: #fef08a; border-radius: 2px; }
.char.ok { color: #16a34a; }
.char.err { color: #dc2626; background: #fee2e2; border-radius: 2px; }

.input-wrap {
  display: flex;
  min-width: 0;
}

.typing-panel.expanded .input-wrap {
  flex: 1 1 0;
  min-height: 0;
  position: relative;
}

.input-box {
  width: 100%;
  min-height: 120px;
  padding: 16px;
  font-size: 18px;
  line-height: 1.8;
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  resize: vertical;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
  overflow-wrap: anywhere;
}

.typing-panel.expanded .input-box {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  min-height: 0;
  padding: 16px 20px;
  font-size: 22px;
  line-height: 1.9;
  resize: none;
  overflow-y: auto;
}

@media (max-height: 800px) {
  .typing-panel.expanded .article-box,
  .typing-panel.expanded .input-box {
    font-size: 18px;
    line-height: 1.75;
    padding: 12px 16px;
  }
}

.input-box:focus { border-color: #4f46e5; }
.input-box:disabled { background: #f9fafb; color: #9ca3af; }

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.result-brief {
  font-size: 15px;
  color: #374151;
  margin-right: 8px;
}
</style>
