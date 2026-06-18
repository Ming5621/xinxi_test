<template>
  <div class="page-container">
    <div class="page-header">
      <h1>课堂 5 分钟打字测试</h1>
      <p>选择班级和文章发起测试，学生端将自动收到测试通知</p>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <el-button type="primary" @click="showCreate = true">
          <el-icon><Plus /></el-icon> 发起新测试
        </el-button>
        <el-button @click="loadSessions"><el-icon><Refresh /></el-icon> 刷新</el-button>
      </div>

      <el-table :data="sessions" stripe v-loading="loading">
        <el-table-column prop="title" label="测试名称" min-width="180" />
        <el-table-column prop="class_name" label="班级" width="120" />
        <el-table-column prop="text_title" label="文章" min-width="140" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提交进度" width="120">
          <template #default="{ row }">{{ row.submitted_count }} / {{ row.participant_count }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" link type="success" @click="handleStart(row)">开始测试</el-button>
            <el-button v-if="row.status === 'active'" link type="warning" @click="handleEnd(row)">结束测试</el-button>
            <el-button link type="primary" @click="showResults(row)">查看成绩</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="showCreate" title="发起课堂打字测试" width="520px">
      <el-form ref="createRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="班级" prop="class_name">
          <ClassFilter v-model="createForm.class_name" placeholder="选择班级" :clearable="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="练习文章" prop="text_id">
          <el-select v-model="createForm.text_id" placeholder="选择文章" style="width: 100%">
            <el-option v-for="t in texts" :key="t.id" :label="`${t.title}（${t.content.length}字）`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="测试名称">
          <el-input v-model="createForm.title" placeholder="可选，默认自动生成" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resultVisible" :title="`测试成绩 - ${currentSession?.title || ''}`" width="800px">
      <div v-if="sessionDetail" class="result-summary">
        <el-tag>{{ sessionDetail.class_name }}</el-tag>
        <span>提交 {{ sessionDetail.submitted_count }} / {{ sessionDetail.participant_count }} 人</span>
        <el-tag :type="statusType(sessionDetail.status)">{{ statusLabel(sessionDetail.status) }}</el-tag>
      </div>
      <el-table :data="sessionDetail?.records || []" stripe max-height="420" v-loading="detailLoading">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="student_name" label="姓名" width="100" />
        <el-table-column prop="class_name" label="班级" width="110" />
        <el-table-column label="评分" width="80">
          <template #default="{ row }"><strong>{{ row.score }}</strong></template>
        </el-table-column>
        <el-table-column label="速度" width="110">
          <template #default="{ row }">{{ row.wpm }} 字/分</template>
        </el-table-column>
        <el-table-column label="准确率" width="90">
          <template #default="{ row }">{{ row.accuracy }}%</template>
        </el-table-column>
        <el-table-column label="等级" width="90">
          <template #default="{ row }">
            <el-tag size="small" effect="dark">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!detailLoading && !sessionDetail?.records?.length" description="暂无提交记录" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { typingApi } from '@/api'
import ClassFilter from '@/components/ClassFilter.vue'

const loading = ref(true)
const creating = ref(false)
const detailLoading = ref(false)
const sessions = ref([])
const texts = ref([])
const showCreate = ref(false)
const resultVisible = ref(false)
const currentSession = ref(null)
const sessionDetail = ref(null)
const createRef = ref()
const createForm = ref({ class_name: '', text_id: null, title: '' })

const createRules = {
  class_name: [{ required: true, message: '请选择班级', trigger: 'change' }],
  text_id: [{ required: true, message: '请选择文章', trigger: 'change' }],
}

function statusLabel(s) {
  return { pending: '待开始', active: '进行中', ended: '已结束' }[s] || s
}

function statusType(s) {
  return { pending: 'info', active: 'success', ended: '' }[s] || 'info'
}

function formatDate(v) {
  return v ? new Date(v).toLocaleString('zh-CN') : '—'
}

async function loadSessions() {
  loading.value = true
  try {
    sessions.value = await typingApi.sessions()
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  await createRef.value.validate()
  creating.value = true
  try {
    await typingApi.createSession({
      class_name: createForm.value.class_name,
      text_id: createForm.value.text_id,
      title: createForm.value.title,
      duration_seconds: 300,
    })
    ElMessage.success('测试已创建，请点击「开始测试」')
    showCreate.value = false
    createForm.value = { class_name: '', text_id: null, title: '' }
    await loadSessions()
  } finally {
    creating.value = false
  }
}

async function handleStart(row) {
  await ElMessageBox.confirm(`确定开始「${row.title}」吗？开始后学生即可参加。`, '开始测试', { type: 'info' })
  await typingApi.startSession(row.id)
  ElMessage.success('测试已开始')
  await loadSessions()
}

async function handleEnd(row) {
  await ElMessageBox.confirm('确定结束本次测试吗？结束后学生将无法继续提交。', '结束测试', { type: 'warning' })
  await typingApi.endSession(row.id)
  ElMessage.success('测试已结束')
  await loadSessions()
}

async function showResults(row) {
  currentSession.value = row
  resultVisible.value = true
  detailLoading.value = true
  try {
    sessionDetail.value = await typingApi.sessionDetail(row.id)
  } finally {
    detailLoading.value = false
  }
}

onMounted(async () => {
  texts.value = await typingApi.texts()
  await loadSessions()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.result-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #374151;
}
</style>
