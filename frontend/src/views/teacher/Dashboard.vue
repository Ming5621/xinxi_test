<template>
  <div class="page-container">
    <div class="page-header">
      <h1>控制台</h1>
      <p>考试系统数据概览</p>
    </div>

    <el-row :gutter="20" v-loading="loading">
      <el-col :xs="12" :sm="6" v-for="item in statCards" :key="item.label">
        <div class="stat-card">
          <div class="stat-icon" :style="{ background: item.bg }">
            <el-icon :style="{ color: item.color }"><component :is="item.icon" /></el-icon>
          </div>
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 24px">
      <el-col :span="16">
        <div class="content-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
            <h3>最近考试</h3>
            <el-button type="primary" @click="$router.push('/teacher/exams/create')">
              <el-icon><Plus /></el-icon> 创建考试
            </el-button>
          </div>
          <el-table :data="exams" stripe>
            <el-table-column prop="title" label="考试名称" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusTag(row.status)" size="small">{{ statusText[row.status] }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="question_count" label="题数" width="80" />
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button link type="primary" @click="$router.push(`/teacher/exams/${row.id}/stats`)">统计</el-button>
                <el-button link @click="$router.push(`/teacher/exams/${row.id}/results`)">成绩</el-button>
                <el-button link @click="$router.push(`/teacher/exams/${row.id}/edit`)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="content-card">
          <h3 style="margin-bottom: 16px">快捷操作</h3>
          <div class="quick-actions">
            <el-button class="action-btn" @click="$router.push('/teacher/students')">
              <el-icon :size="24"><User /></el-icon>
              <span>管理学生</span>
            </el-button>
            <el-button class="action-btn" @click="$router.push('/teacher/exams')">
              <el-icon :size="24"><Document /></el-icon>
              <span>考试列表</span>
            </el-button>
            <el-button class="action-btn" @click="$router.push('/teacher/exams/create')">
              <el-icon :size="24"><EditPen /></el-icon>
              <span>创建考试</span>
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { statsApi, examApi } from '@/api'

const loading = ref(true)
const stats = ref({})
const exams = ref([])

const statusText = { draft: '草稿', published: '进行中', ended: '已结束' }
const statusTag = { draft: 'info', published: 'success', ended: 'warning' }

const statCards = computed(() => [
  { label: '学生总数', value: stats.value.total_students || 0, icon: 'User', bg: '#eef2ff', color: '#4f46e5' },
  { label: '考试总数', value: stats.value.total_exams || 0, icon: 'Document', bg: '#ecfdf5', color: '#10b981' },
  { label: '进行中', value: stats.value.active_exams || 0, icon: 'Timer', bg: '#fff7ed', color: '#f59e0b' },
  { label: '已完成', value: stats.value.completed_sessions || 0, icon: 'CircleCheck', bg: '#fdf2f8', color: '#ec4899' },
])

onMounted(async () => {
  const [s, e] = await Promise.all([statsApi.dashboard(), examApi.list()])
  stats.value = s
  exams.value = e.slice(0, 5)
  loading.value = false
})
</script>

<style scoped>
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-btn {
  width: 100%;
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: flex-start;
  padding: 0 20px;
  font-size: 15px;
}
</style>
