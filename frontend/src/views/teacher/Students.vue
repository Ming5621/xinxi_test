<template>
  <div class="page-container">
    <div class="page-header">
      <h1>学生管理</h1>
      <p>管理学生账号信息</p>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索学生姓名或用户名" style="width: 300px" clearable :prefix-icon="Search" />
        <div class="toolbar-right">
          <span class="online-summary">
            <span class="online-dot"></span>
            在线 {{ onlineCount }} / {{ students.length }}
          </span>
          <el-button @click="importVisible = true">
            <el-icon><Upload /></el-icon> 批量导入
          </el-button>
          <el-button type="primary" @click="showDialog()">
            <el-icon><Plus /></el-icon> 添加学生
          </el-button>
        </div>
      </div>

      <el-table :data="filteredStudents" stripe v-loading="loading">
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="class_name" label="班级" width="140" />
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

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑学生' : '添加学生'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="班级" prop="class_name">
          <el-input v-model="form.class_name" />
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
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { presenceApi, userApi, importApi } from '@/api'
import BatchImportDialog from '@/components/BatchImportDialog.vue'

const studentTemplate = `用户名,姓名,班级,密码
student06,张三,微机1班,123456
student07,李四,微机2班,
student08,王五,微机2班,123456`

const loading = ref(true)
const saving = ref(false)
const students = ref([])
const search = ref('')
const dialogVisible = ref(false)
const importVisible = ref(false)
const editing = ref(null)
const formRef = ref()
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
  if (!value) return '从未登录'
  return new Date(value).toLocaleString('zh-CN')
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
  students.value = await presenceApi.students()
}

async function handleBatchImport({ text, file, defaultPassword }) {
  if (file) {
    return importApi.studentsFile(file, defaultPassword)
  }
  return importApi.students({ text, default_password: defaultPassword })
}

onMounted(async () => {
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

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
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
</style>
