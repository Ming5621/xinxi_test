<template>
  <div class="page-container">
    <div class="page-header">
      <h1>账号管理</h1>
      <p>管理管理员、教师和学生账号。学生使用姓名登录；教师和管理员使用用户名与密码。</p>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="search"
            placeholder="搜索姓名、用户名或班级"
            style="width: 260px"
            clearable
            :prefix-icon="Search"
          />
          <el-radio-group v-model="roleFilter">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="admin">管理员</el-radio-button>
            <el-radio-button value="teacher">教师</el-radio-button>
            <el-radio-button value="student">学生</el-radio-button>
          </el-radio-group>
        </div>
        <el-button type="primary" @click="showDialog()">
          <el-icon><Plus /></el-icon> 添加账号
        </el-button>
      </div>
      <p class="summary">
        共 {{ users.length }} 个账号（管理员 {{ counts.admin }}，教师 {{ counts.teacher }}，学生 {{ counts.student }}）
      </p>

      <el-table :data="filteredUsers" stripe v-loading="loading">
        <el-table-column prop="username" label="用户名" min-width="150" />
        <el-table-column label="姓名" width="140">
          <template #default="{ row }">
            {{ row.name }}
            <el-tag v-if="row.id === auth.user?.id" size="small" type="info" style="margin-left: 4px">当前</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small">{{ roleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="班级" min-width="220">
          <template #default="{ row }">
            <template v-if="row.role === 'teacher'">
              <el-tag v-for="c in row.assigned_classes || []" :key="c" size="small" style="margin: 2px">{{ c }}</el-tag>
              <span v-if="!row.assigned_classes?.length" class="muted">未分配班级</span>
            </template>
            <template v-else-if="row.role === 'student'">{{ row.class_name || '未分班' }}</template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDialog(row)">编辑</el-button>
            <el-button v-if="canDelete(row)" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="角色" prop="role">
          <el-select v-if="!isAdminAccount" v-model="form.role" style="width: 100%" @change="onRoleChange">
            <el-option label="教师" value="teacher" />
            <el-option label="学生" value="student" />
          </el-select>
          <el-input v-else model-value="管理员" disabled />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" maxlength="100" />
        </el-form-item>
        <el-form-item v-if="form.role === 'student'" label="班级" prop="class_name">
          <el-select
            v-model="form.class_name"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入班级"
            style="width: 100%"
          >
            <el-option v-for="c in knownClasses" :key="c" :label="c" :value="c" />
          </el-select>
          <div class="hint">学生在登录页输入姓名后进入「课堂」。班级需与登录时一致，才能匹配到该账号。</div>
        </el-form-item>
        <el-form-item v-if="form.role === 'teacher'" label="管理班级">
          <el-select
            v-model="form.assigned_classes"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入班级名称"
            style="width: 100%"
          >
            <el-option v-for="c in knownClasses" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.role !== 'student'" label="密码" :prop="passwordRequired ? 'password' : ''">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="passwordRequired ? '请输入密码' : '留空则不修改'"
          />
        </el-form-item>
        <p v-else class="hint field-hint">学生使用姓名登录，无需设置密码。</p>
        <el-form-item v-if="editing" label="状态">
          <el-switch
            v-model="form.is_active"
            :disabled="isAdminAccount"
            active-text="启用"
            inactive-text="禁用"
          />
          <div v-if="isAdminAccount" class="hint">不能禁用管理员，以免无法登录系统。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { Search, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { classApi, userApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(true)
const saving = ref(false)
const users = ref([])
const knownClasses = ref([])
const search = ref('')
const roleFilter = ref('')
const dialogVisible = ref(false)
const editing = ref(null)
const formRef = ref()
const form = ref(emptyForm())

const rules = {
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  class_name: [{ required: true, message: '请输入班级', trigger: 'change' }],
}

const isAdminAccount = computed(() => editing.value?.role === 'admin')
const passwordRequired = computed(() => {
  if (form.value.role !== 'teacher') return false
  if (!editing.value) return true
  return editing.value.role !== 'teacher'
})
const dialogTitle = computed(() => {
  if (!editing.value) return '添加账号'
  if (editing.value.role === 'admin') return '编辑管理员'
  return '编辑账号'
})

const counts = computed(() => ({
  admin: users.value.filter((u) => u.role === 'admin').length,
  teacher: users.value.filter((u) => u.role === 'teacher').length,
  student: users.value.filter((u) => u.role === 'student').length,
}))

const filteredUsers = computed(() => {
  const q = search.value.trim().toLowerCase()
  return users.value.filter((u) => {
    if (roleFilter.value && u.role !== roleFilter.value) return false
    if (!q) return true
    const blob = [u.name, u.username, u.class_name, ...(u.assigned_classes || [])].join(' ').toLowerCase()
    return blob.includes(q)
  })
})

function emptyForm() {
  return {
    username: '',
    name: '',
    password: '',
    role: 'teacher',
    class_name: '课堂',
    assigned_classes: [],
    is_active: true,
  }
}

function roleLabel(role) {
  return { admin: '管理员', teacher: '教师', student: '学生' }[role] || role
}

function roleTagType(role) {
  return { admin: 'danger', teacher: 'primary', student: 'success' }[role] || 'info'
}

function canDelete(row) {
  return row.role !== 'admin' && row.id !== auth.user?.id
}

function showDialog(row = null) {
  editing.value = row
  form.value = row
    ? {
        username: row.username,
        name: row.name,
        password: '',
        role: row.role,
        class_name: row.class_name || '课堂',
        assigned_classes: [...(row.assigned_classes || [])],
        is_active: row.is_active,
      }
    : emptyForm()
  dialogVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

async function onRoleChange() {
  if (form.value.role === 'student' && !form.value.class_name) {
    form.value.class_name = '课堂'
  }
  await nextTick()
  formRef.value?.clearValidate()
}

async function handleSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editing.value) {
      const data = {
        username: form.value.username.trim(),
        name: form.value.name.trim(),
      }
      if (!isAdminAccount.value) {
        data.role = form.value.role
        data.is_active = form.value.is_active
      }
      if (form.value.role === 'student') {
        data.class_name = form.value.class_name
      }
      if (form.value.role === 'teacher') {
        data.assigned_classes = form.value.assigned_classes
      }
      if (form.value.role !== 'student' && form.value.password) {
        data.password = form.value.password
      }
      const updated = await userApi.update(editing.value.id, data)
      if (updated?.id === auth.user?.id) {
        auth.patchUser(updated)
      }
      ElMessage.success('更新成功')
    } else {
      const data = {
        username: form.value.username.trim(),
        name: form.value.name.trim(),
        role: form.value.role,
      }
      if (form.value.role === 'student') {
        data.class_name = form.value.class_name || '课堂'
      } else {
        data.password = form.value.password
        data.assigned_classes = form.value.assigned_classes
      }
      await userApi.create(data)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    await loadUsers()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  const label = roleLabel(row.role)
  await ElMessageBox.confirm(`确定删除${label}「${row.name}」吗？此操作不可恢复。`, '警告', { type: 'warning' })
  await userApi.delete(row.id)
  ElMessage.success('删除成功')
  await loadUsers()
}

function mergeClasses(list) {
  const set = new Set(knownClasses.value)
  for (const user of list) {
    if (user.class_name) set.add(user.class_name)
    for (const name of user.assigned_classes || []) {
      if (name) set.add(name)
    }
  }
  if (!set.size) set.add('课堂')
  knownClasses.value = [...set].sort()
}

async function loadUsers() {
  users.value = await userApi.list()
  mergeClasses(users.value)
}

onMounted(async () => {
  const res = await classApi.list()
  knownClasses.value = res.classes || []
  await loadUsers()
  loading.value = false
})
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.summary {
  margin: 0 0 12px;
  color: #6b7280;
  font-size: 13px;
}

.muted {
  color: #9ca3af;
  font-size: 13px;
}

.hint {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
  margin-top: 4px;
}

.field-hint {
  margin: 0 0 12px 90px;
}
</style>
