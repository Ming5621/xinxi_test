<template>
  <div>
    <div class="page-header">
      <h1>我的成绩</h1>
      <p>查看您的考试记录和成绩详情</p>
    </div>

    <div class="content-card" v-loading="loading">
      <el-table :data="sessions" stripe style="width: 100%">
        <el-table-column prop="exam_title" label="考试名称" min-width="200" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'submitted' ? 'success' : 'warning'" size="small">
              {{ row.status === 'submitted' ? '已提交' : '答题中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="得分" width="140">
          <template #default="{ row }">
            <span v-if="row.status === 'submitted'" class="score-text">
              {{ row.total_score }} / {{ row.max_score }}
            </span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="是否及格" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'submitted'" :type="row.is_passed ? 'success' : 'danger'" size="small">
              {{ row.is_passed ? '及格' : '不及格' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="180">
          <template #default="{ row }">
            {{ row.submit_time ? formatDate(row.submit_time) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'submitted'"
              type="primary"
              link
              @click="$router.push(`/student/results/${row.id}`)"
            >
              查看详情
            </el-button>
            <el-button v-else type="warning" link @click="$router.push(`/student/exam/${row.exam_id}`)">
              继续答题
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && sessions.length === 0" description="暂无考试记录" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { examApi } from '@/api'

const loading = ref(true)
const sessions = ref([])

function formatDate(d) {
  return new Date(d).toLocaleString('zh-CN')
}

onMounted(async () => {
  sessions.value = await examApi.mySessions()
  loading.value = false
})
</script>

<style scoped>
.score-text {
  font-weight: 600;
  color: #4f46e5;
  font-size: 15px;
}

.text-muted {
  color: #9ca3af;
}
</style>
