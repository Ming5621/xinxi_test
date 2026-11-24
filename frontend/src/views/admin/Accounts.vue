<template>
  <div class="page-container">
    <div class="page-header">
      <h1>账号管理</h1>
      <p>学生使用班级、本人姓名和密码登录。教师和管理员使用用户名与密码。</p>
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
        <el-button @click="handleExportPack">导出全部数据</el-button>
        <el-button @click="packFileRef?.click()">导入数据包</el-button>
        <input ref="packFileRef" type="file" accept=".json,application/json" class="hidden-file" @change="handleImportPack" />
        <el-button @click="importVisible = true">批量导入学生</el-button>
        <el-button type="danger" plain :disabled="!selectedStudents.length" @click="deleteSelectedStudents">
          批量删除学生
        </el-button>
        <el-button type="danger" plain :disabled="!selectedDisabledTeachers.length" @click="forceDeleteTeachers">
          强制删除已停用教师
        </el-button>
        <el-button type="primary" @click="showDialog()">
          <el-icon><Plus /></el-icon> 添加账号
        </el-button>
      </div>
      <p class="summary">
        共 {{ users.length }} 个账号（管理员 {{ counts.admin }}，教师 {{ counts.teacher }}，学生 {{ counts.student }}）
      </p>

      <el-table :data="filteredUsers" stripe v-loading="loading" row-key="id" @selection-change="selected = $event">
        <el-table-column type="selection" width="48" :selectable="(row) => row.role !== 'admin' && row.id !== auth.user?.id" />
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
        <el-table-column label="学生绑定教师" min-width="155">
          <template #default="{ row }">
            <span v-if="row.role === 'student'">{{ studentTeacherLabel(row.managed_by_teacher_id) }}</span>
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
        <el-form-item v-if="editing" label="用户名" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" maxlength="100" />
        </el-form-item>
        <el-form-item v-if="form.role === 'student'" label="班级" :prop="editing?.role === 'student' && !editing.class_name ? '' : 'class_name'">
          <el-select
            v-model="form.class_name"
            filterable
            placeholder="选择班级"
            style="width: 100%"
            @change="onStudentClassChange"
          >
            <el-option v-for="c in knownClasses" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.role === 'student'" label="绑定教师">
          <el-select v-model="form.managed_by_teacher_id" placeholder="未单独绑定" clearable :value-on-clear="null" filterable style="width: 100%">
            <el-option
              v-for="teacher in eligibleTeachers"
              :key="teacher.id"
              :label="teacherLabel(teacher)"
              :value="teacher.id"
              :disabled="!teacher.is_active || !teacher.assigned_classes.includes(form.class_name)"
            />
          </el-select>
          <div class="hint">未单独绑定时，该班级的所有管理教师均可管理此学生。</div>
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
        <el-form-item :label="form.role === 'student' ? '初始密码' : '密码'" :prop="passwordRequired ? 'password' : ''">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="passwordRequired ? '请输入密码' : form.role === 'student' && (!editing || editing.role !== 'student') ? '留空使用 123456' : '留空则不修改'"
          />
          <div v-if="form.role === 'student' && editing?.role === 'student'" class="hint">填写后会重置密码，学生下次登录时必须修改。</div>
        </el-form-item>
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
    <BatchImportDialog
      v-model="importVisible"
      title="批量导入学生"
      format-hint="用户名可省略。更新已有学生时，系统按姓名和班级匹配，旧表也可用用户名匹配。教师列留空保留有效绑定，填「未绑定」可解除。"
      :placeholder="studentTemplate"
      template-filename="学生导入模板.csv"
      :template-content="studentTemplate"
      show-default-password
      show-update-existing
      :preview-columns="[
        { prop: 'username', label: '用户名' },
        { prop: 'name', label: '姓名' },
        { prop: 'class_name', label: '班级' },
      ]"
      :on-import="handleBatchImport"
      @success="loadUsers"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { Search, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { classApi, exportApi, importApi, userApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import BatchImportDialog from '@/components/BatchImportDialog.vue'

const studentTemplate = `姓名,班级,密码,教师用户名
张三,课堂,,teacher1
李四,课堂,,未绑定`

const auth = useAuthStore()
const loading = ref(true)
const saving = ref(false)
const users = ref([])
const knownClasses = ref([])
const search = ref('')
const roleFilter = ref('')
const dialogVisible = ref(false)
const importVisible = ref(false)
const editing = ref(null)
const formRef = ref()
const packFileRef = ref()
const selected = ref([])
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

const teachers = computed(() => users.value.filter((user) => user.role === 'teacher'))
const selectedStudents = computed(() => selected.value.filter((user) => user.role === 'student'))
const selectedDisabledTeachers = computed(() => selected.value.filter((user) => user.role === 'teacher' && !user.is_active))
const eligibleTeachers = computed(() => teachers.value.filter((teacher) =>
  teacher.id === form.value.managed_by_teacher_id
  || (teacher.is_active && teacher.assigned_classes.includes(form.value.class_name))
))

function defaultClass() {
  return knownClasses.value.includes('课堂') ? '课堂' : knownClasses.value[0] || ''
}

function emptyForm() {
  return {
    username: '',
    name: '',
    password: '',
    role: 'teacher',
    class_name: '',
    assigned_classes: [],
    managed_by_teacher_id: null,
    is_active: true,
  }
}

function teacherLabel(teacher) {
  const username = teacher.name === teacher.username ? '' : `（${teacher.username}）`
  return `${teacher.name}${username}${teacher.is_active ? '' : ' · 已禁用'}`
}

function studentTeacherLabel(teacherId) {
  const teacher = teachers.value.find((user) => user.id === teacherId)
  return teacher ? teacherLabel(teacher) : teacherId ? '教师账号不可用' : '未单独绑定'
}

function onStudentClassChange(className) {
  const teacher = teachers.value.find((user) => user.id === form.value.managed_by_teacher_id)
  if (!teacher?.is_active || !teacher.assigned_classes.includes(className)) {
    form.value.managed_by_teacher_id = null
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
        class_name: row.class_name,
        assigned_classes: [...(row.assigned_classes || [])],
        managed_by_teacher_id: row.managed_by_teacher_id,
        is_active: row.is_active,
      }
    : emptyForm()
  if (!row) {
    form.value.role = roleFilter.value === 'student' ? 'student' : 'teacher'
    form.value.class_name = defaultClass()
  }
  dialogVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

async function onRoleChange() {
  if (form.value.role === 'student' && !form.value.class_name) {
    form.value.class_name = defaultClass()
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
        if (form.value.class_name) data.class_name = form.value.class_name
        if (form.value.managed_by_teacher_id !== editing.value.managed_by_teacher_id) {
          data.managed_by_teacher_id = form.value.managed_by_teacher_id
        }
      }
      if (form.value.role === 'teacher') {
        data.assigned_classes = form.value.assigned_classes
      }
      if (form.value.password) {
        data.password = form.value.password
      }
      const updated = await userApi.update(editing.value.id, data)
      if (updated?.id === auth.user?.id) {
        auth.patchUser(updated)
      }
      ElMessage.success('更新成功')
    } else {
      const data = {
        name: form.value.name.trim(),
        role: form.value.role,
      }
      if (form.value.role === 'student') {
        data.class_name = form.value.class_name
        data.managed_by_teacher_id = form.value.managed_by_teacher_id
        if (form.value.password) data.password = form.value.password
      } else {
        data.password = form.value.password
        data.assigned_classes = form.value.assigned_classes
      }
      const created = await userApi.create(data)
      ElMessage.success(created.role === 'teacher' ? `添加成功，登录用户名为 ${created.username}` : '添加成功')
    }
    dialogVisible.value = false
    await loadUsers()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  const force = row.role === 'teacher' && !row.is_active
  const message = force
    ? `「${row.name}」已停用。强制删除会同时删除其考试、练习文章和课堂测试，学生账号保留并解除绑定。此操作不可恢复。`
    : `确定删除${roleLabel(row.role)}「${row.name}」${row.role === 'student' ? '及其考试、打字记录' : ''}吗？此操作不可恢复。`
  await ElMessageBox.confirm(message, force ? '强制删除教师' : '警告', { type: 'warning' })
  await userApi.delete(row.id, force)
  ElMessage.success('删除成功')
  await loadUsers()
}

async function reportBatch(result, successText) {
  await loadUsers()
  selected.value = []
  if (result?.errors?.length) {
    await ElMessageBox.alert([`${successText} ${result.deleted || 0} 个`, ...result.errors].join('\n'), '删除结果')
  } else {
    ElMessage.success(`${successText} ${result?.deleted || 0} 个`)
  }
}

async function deleteSelectedStudents() {
  const rows = selectedStudents.value
  if (!rows.length) return
  await ElMessageBox.confirm(
    `将强制删除 ${rows.length} 名学生及其考试成绩、打字记录。此操作不可恢复。`,
    '批量删除学生',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  const result = await userApi.batchDelete(rows.map((row) => row.id), true)
  await reportBatch(result, '已删除学生')
}

async function forceDeleteTeachers() {
  const rows = selectedDisabledTeachers.value
  if (!rows.length) return
  await ElMessageBox.confirm(
    `将强制删除 ${rows.length} 名已停用教师，以及他们的考试、练习文章和课堂测试。学生账号会保留，并解除与这些教师的绑定。`,
    '强制删除已停用教师',
    { type: 'warning', confirmButtonText: '强制删除', cancelButtonText: '取消' },
  )
  const result = await userApi.batchDelete(rows.map((row) => row.id), true)
  await reportBatch(result, '已强制删除教师')
}

async function loadUsers() {
  const [accounts, result] = await Promise.all([userApi.list(), classApi.list()])
  users.value = accounts
  knownClasses.value = result.classes
}

async function handleBatchImport({ text, file, defaultPassword, updateExisting }) {
  if (file) return importApi.studentsFile(file, defaultPassword, updateExisting)
  return importApi.students({ text, default_password: defaultPassword, update_existing: updateExisting })
}

async function handleExportPack() {
  await exportApi.teacherPack()
  ElMessage.success('已导出数据包，可在另一台机器导入')
}

async function confirmPackOverwrite() {
  try {
    await ElMessageBox.confirm(
      '导入后，数据包中的教师和管理员账号（含登录密码）、学生、班级、考试、打字文章，以及全部考试答卷和打字记录会写入本机。如果本机已有相同账号，或这些教师以前的学生、考试、文章和成绩，确认后会用数据包覆盖。',
      '确认覆盖并导入',
      { type: 'warning', confirmButtonText: '覆盖并导入', cancelButtonText: '取消' },
    )
    return true
  } catch {
    return false
  }
}

function packSummary(result) {
  return `教师新增 ${result?.teacher_created || 0}、更新 ${result?.teacher_updated || 0}，学生新增 ${result?.student_created || 0}、更新 ${result?.student_updated || 0}、移除 ${result?.student_removed || 0}，考试 ${result?.exam_count || 0}，文章 ${result?.text_count || 0}，答卷 ${result?.exam_result_count || 0}，打字记录 ${result?.typing_record_count || 0}`
}

async function handleImportPack(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!await confirmPackOverwrite()) return
  const result = await importApi.teacherPackFile(file, true)
  await loadUsers()
  const summary = packSummary(result)
  if (result?.errors?.length) {
    await ElMessageBox.alert([summary, ...result.errors].join('\n'), '导入结果')
  } else {
    ElMessage.success(summary)
  }
}

onMounted(async () => {
  try {
    await loadUsers()
  } finally {
    loading.value = false
  }
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

.hidden-file {
  display: none;
}
</style>
