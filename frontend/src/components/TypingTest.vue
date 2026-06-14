<template>
  <div class="typing-panel">
    <!-- 简洁状态栏 -->
    <div class="status-bar" v-if="started">
      <span>{{ liveWpm }} 字/分</span>
      <span>准确率 {{ liveAccuracy }}%</span>
      <span v-if="mode === 'test'">剩余 {{ formatTime(timeLeft) }}</span>
      <span v-else>用时 {{ formatTime(elapsed) }}</span>
      <span v-if="paused" class="paused-tag">已暂停</span>
    </div>

    <!-- 全文展示区（白底） -->
    <div class="article-box">
      <span
        v-for="(char, i) in referenceChars"
        :key="i"
        class="char"
        :class="charClass(i)"
      >{{ char === ' ' ? '\u00A0' : char }}</span>
    </div>

    <!-- 打字输入区 -->
    <textarea
      ref="inputRef"
      v-model="typedText"
      class="input-box"
      :disabled="!started || finished || paused || (mode === 'test' && locked)"
      :placeholder="started ? '请开始输入...' : '点击开始后在此输入'"
      @input="onInput"
      @keydown="onKeydown"
    />

    <!-- 操作按钮 -->
    <div class="actions">
      <template v-if="!started && !finished">
        <el-button type="primary" size="large" @click="start">开始</el-button>
      </template>

      <template v-if="mode === 'free' && started && !finished">
        <el-button v-if="!paused" @click="pause">暂停</el-button>
        <el-button v-else type="primary" @click="resume">继续</el-button>
        <el-button type="danger" @click="stop">停止</el-button>
      </template>

      <template v-if="finished">
        <div class="result-brief">
          <strong>{{ result.level }}</strong> · {{ result.wpm }} 字/分 · 准确率 {{ result.accuracy }}%
        </div>
        <el-button @click="reset">再来一次</el-button>
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
})

const emit = defineEmits(['complete', 'started', 'finished'])

const typedText = ref('')
const started = ref(false)
const finished = ref(false)
const paused = ref(false)
const locked = ref(false)
const timeLeft = ref(props.timeLimit)
const elapsed = ref(0)
const startTime = ref(0)
const pausedDuration = ref(0)
const pauseStart = ref(0)
const result = ref(null)
const inputRef = ref()
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

function getActiveElapsed() {
  if (!started.value) return 0
  const now = paused.value ? pauseStart.value : Date.now()
  return (now - startTime.value - pausedDuration.value) / 1000
}

function calcStats(typed, reference, seconds) {
  let correct = 0
  for (let i = 0; i < typed.length; i++) {
    if (typed[i] === reference[i]) correct++
  }
  const acc = typed.length ? Math.round((correct / typed.length) * 100) : 100
  const mins = seconds > 1 ? seconds / 60 : 0
  const wpm = mins > 0 ? Math.round((correct / mins) * 10) / 10 : 0
  return { correct, accuracy: acc, wpm }
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
    try {
      await ElMessageBox.confirm(
        '5分钟测试开始后无法暂停或停止，时间到自动结束。确定开始吗？',
        '开始测试',
        { type: 'warning', confirmButtonText: '开始', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }

  started.value = true
  finished.value = false
  paused.value = false
  locked.value = props.mode === 'test'
  result.value = null
  typedText.value = ''
  timeLeft.value = props.timeLimit
  startTime.value = Date.now()
  pausedDuration.value = 0
  timer = setInterval(tick, 200)
  emit('started')
  nextTick(() => inputRef.value?.focus())
}

function pause() {
  if (props.mode !== 'free' || !started.value || finished.value) return
  paused.value = true
  pauseStart.value = Date.now()
}

function resume() {
  if (!paused.value) return
  pausedDuration.value += Date.now() - pauseStart.value
  paused.value = false
  nextTick(() => inputRef.value?.focus())
}

function stop() {
  if (props.mode !== 'free') return
  finish()
}

function onInput() {
  if (props.mode === 'free' && typedText.value.length >= props.referenceText.length) {
    finish()
  }
}

function onKeydown(e) {
  if (e.key === 'Tab') e.preventDefault()
}

function finish() {
  if (finished.value) return
  clearInterval(timer)
  finished.value = true
  locked.value = false
  elapsed.value = getActiveElapsed()

  const stats = calcStats(typedText.value, props.referenceText, elapsed.value)
  const level = standards.find((s) => stats.wpm >= s.min_wpm) || standards[standards.length - 1]

  result.value = {
    wpm: stats.wpm,
    accuracy: stats.accuracy,
    correct_chars: stats.correct,
    level: level.level,
    level_desc: '',
    passed: stats.wpm >= 10 && stats.accuracy >= 95,
  }

  emit('complete', {
    typed_text: typedText.value,
    duration_seconds: elapsed.value,
    mode: props.mode,
    ...result.value,
  })
  emit('finished')
}

function reset() {
  clearInterval(timer)
  typedText.value = ''
  started.value = false
  finished.value = false
  paused.value = false
  locked.value = false
  result.value = null
  elapsed.value = 0
  timeLeft.value = props.timeLimit
  pausedDuration.value = 0
  emit('finished')
}

watch(() => [props.referenceText, props.mode], reset)

onUnmounted(() => clearInterval(timer))

defineExpose({ reset })
</script>

<style scoped>
.typing-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.status-bar {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #6b7280;
  padding: 8px 0;
}

.status-bar span { font-variant-numeric: tabular-nums; }
.paused-tag { color: #f59e0b; font-weight: 600; }

.article-box {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 20px 24px;
  font-size: 18px;
  line-height: 2;
  letter-spacing: 1px;
  min-height: 120px;
  max-height: 280px;
  overflow-y: auto;
  color: #374151;
}

.char.idle { color: #9ca3af; }
.char.current { color: #111827; background: #fef08a; border-radius: 2px; }
.char.ok { color: #16a34a; }
.char.err { color: #dc2626; background: #fee2e2; border-radius: 2px; }

.input-box {
  width: 100%;
  min-height: 100px;
  padding: 16px;
  font-size: 18px;
  line-height: 1.8;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  resize: vertical;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  outline: none;
  transition: border-color 0.2s;
}

.input-box:focus { border-color: #4f46e5; }
.input-box:disabled { background: #f9fafb; color: #9ca3af; }

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.result-brief {
  font-size: 15px;
  color: #374151;
  margin-right: 8px;
}
</style>
