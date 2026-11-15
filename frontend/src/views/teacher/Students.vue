<template>
  <div class="page-container">
    <div class="page-header">
      <h1>学生动态</h1>
      <p>可新建班级、批量导入学生；导入的学生只对本教师可见。换教室时导出教师数据再导入即可同步。</p>
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
          <el-button @click="showCreateClass">新建班级</el-button>
          <el-button @click="handleExportPack">导出教师数据</el-button>
          <el-button @click="packFileRef?.click()">导入教师数据</el-button>
          <input ref="packFileRef" type="file" accept=".json,application/json" class="hidden-file" @change="handleImportPack" />
          <el-button @click="handleExport">
            <el-icon><Download /></el-icon> 导出 Excel
          </el-button>
          <el-button @click="importVisible = true">
            <el-icon><Upload /></el-icon> 批量导入
          </el-button>
          <el-button type="primary" @click="showDialog()">
            <el-icon><Plus /></el-icon> 添加学生
          </el-button>
        </div>
      </div>

      <el-table :data="filteredStudents" stripe v-loading="loading">
        <el-table-column prop="username" label="用户名" width="140" sortable />
        <el-table-column prop="name" label="姓名" width="120" sortable />
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
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="classDialogVisible" title="新建班级" width="420px">
      <el-form @submit.prevent="handleCreateClass">
        <el-form-item label="班级名称">
          <el-input v-model="newClassName" placeholder="例如：微机1班" maxlength="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="classDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingClass" @click="handleCreateClass">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑学生' : '添加学生'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="班级" prop="class_name">
          <el-select v-model="form.class_name" placeholder="选择班级" style="width: 100%" filterable allow-create>
            <el-option v-for="c in availableClasses" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="密码" :prop="editing ? '' : 'password'">
          <el-input v-model="form.password" type="password" :placeholder="editing ? '留空则不修改' : '请输入密码'" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <BatchImportDialog
      v-model="importVisible"
      title="批量导入学生"
      format-hint="支持 CSV/TXT 格式，每行一个学生。可带表头（用户名,姓名,班级,密码），密码可留空使用默认值。"
      placeholder="用户名,姓名,班级,密码
student06,张三,微机1班,123456
student07,李四,微机2班,
student08,王五,微机2班,123456"
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

const studentTemplate = `用户名,姓名,班级,密码
student06,张三,微机1班,123456
student07,李四,微机2班,
student08,王五,微机2班,123456`

const loading = ref(true)
const saving = ref(false)
const students = ref([])
const availableClasses = ref([])
const classFilter = ref('')
const search = ref('')
const dialogVisible = ref(false)
const classDialogVisible = ref(false)
const importVisible = ref(false)
const editing = ref(null)
const formRef = ref()
const packFileRef = ref()
const newClassName = ref('')
const savingClass = ref(false)
const form = ref({ username: '', name: '', class_name: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const filteredStudents = computed(() => {
  if (!search.value) return students.value
  const q = search.value.toLowerCase()
  return students.value.filter(
    (s) => s.name.toLowerCase().includes(q) || s.username.toLowerCase().includes(q)
  )
})

const onlineCount = computed(() => students.value.filter((s) => s.is_online).length)

let refreshTimer = null

function formatLastSeen(value) {
  return formatDateTime(value, '从未登录')
}

function showDialog(row = null) {
  editing.value = row
  form.value = row
    ? { username: row.username, name: row.name, class_name: row.class_name, password: '' }
    : { username: '', name: '', class_name: '', password: '' }
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editing.value) {
      const data = { name: form.value.name, class_name: form.value.class_name }
      if (form.value.password) data.password = form.value.password
      await userApi.update(editing.value.id, data)
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

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除学生「${row.name}」吗？`, '警告', { type: 'warning' })
  await userApi.delete(row.id)
  ElMessage.success('删除成功')
  await loadStudents()
}

async function loadStudents() {
  students.value = await presenceApi.students(classFilter.value)
}

async function loadClasses() {
  const res = await classApi.list()
  availableClasses.value = res.classes || []
  window.dispatchEvent(new Event('exam-classes-changed'))
}

function showCreateClass() {
  newClassName.value = ''
  classDialogVisible.value = true
}

async function handleCreateClass() {
  const name = newClassName.value.trim()
  if (!name) {
    ElMessage.warning('请输入班级名称')
    return
  }
  savingClass.value = true
  try {
    await classApi.create(name)
    ElMessage.success(`已创建班级「${name}」`)
    classDialogVisible.value = false
    await loadClasses()
  } finally {
    savingClass.value = false
  }
}

async function handleExportPack() {
  await exportApi.teacherPack()
  ElMessage.success('已导出教师数据，可在另一台教师机导入')
}

async function handleImportPack(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  const result = await importApi.teacherPackFile(file)
  await loadClasses()
  await loadStudents()
  const created = result?.student_created || 0
  const updated = result?.student_updated || 0
  const exams = result?.exam_count || 0
  const texts = result?.text_count || 0
  ElMessage.success(`导入完成：学生新增 ${created}、更新 ${updated}，考试 ${exams}，文章 ${texts}`)
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
</style>
