<template>
  <div class="page-container">
    <div class="page-header">
      <h1>考试管理</h1>
      <p>创建和管理考试内容</p>
    </div>

    <div class="content-card">
      <div style="display: flex; justify-content: space-between; margin-bottom: 16px">
        <el-radio-group v-model="filter" size="small">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="draft">草稿</el-radio-button>
          <el-radio-button value="published">进行中</el-radio-button>
          <el-radio-button value="ended">已结束</el-radio-button>
        </el-radio-group>
        <el-button type="primary" @click="$router.push('/teacher/exams/create')">
          <el-icon><Plus /></el-icon> 创建考试
        </el-button>
      </div>

      <el-table :data="filteredExams" stripe v-loading="loading">
        <el-table-column prop="title" label="考试名称" min-width="200" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ statusText[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="question_count" label="题数" width="80" />
        <el-table-column label="满分" width="80">
          <template #default="{ row }">{{ row.total_score }}</template>
        </el-table-column>
        <el-table-column prop="duration_minutes" label="时长(分)" width="100" />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/teacher/exams/${row.id}/edit`)">编辑</el-button>
            <el-button v-if="row.status === 'draft'" link type="success" @click="handlePublish(row)">发布</el-button>
            <el-button v-if="row.status === 'published'" link type="warning" @click="handleEnd(row)">结束</el-button>
            <el-button link @click="$router.push(`/teacher/exams/${row.id}/results`)">成绩</el-button>
            <el-button link @click="$router.push(`/teacher/exams/${row.id}/stats`)">统计</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { examApi } from '@/api'

const loading = ref(true)
const exams = ref([])
const filter = ref('all')

const statusText = { draft: '草稿', published: '进行中', ended: '已结束' }
const statusTag = { draft: 'info', published: 'success', ended: 'warning' }

const filteredExams = computed(() => {
  if (filter.value === 'all') return exams.value
  return exams.value.filter((e) => e.status === filter.value)
})

function formatDate(d) {
  return new Date(d).toLocaleString('zh-CN')
}

async function handlePublish(row) {
  await ElMessageBox.confirm(`确定发布考试「${row.title}」吗？发布后学生可以开始答题。`, '发布考试')
  await examApi.publish(row.id)
  ElMessage.success('发布成功')
  exams.value = await examApi.list()
}

async function handleEnd(row) {
  await ElMessageBox.confirm(`确定结束考试「${row.title}」吗？结束后将自动批改未提交的答卷。`, '结束考试', { type: 'warning' })
  await examApi.end(row.id)
  ElMessage.success('考试已结束')
  exams.value = await examApi.list()
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除考试「${row.title}」吗？此操作不可恢复。`, '警告', { type: 'warning' })
  await examApi.delete(row.id)
  ElMessage.success('删除成功')
  exams.value = await examApi.list()
}

onMounted(async () => {
  exams.value = await examApi.list()
  loading.value = false
})
</script>
