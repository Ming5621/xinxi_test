<template>
  <div class="page-container">
    <div class="page-header">
      <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
      <div class="header-row">
        <h1>考试成绩</h1>
        <div class="header-actions">
          <ClassFilter v-model="classFilter" @update:model-value="loadSessions" />
          <el-button @click="handleExport"><el-icon><Download /></el-icon> 导出 Excel</el-button>
        </div>
      </div>
    </div>

    <div class="content-card" v-loading="loading">
      <el-table :data="sessions" stripe>
        <el-table-column prop="student_name" label="姓名" width="120" />
        <el-table-column prop="class_name" label="班级" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'submitted' ? 'success' : 'warning'" size="small">
              {{ row.status === 'submitted' ? '已提交' : '答题中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="得分" width="140" sortable :sort-method="sortByScore">
          <template #default="{ row }">
            <span v-if="row.status === 'submitted'" class="score">{{ row.total_score }} / {{ row.max_score }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="及格" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'submitted'" :type="row.is_passed ? 'success' : 'danger'" size="small">
              {{ row.is_passed ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="180">
          <template #default="{ row }">{{ formatDate(row.start_time) }}</template>
        </el-table-column>
        <el-table-column label="提交时间" width="180">
          <template #default="{ row }">{{ row.submit_time ? formatDate(row.submit_time) : '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'submitted'" link type="primary" @click="showDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && sessions.length === 0" description="暂无考试记录" />
    </div>

    <el-dialog v-model="detailVisible" title="答题详情" width="700px">
      <template v-if="detail">
        <div class="detail-header">
          <span>{{ detail.student_name }} · {{ detail.class_name }}</span>
          <el-tag :type="detail.is_passed ? 'success' : 'danger'">
            {{ detail.total_score }} / {{ detail.max_score }} 分
          </el-tag>
        </div>
        <div v-for="(ans, i) in detail.answers" :key="ans.question_id" class="detail-item">
          <div class="detail-q">
            <span>第{{ i + 1 }}题</span>
            <el-tag :type="ans.is_correct ? 'success' : 'danger'" size="small">
              {{ ans.is_correct ? '✓' : '✗' }} {{ ans.score }}分
            </el-tag>
          </div>
          <p>{{ ans.question_content }}</p>
          <p class="detail-a">
            学生答案: <strong>{{ ans.student_answer }}</strong>
            <span v-if="!ans.is_correct"> · 正确答案: <strong>{{ ans.correct_answer }}</strong></span>
          </p>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { examApi, exportApi } from '@/api'
import ClassFilter from '@/components/ClassFilter.vue'

const route = useRoute()
const loading = ref(true)
const sessions = ref([])
const classFilter = ref('')
const detailVisible = ref(false)
const detail = ref(null)

function formatDate(d) {
  return new Date(d).toLocaleString('zh-CN')
}

function sortByScore(a, b) {
  return (a.total_score || 0) - (b.total_score || 0)
}

async function showDetail(row) {
  detail.value = await examApi.sessionDetail(row.id)
  detailVisible.value = true
}

async function loadSessions() {
  loading.value = true
  try {
    sessions.value = await examApi.examSessions(Number(route.params.id), classFilter.value)
  } finally {
    loading.value = false
  }
}

async function handleExport() {
  await exportApi.examResults(Number(route.params.id), classFilter.value)
  ElMessage.success('导出成功')
}

onMounted(loadSessions)
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.score {
  font-weight: 600;
  color: #4f46e5;
}

.muted {
  color: #9ca3af;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f3f4f6;
  font-weight: 500;
}

.detail-item {
  padding: 12px 0;
  border-bottom: 1px solid #f9fafb;
}

.detail-q {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  font-weight: 500;
  color: #4f46e5;
}

.detail-a {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}
</style>
