<template>
  <div class="page-container">
    <div class="page-header">
      <h1>学生动态</h1>
      <p>可管理和导入已分配班级的学生。班级分配由管理员维护。</p>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="search" placeholder="搜索学生姓名或用户名" style="width: 260px" clearable :prefix-icon="Search" />
          <ClassFilter v-model="classFilter" @update:model-value="loadStudents" />
        </div>
        <div class="toolbar-right">
          <span class="online-summary">
            <span class="online-dot"></span>
            在线 {{ onlineCount }} / {{ students.length }}
          </span>
          <el-button @click="handleExportPack">导出教师数据</el-button>
          <el-button @click="packFileRef?.click()">导入教师数据</el-button>
          <input ref="packFileRef" type="file" accept=".json,application/json" class="hidden-file" @change="handleImportPack" />
          <el-button @click="handleExport">
            <el-icon><Download /></el-icon> 导出 Excel
          </el-button>
          <el-button :disabled="!availableClasses.length" @click="importVisible = true">
            <el-icon><Upload /></el-icon> 批量导入
          </el-button>
          <el-button type="primary" :disabled="!availableClasses.length" @click="showDialog()">
            <el-icon><Plus /></el-icon> 添加学生
          </el-button>
        </div>
      </div>

      <el-table :data="filteredStudents" stripe v-loading="loading" class="student-table" @row-click="openPanel">
        <el-table-column prop="username" label="账号编号" width="140" sortable />
        <el-table-column prop="name" label="姓名（登录名）" width="140" sortable />
        <el-table-column prop="class_name" label="班级" width="140" sortable />
        <el-table-column label="在线" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_online ? 'success' : 'info'" size="small" effect="plain">
              <span class="status-dot" :class="{ online: row.is_online }"></span>
              {{ row.is_online ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账号" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近活跃" width="180">
          <template #default="{ row }">{{ formatLastSeen(row.last_seen_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openPanel(row)">数据</el-button>
            <el-button link type="primary" @click.stop="showDialog(row)">编辑</el-button>
            <el-button link type="warning" @click.stop="handleResetPassword(row)">重置密码</el-button>
            <el-button link type="danger" @click.stop="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑学生' : '添加学生'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="班级" prop="class_name">
          <el-select v-model="form.class_name" placeholder="选择班级" style="width: 100%" filterable>
            <el-option v-for="c in availableClasses" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!editing" label="初始密码">
          <el-input v-model="form.password" type="password" placeholder="留空使用 123456" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="panelVisible" :title="panelTitle" size="720px">
      <div v-loading="panelLoading">
        <template v-if="panel">
          <p class="panel-meta">
            {{ panel.student.class_name || '未分班' }} · {{ panel.student.is_online ? '在线' : '离线' }}
            · 最近活跃 {{ formatLastSeen(panel.student.last_seen_at) }}
          </p>
          <div class="panel-summary">
            <div><strong>{{ panel.summary.practice_count }}</strong><span>日常练习</span></div>
            <div><strong>{{ panel.summary.test_count }}</strong><span>测试</span></div>
            <div><strong>{{ panel.summary.exam_count }}</strong><span>考试</span></div>
            <div><strong>{{ panel.summary.avg_wpm }}</strong><span>练习均速</span></div>
            <div><strong>{{ panel.summary.avg_accuracy }}%</strong><span>练习准确率</span></div>
            <div><strong>{{ panel.summary.best_wpm }}</strong><span>最佳速度</span></div>
          </div>
          <el-tabs>
            <el-tab-pane :label="`日常练习 ${panel.practice_records.length}`">
              <el-table :data="panel.practice_records" stripe size="small" empty-text="暂无日常练习" max-height="420">
                <el-table-column prop="text_title" label="文章" min-width="140" />
                <el-table-column prop="score" label="评分" width="70" />
                <el-table-column prop="wpm" label="速度" width="90" />
                <el-table-column prop="accuracy" label="准确率" width="80" />
                <el-table-column prop="level" label="等级" width="80" />
                <el-table-column label="时间" width="160">
                  <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane :label="`测试 ${panel.test_records.length}`">
              <el-table :data="panel.test_records" stripe size="small" empty-text="暂无测试记录" max-height="420">
                <el-table-column prop="text_title" label="文章" min-width="140" />
                <el-table-column label="类型" width="100">
                  <template #default="{ row }">{{ row.source === 'class_test' ? '课堂测试' : '5分钟测试' }}</template>
                </el-table-column>
                <el-table-column prop="score" label="评分" width="70" />
                <el-table-column prop="wpm" label="速度" width="90" />
                <el-table-column prop="accuracy" label="准确率" width="80" />
                <el-table-column label="时间" width="160">
                  <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane :label="`考试 ${panel.exams.length}`">
              <el-table :data="panel.exams" stripe size="small" empty-text="暂无考试记录" max-height="280">
                <el-table-column prop="exam_title" label="考试" min-width="160" />
                <el-table-column label="状态" width="90">
                  <template #default="{ row }">{{ row.status === 'submitted' ? '已提交' : '答题中' }}</template>
                </el-table-column>
                <el-table-column label="得分" width="110">
                  <template #default="{ row }">{{ row.total_score }} / {{ row.max_score }}</template>
                </el-table-column>
                <el-table-column label="提交时间" width="160">
                  <template #default="{ row }">{{ formatDateTime(row.submit_time, '未提交') }}</template>
                </el-table-column>
              </el-table>
              <h4 v-if="panel.exam_typing_records.length" class="exam-typing-title">考试中的打字题</h4>
              <el-table v-if="panel.exam_typing_records.length" :data="panel.exam_typing_records" stripe size="small" max-height="220">
                <el-table-column prop="text_title" label="文章" min-width="140" />
                <el-table-column prop="score" label="评分" width="70" />
                <el-table-column prop="wpm" label="速度" width="90" />
                <el-table-column prop="accuracy" label="准确率" width="80" />
                <el-table-column label="时间" width="160">
                  <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </template>
      </div>
    </el-drawer>

    <BatchImportDialog
      v-model="importVisible"
      title="批量导入学生"
      format-hint="填写姓名、班级和初始密码。班级留空时使用首个已分配班级，密码可留空，用户名由系统生成。"
      :placeholder="studentTemplate"
      template-filename="学生导入模板.csv"
      :template-content="studentTemplate"
      :show-default-password="true"
      :preview-columns="[
        { prop: 'username', label: '用户名' },
        { prop: 'name', label: '姓名' },
        { prop: 'class_name', label: '班级' },
      ]"
      :on-import="handleBatchImport"
      @success="loadStudents"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Search, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { presenceApi, userApi, importApi, exportApi, classApi } from '@/api'
import BatchImportDialog from '@/components/BatchImportDialog.vue'
import ClassFilter from '@/components/ClassFilter.vue'
import { formatDateTime } from '@/utils/datetime'

const studentTemplate = `姓名,班级,密码
张三,微机1班,123456
李四,微机2班,
王五,微机2班,123456`

const loading = ref(true)
const saving = ref(false)
const students = ref([])
const availableClasses = ref([])
const classFilter = ref('')
const search = ref('')
const dialogVisible = ref(false)
const importVisible = ref(false)
const editing = ref(null)
const formRef = ref()
const packFileRef = ref()
const panelVisible = ref(false)
const panelLoading = ref(false)
const panel = ref(null)
const form = ref({ name: '', class_name: '', password: '' })

const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
}

const filteredStudents = computed(() => {
  if (!search.value) return students.value
  const q = search.value.toLowerCase()
  return students.value.filter(
    (s) => s.name.toLowerCase().includes(q) || s.username.toLowerCase().includes(q)
  )
})

const onlineCount = computed(() => students.value.filter((s) => s.is_online).length)
const panelTitle = computed(() => panel.value ? `${panel.value.student.name} 的学习数据` : '学生学习数据')

let refreshTimer = null

function formatLastSeen(value) {
  return formatDateTime(value, '从未登录')
}

function showDialog(row = null) {
  editing.value = row
  form.value = row
    ? { name: row.name, class_name: row.class_name, password: '' }
    : { name: '', class_name: availableClasses.value[0] || '', password: '' }
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editing.value) {
      await userApi.update(editing.value.id, { name: form.value.name, class_name: form.value.class_name })
      ElMessage.success('更新成功')
    } else {
      await userApi.create({ ...form.value, role: 'student' })
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    await loadClasses()
    await loadStudents()
  } finally {
    saving.value = false
  }
}

async function handleResetPassword(row) {
  const result = await ElMessageBox.prompt(
    `为「${row.name}」设置临时密码。重置后，学生需要重新登录并修改初始密码。`,
    '重置学生密码',
    {
      inputType: 'password',
      inputPlaceholder: '输入临时密码',
      inputValidator: (value) => (
        !!value?.trim() && new TextEncoder().encode(value.trim()).length <= 72
        || '请输入临时密码（最多 72 字节）'
      ),
      confirmButtonText: '确认重置',
      cancelButtonText: '取消',
    },
  ).catch(() => null)
  if (!result) return
  await userApi.update(row.id, { password: result.value })
  ElMessage.success('已重置密码')
  await loadStudents()
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除学生「${row.name}」及其考试、打字记录吗？此操作不可恢复。`, '警告', { type: 'warning' })
  await userApi.delete(row.id)
  ElMessage.success('删除成功')
  await loadStudents()
}

async function openPanel(row) {
  panelVisible.value = true
  panelLoading.value = true
  panel.value = null
  try {
    panel.value = await userApi.panel(row.id)
  } finally {
    panelLoading.value = false
  }
}

async function loadStudents() {
  students.value = await presenceApi.students(classFilter.value)
}

async function loadClasses() {
  const res = await classApi.list()
  availableClasses.value = res.classes || []
  window.dispatchEvent(new Event('exam-classes-changed'))
}

async function handleExportPack() {
  await exportApi.teacherPack()
  ElMessage.success('已导出教师数据，可在另一台教师机导入')
}

async function confirmPackOverwrite() {
  try {
    await ElMessageBox.confirm(
      '导入后，数据包中的学生、班级、考试和打字文章会写入当前教师账号。如果本机已有相同学生账号，或该教师以前的考试和文章，确认后会用数据包覆盖。数据包里没有、但仍属于该教师的旧学生、考试和文章也会被替换。',
      '确认覆盖并导入',
      { type: 'warning', confirmButtonText: '覆盖并导入', cancelButtonText: '取消' },
    )
    return true
  } catch {
    return false
  }
}

async function handleImportPack(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!await confirmPackOverwrite()) return
  const result = await importApi.teacherPackFile(file, true)
  await loadClasses()
  await loadStudents()
  const summary = `学生新增 ${result?.student_created || 0}、更新 ${result?.student_updated || 0}、移除 ${result?.student_removed || 0}，考试 ${result?.exam_count || 0}，文章 ${result?.text_count || 0}`
  if (result?.errors?.length) {
    await ElMessageBox.alert([summary, ...result.errors].join('\n'), '导入结果', {
      customClass: 'pack-import-result',
    })
  } else {
    ElMessage.success(summary)
  }
}

async function handleExport() {
  await exportApi.students(classFilter.value)
  ElMessage.success('导出成功')
}

async function handleBatchImport({ text, file, defaultPassword }) {
  if (file) {
    return importApi.studentsFile(file, defaultPassword)
  }
  return importApi.students({ text, default_password: defaultPassword })
}

onMounted(async () => {
  await loadClasses()
  await loadStudents()
  loading.value = false
  refreshTimer = setInterval(loadStudents, 10000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
:global(.pack-import-result .el-message-box__message) {
  white-space: pre-wrap;
  overflow: auto;
  max-height: 45vh;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.online-summary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #374151;
}

.online-dot,
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d1d5db;
  display: inline-block;
}

.online-dot,
.status-dot.online {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.15);
}

.hidden-file {
  display: none;
}

.student-table :deep(.el-table__row) {
  cursor: pointer;
}

.panel-meta {
  margin: 0 0 12px;
  color: #6b7280;
}

.panel-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.panel-summary div {
  background: #f8fafc;
  border-radius: 10px;
  padding: 10px 12px;
}

.panel-summary strong {
  display: block;
  font-size: 18px;
}

.panel-summary span,
.exam-typing-title {
  color: #6b7280;
  font-size: 12px;
}

.exam-typing-title {
  margin: 16px 0 8px;
  font-size: 14px;
}
</style>
