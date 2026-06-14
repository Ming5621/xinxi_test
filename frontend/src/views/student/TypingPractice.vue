<template>
  <div>
    <div class="page-header">
      <h1>打字练习</h1>
      <p>参考初中信息技术标准，提升中文打字速度与准确率</p>
    </div>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="8">
        <div class="content-card sidebar-card">
          <h3>选择练习素材</h3>
          <el-radio-group v-model="difficulty" size="small" style="margin-bottom: 12px" @change="loadTexts">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="beginner">入门</el-radio-button>
            <el-radio-button value="basic">基础</el-radio-button>
            <el-radio-button value="standard">达标</el-radio-button>
            <el-radio-button value="advanced">进阶</el-radio-button>
          </el-radio-group>

          <div class="text-list" v-loading="loading">
            <div
              v-for="item in texts"
              :key="item.id"
              class="text-item"
              :class="{ active: selected?.id === item.id }"
              @click="selectText(item)"
            >
              <div class="text-title">{{ item.title }}</div>
              <div class="text-meta">
                <el-tag size="small" :type="diffTag(item.difficulty)">{{ diffLabel(item.difficulty) }}</el-tag>
                <span>{{ item.char_count }} 字 · {{ item.time_limit }}秒</span>
              </div>
            </div>
          </div>
        </div>

        <div class="content-card" style="margin-top: 16px">
          <h3>我的最近记录</h3>
          <div v-for="r in records" :key="r.id" class="record-item">
            <div class="record-title">{{ r.text_title }}</div>
            <div class="record-stats">
              <el-tag size="small" :color="levelColor(r.level)" effect="dark">{{ r.level }}</el-tag>
              <span>{{ r.wpm }} 字/分 · {{ r.accuracy }}%</span>
            </div>
          </div>
          <el-empty v-if="records.length === 0" description="暂无记录" :image-size="60" />
        </div>
      </el-col>

      <el-col :xs="24" :lg="16">
        <div class="content-card" v-if="selected">
          <div class="practice-header">
            <h3>{{ selected.title }}</h3>
            <el-tag>{{ diffLabel(selected.difficulty) }}</el-tag>
          </div>
          <TypingTest
            :reference-text="selected.content"
            :time-limit="selected.time_limit"
            @complete="handleComplete"
          />
        </div>
        <div class="content-card empty-practice" v-else>
          <el-icon :size="64" color="#d1d5db"><EditPen /></el-icon>
          <p>请从左侧选择一篇练习素材开始打字</p>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { typingApi } from '@/api'
import TypingTest from '@/components/TypingTest.vue'

const loading = ref(true)
const texts = ref([])
const records = ref([])
const selected = ref(null)
const difficulty = ref('')

const diffMap = {
  beginner: { label: '入门', tag: 'info' },
  basic: { label: '基础', tag: '' },
  standard: { label: '达标', tag: 'success' },
  advanced: { label: '进阶', tag: 'warning' },
}

const levelColors = {
  '卓越': '#7c3aed', '优秀': '#10b981', '良好': '#3b82f6',
  '达标': '#f59e0b', '未达标': '#ef4444',
}

function diffLabel(d) { return diffMap[d]?.label || d }
function diffTag(d) { return diffMap[d]?.tag || '' }
function levelColor(l) { return levelColors[l] || '#6b7280' }

async function loadTexts() {
  loading.value = true
  texts.value = await typingApi.texts(difficulty.value || undefined)
  loading.value = false
}

function selectText(item) {
  selected.value = item
}

async function handleComplete(data) {
  await typingApi.submit({
    text_id: selected.value.id,
    reference_text: selected.value.content,
    typed_text: data.typed_text,
    duration_seconds: data.duration_seconds,
    source: 'practice',
  })
  ElMessage.success(`练习完成！${data.level} — ${data.wpm} 字/分钟`)
  records.value = await typingApi.myRecords()
}

onMounted(async () => {
  await loadTexts()
  records.value = await typingApi.myRecords()
  if (texts.value.length) selected.value = texts.value[0]
})
</script>

<style scoped>
.sidebar-card h3 { margin-bottom: 12px; }

.text-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.text-item {
  padding: 12px;
  border: 2px solid #f3f4f6;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.text-item:hover { border-color: #c7d2fe; background: #f5f3ff; }
.text-item.active { border-color: #4f46e5; background: #eef2ff; }

.text-title { font-weight: 500; margin-bottom: 4px; }
.text-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #9ca3af; }

.record-item {
  padding: 10px 0;
  border-bottom: 1px solid #f3f4f6;
}

.record-title { font-size: 14px; margin-bottom: 4px; }
.record-stats { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #6b7280; }

.practice-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.empty-practice {
  text-align: center;
  padding: 80px 20px;
  color: #9ca3af;
}

.empty-practice p { margin-top: 16px; font-size: 16px; }
</style>
