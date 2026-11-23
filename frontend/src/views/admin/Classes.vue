<template>
  <div class="page-container">
    <div class="page-header">
      <h1>班级管理</h1>
    </div>

    <div class="content-card">
      <div class="class-toolbar">
        <el-input v-model="search" placeholder="搜索班级" clearable style="max-width: 260px" />
        <el-button type="primary" @click="showDialog()">新建班级</el-button>
      </div>

      <el-table :data="filteredClasses" v-loading="loading" stripe>
        <el-table-column prop="name" label="班级" min-width="160" />
        <el-table-column label="管理教师" min-width="250">
          <template #default="{ row }">
            <template v-if="row.teachers.length">
              <el-tag v-for="teacher in row.teachers" :key="teacher.id" class="teacher-tag" effect="plain">
                {{ teacherLabel(teacher) }}
              </el-tag>
            </template>
            <span v-else class="muted">未分配</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button type="primary" link @click="showDialog(row)">编辑</el-button>
            <el-button type="danger" link :loading="deleting === row.name" @click="removeClass(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="visible" :title="originalName ? '编辑班级' : '新建班级'" width="500px">
      <el-form label-width="80px" @submit.prevent="save">
        <el-form-item label="班级名称" required>
          <el-input v-model="form.name" maxlength="100" />
        </el-form-item>
        <el-form-item label="绑定教师">
          <el-select v-model="form.teacher_ids" multiple filterable placeholder="选择管理教师" style="width: 100%">
            <el-option
              v-for="teacher in teachers"
              :key="teacher.id"
              :label="teacherLabel(teacher)"
              :value="teacher.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { classApi, userApi } from '@/api'

const classes = ref([])
const teachers = ref([])
const search = ref('')
const loading = ref(false)
const visible = ref(false)
const saving = ref(false)
const deleting = ref('')
const originalName = ref('')
const form = ref({ name: '', teacher_ids: [] })

const filteredClasses = computed(() => {
  const query = search.value.trim().toLowerCase()
  return classes.value.filter((name) => name.toLowerCase().includes(query)).map((name) => ({
    name,
    teachers: teachers.value.filter((teacher) => teacher.assigned_classes.includes(name)),
  }))
})

function showDialog(row = null) {
  originalName.value = row?.name || ''
  form.value = { name: originalName.value, teacher_ids: row?.teachers.map((teacher) => teacher.id) || [] }
  visible.value = true
}

function teacherLabel(teacher) {
  const username = teacher.name === teacher.username ? '' : `（${teacher.username}）`
  return `${teacher.name}${username}${teacher.is_active ? '' : ' · 已禁用'}`
}

async function removeClass(row) {
  const confirmed = await ElMessageBox.confirm(
    `删除「${row.name}」会解除师生班级分配，并结束该班未结束的课堂打字测试。学生账号和历史成绩会保留，学生需重新分班后才能再次登录。`,
    '删除班级',
    { type: 'warning', confirmButtonText: '删除班级', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) return
  deleting.value = row.name
  try {
    await classApi.delete(row.name)
    await load()
    ElMessage.success('班级已删除')
  } catch {
    // The API interceptor displays request errors.
  } finally {
    deleting.value = ''
  }
}

async function load() {
  loading.value = true
  try {
    const [result, users] = await Promise.all([classApi.list(), userApi.list({ role: 'teacher' })])
    classes.value = result.classes
    teachers.value = users
  } finally {
    loading.value = false
  }
}

async function save() {
  const name = form.value.name.trim()
  if (!name) {
    ElMessage.warning('请输入班级名称')
    return
  }
  saving.value = true
  const payload = { name, teacher_ids: form.value.teacher_ids }
  try {
    if (originalName.value) await classApi.update({ ...payload, original_name: originalName.value })
    else await classApi.create(payload)
    visible.value = false
    ElMessage.success('班级已保存')
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.class-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.teacher-tag {
  margin: 2px 6px 2px 0;
}

.muted {
  color: #6b7280;
}
</style>
