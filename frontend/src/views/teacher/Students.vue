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

      <el-table :data="filteredStudents" stripe v-loading="loading">
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
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDialog(row)">编辑</el-button>
            <el-button link type="warning" @click="handleResetPassword(row)">重置密码</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
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
  const summary = `学生新增 ${created}、更新 ${updated}，考试 ${exams}，文章 ${texts}`
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
</style>
