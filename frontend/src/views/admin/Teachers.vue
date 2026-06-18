<template>
  <div class="page-container">
    <div class="page-header">
      <h1>教师账户管理</h1>
      <p>创建教师账号并分配其可管理的班级，教师只能查看所管班级学生的成绩与数据</p>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <el-input v-model="search" placeholder="搜索教师姓名或用户名" style="width: 280px" clearable :prefix-icon="Search" />
        <el-button type="primary" @click="showDialog()">
          <el-icon><Plus /></el-icon> 添加教师
        </el-button>
      </div>

      <el-table :data="filteredTeachers" stripe v-loading="loading">
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column label="管理班级" min-width="220">
          <template #default="{ row }">
            <el-tag v-for="c in row.assigned_classes || []" :key="c" size="small" style="margin: 2px">{{ c }}</el-tag>
            <span v-if="!row.assigned_classes?.length" class="muted">未分配班级</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑教师' : '添加教师'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="管理班级" prop="assigned_classes">
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
        <el-form-item label="密码" :prop="editing ? '' : 'password'">
          <el-input v-model="form.password" type="password" :placeholder="editing ? '留空则不修改' : '请输入密码'" show-password />
        </el-form-item>
        <el-form-item v-if="editing" label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
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
import { ref, computed, onMounted } from 'vue'
import { Search, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { classApi, userApi } from '@/api'

const loading = ref(true)
const saving = ref(false)
const teachers = ref([])
const knownClasses = ref([])
const search = ref('')
const dialogVisible = ref(false)
const editing = ref(null)
const formRef = ref()
const form = ref({
  username: '',
  name: '',
  password: '',
  assigned_classes: [],
  is_active: true,
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const filteredTeachers = computed(() => {
  if (!search.value) return teachers.value
  const q = search.value.toLowerCase()
  return teachers.value.filter(
    (t) => t.name.toLowerCase().includes(q) || t.username.toLowerCase().includes(q)
  )
})

function showDialog(row = null) {
  editing.value = row
  form.value = row
    ? {
        username: row.username,
        name: row.name,
        password: '',
        assigned_classes: [...(row.assigned_classes || [])],
        is_active: row.is_active,
      }
    : { username: '', name: '', password: '', assigned_classes: [], is_active: true }
  dialogVisible.value = true
}

async function handleSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editing.value) {
      const data = {
        name: form.value.name,
        assigned_classes: form.value.assigned_classes,
        is_active: form.value.is_active,
      }
      if (form.value.password) data.password = form.value.password
      await userApi.update(editing.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await userApi.create({
        username: form.value.username,
        name: form.value.name,
        password: form.value.password,
        role: 'teacher',
        assigned_classes: form.value.assigned_classes,
      })
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    await loadTeachers()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除教师「${row.name}」吗？`, '警告', { type: 'warning' })
  await userApi.delete(row.id)
  ElMessage.success('删除成功')
  await loadTeachers()
}

async function loadTeachers() {
  teachers.value = await userApi.list({ role: 'teacher' })
}

onMounted(async () => {
  const res = await classApi.list()
  knownClasses.value = res.classes || []
  await loadTeachers()
  loading.value = false
})
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.muted {
  color: #9ca3af;
  font-size: 13px;
}
</style>
