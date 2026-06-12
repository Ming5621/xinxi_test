<template>
  <div>
    <div class="page-header">
      <h1>考试大厅</h1>
      <p>选择一场考试开始答题</p>
    </div>

    <el-row :gutter="20" v-loading="loading">
      <el-col :xs="24" :sm="12" :lg="8" v-for="exam in exams" :key="exam.id">
        <div class="exam-card" :class="statusClass(exam.status)">
          <div class="exam-status">
            <el-tag :type="statusTag(exam.status)" effect="dark" size="small">
              {{ statusText(exam.status) }}
            </el-tag>
          </div>
          <h3>{{ exam.title }}</h3>
          <p class="exam-desc">{{ exam.description || '暂无描述' }}</p>
          <div class="exam-meta">
            <span><el-icon><Clock /></el-icon> {{ exam.duration_minutes }} 分钟</span>
            <span><el-icon><Document /></el-icon> {{ exam.question_count }} 题</span>
            <span><el-icon><Trophy /></el-icon> 满分 {{ exam.total_score }} 分</span>
          </div>
          <div class="exam-action">
            <el-button
              v-if="exam.status === 'published' && !submittedExams.has(exam.id)"
              type="primary"
              @click="startExam(exam)"
            >
              开始考试
            </el-button>
            <el-button
              v-else-if="submittedExams.has(exam.id)"
              type="success"
              plain
              @click="$router.push(`/student/results`)"
            >
              已提交 · 查看成绩
            </el-button>
            <el-button v-else disabled>
              {{ exam.status === 'ended' ? '考试已结束' : '未开放' }}
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-empty v-if="!loading && exams.length === 0" description="暂无可参加的考试" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { examApi } from '@/api'

const router = useRouter()
const loading = ref(true)
const exams = ref([])
const submittedExams = ref(new Set())

const statusText = { draft: '草稿', published: '进行中', ended: '已结束' }
const statusTag = { draft: 'info', published: 'success', ended: 'warning' }
const statusClass = (s) => ({ 'status-published': s === 'published', 'status-ended': s === 'ended' })

onMounted(async () => {
  const [examList, sessions] = await Promise.all([examApi.list(), examApi.mySessions()])
  exams.value = examList
  sessions.forEach((s) => {
    if (s.status === 'submitted') submittedExams.value.add(s.exam_id)
  })
  loading.value = false
})

async function startExam(exam) {
  await ElMessageBox.confirm(
    `即将开始「${exam.title}」，考试时长 ${exam.duration_minutes} 分钟，确定开始吗？`,
    '开始考试',
    { type: 'info', confirmButtonText: '开始答题', cancelButtonText: '再想想' }
  )
  await examApi.start(exam.id)
  router.push(`/student/exam/${exam.id}`)
}
</script>

<style scoped>
.exam-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
  border: 2px solid transparent;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
}

.exam-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: #e5e7eb;
}

.exam-card.status-published::before { background: linear-gradient(90deg, #10b981, #34d399); }
.exam-card.status-ended::before { background: linear-gradient(90deg, #f59e0b, #fbbf24); }

.exam-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.1);
}

.exam-status { margin-bottom: 12px; }

.exam-card h3 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #111827;
}

.exam-desc {
  color: #6b7280;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 16px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 44px;
}

.exam-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 20px;
  font-size: 13px;
  color: #9ca3af;
}

.exam-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.exam-action {
  border-top: 1px solid #f3f4f6;
  padding-top: 16px;
}
</style>
