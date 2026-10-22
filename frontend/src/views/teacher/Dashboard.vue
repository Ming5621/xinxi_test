<template>
  <div class="page-container">
    <div class="page-header">
      <h1>控制台</h1>
      <p>查看已登录学生，并发布考试 / 发起打字测试</p>
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
      <el-col :xs="24" :lg="14">
        <div class="content-card">
          <div class="card-head">
            <div>
              <h3>当前在线学生</h3>
              <p class="card-sub">姓名登录后会出现在此列表（约每 10 秒刷新）</p>
            </div>
            <el-tag type="success" effect="dark">在线 {{ onlineStudents.length }}</el-tag>
          </div>

          <el-table :data="onlineStudents" stripe empty-text="暂无学生在线，请学生在登录页输入姓名进入">
            <el-table-column prop="name" label="姓名" min-width="120" />
            <el-table-column prop="class_name" label="班级" width="120" />
            <el-table-column label="状态" width="100">
              <template #default>
                <el-tag type="success" size="small">在线</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="最近心跳" width="180">
              <template #default="{ row }">{{ formatTime(row.last_seen_at) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
        <div class="content-card">
          <h3 style="margin-bottom: 8px">发任务</h3>
          <p class="card-sub" style="margin-bottom: 16px">学生在线后，可发布考试或发起课堂打字测试</p>
          <div class="quick-actions">
            <el-button class="action-btn" type="primary" @click="$router.push('/teacher/exams')">
              <el-icon :size="22"><Document /></el-icon>
              <div class="action-text">
                <strong>考试管理 / 发布考试</strong>
                <span>创建题目后点击「发布」，在线学生即可作答</span>
              </div>
            </el-button>
            <el-button class="action-btn" @click="$router.push('/teacher/exams/create')">
              <el-icon :size="22"><EditPen /></el-icon>
              <div class="action-text">
                <strong>创建新考试</strong>
                <span>选择题 / 判断题 / 打字题</span>
              </div>
            </el-button>
            <el-button class="action-btn" @click="$router.push('/teacher/typing/class-test')">
              <el-icon :size="22"><Timer /></el-icon>
              <div class="action-text">
                <strong>发起课堂打字测试</strong>
                <span>5 分钟测试，学生端自动提示参加</span>
              </div>
            </el-button>
            <el-button class="action-btn" @click="$router.push('/teacher/students')">
              <el-icon :size="22"><User /></el-icon>
              <div class="action-text">
                <strong>学生动态</strong>
                <span>查看全部已登录学生（含离线）</span>
              </div>
            </el-button>
          </div>
        </div>

        <div class="content-card" style="margin-top: 20px">
          <div class="card-head">
            <h3>最近考试</h3>
            <el-button link type="primary" @click="$router.push('/teacher/exams')">全部</el-button>
          </div>
          <el-table :data="exams" stripe size="small" empty-text="暂无考试">
            <el-table-column prop="title" label="考试名称" min-width="140" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusTag[row.status]" size="small">{{ statusText[row.status] }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'draft'"
                  link
                  type="success"
                  @click="publishExam(row)"
                >发布</el-button>
                <el-button
                  v-else
                  link
                  type="primary"
                  @click="$router.push(`/teacher/exams/${row.id}/results`)"
                >成绩</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { statsApi, examApi, presenceApi } from '@/api'

const loading = ref(true)
const stats = ref({})
const exams = ref([])
const presence = ref([])
let refreshTimer = null

const statusText = { draft: '草稿', published: '进行中', ended: '已结束' }
const statusTag = { draft: 'info', published: 'success', ended: 'warning' }

const onlineStudents = computed(() => presence.value.filter((s) => s.is_online))

const statCards = computed(() => [
  { label: '已登录学生', value: stats.value.total_students || 0, icon: 'User', bg: '#eef2ff', color: '#4f46e5' },
  { label: '当前在线', value: onlineStudents.value.length, icon: 'Connection', bg: '#ecfdf5', color: '#10b981' },
  { label: '进行中考试', value: stats.value.active_exams || 0, icon: 'Timer', bg: '#fff7ed', color: '#f59e0b' },
  { label: '考试总数', value: stats.value.total_exams || 0, icon: 'Document', bg: '#f0f9ff', color: '#0ea5e9' },
])

function formatTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN')
}

async function publishExam(row) {
  await ElMessageBox.confirm(`确定发布「${row.title}」吗？在线学生将可开始答题。`, '发布考试')
  await examApi.publish(row.id)
  ElMessage.success('已发布')
  await refreshDashboard()
}

async function refreshDashboard() {
  const [s, e, p] = await Promise.all([
    statsApi.dashboard(),
    examApi.list(),
    presenceApi.students(),
  ])
  stats.value = s
  exams.value = e.slice(0, 6)
  presence.value = p
  loading.value = false
}

onMounted(async () => {
  await refreshDashboard()
  refreshTimer = setInterval(refreshDashboard, 10000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 12px;
}

.card-head h3 {
  margin: 0;
}

.card-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: #9ca3af;
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-btn {
  width: 100%;
  height: auto;
  min-height: 72px;
  display: flex;
  align-items: center;
  gap: 14px;
  justify-content: flex-start;
  padding: 14px 18px;
  white-space: normal;
}

.action-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  text-align: left;
}

.action-text strong {
  font-size: 15px;
}

.action-text span {
  font-size: 12px;
  color: #6b7280;
  font-weight: 400;
}
</style>
