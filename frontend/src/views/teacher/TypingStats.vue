<template>
  <div class="page-container">
    <div class="page-header">
      <h1>打字练习统计</h1>
      <p>查看学生打字练习评分与历史记录</p>
    </div>

    <div class="content-card materials-card">
      <div class="toolbar">
        <div>
          <h3 class="section-title">练习文章</h3>
          <p class="section-hint">可手动添加，或粘贴 / 上传 txt、csv 导入。文章绑定当前教师，本班学生可选用</p>
        </div>
        <div class="toolbar-actions">
          <el-button @click="importVisible = true">
            <el-icon><Upload /></el-icon> 导入文章
          </el-button>
          <el-button type="primary" @click="openCreate">
            <el-icon><Plus /></el-icon> 手动添加
          </el-button>
        </div>
      </div>
      <el-table :data="myTexts" stripe v-loading="textsLoading" empty-text="暂无练习文章，请先导入或添加">
        <el-table-column prop="title" label="标题" min-width="160" />
        <el-table-column label="难度" width="100">
          <template #default="{ row }">{{ difficultyLabel(row.difficulty) }}</template>
        </el-table-column>
        <el-table-column prop="char_count" label="字数" width="80" />
        <el-table-column prop="time_limit" label="建议时长(秒)" width="120" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="removeText(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="content-card" v-loading="loading">
      <div class="toolbar">
        <ClassFilter v-model="classFilter" @update:model-value="loadStats" />
        <div class="toolbar-right">
          <el-button @click="$router.push('/teacher/typing/class-test')">课堂打字测试</el-button>
          <el-button @click="handleExport"><el-icon><Download /></el-icon> 导出 Excel</el-button>
        </div>
      </div>

      <el-table :data="stats" stripe>
        <el-table-column prop="student_name" label="姓名" width="100" />
        <el-table-column prop="class_name" label="班级" width="120" />
        <el-table-column prop="practice_count" label="练习次数" width="100" />
        <el-table-column label="平均评分" width="100">
          <template #default="{ row }">
            <strong>{{ row.avg_score || '—' }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="平均速度" width="120">
          <template #default="{ row }">
            <span :style="{ color: speedColor(row.avg_wpm), fontWeight: 600 }">{{ row.avg_wpm }} 字/分</span>
          </template>
        </el-table-column>
        <el-table-column prop="best_wpm" label="最佳速度" width="120">
          <template #default="{ row }">{{ row.best_wpm }} 字/分</template>
        </el-table-column>
        <el-table-column prop="avg_accuracy" label="平均准确率" width="120">
          <template #default="{ row }">{{ row.avg_accuracy }}%</template>
        </el-table-column>
        <el-table-column label="最近等级" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.latest_level !== '—'" size="small" effect="dark"
              :color="levelColor(row.latest_level)">{{ row.latest_level }}</el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showRecords(row)">历史记录</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="content-card standards-card">
      <h3>初中打字考核标准参考</h3>
      <el-row :gutter="16">
        <el-col :span="6" v-for="lv in levels" :key="lv.level">
          <div class="std-item" :style="{ borderColor: lv.color }">
            <div class="std-level" :style="{ color: lv.color }">{{ lv.level }}</div>
            <div class="std-wpm">≥ {{ lv.min_wpm }} 字/分钟</div>
            <div class="std-desc">{{ lv.desc }}</div>
          </div>
        </el-col>
      </el-row>
      <p class="std-note">准确率要求 ≥ 95% · 综合评分满分 100 分</p>
    </div>

    <el-dialog v-model="dialogVisible" :title="`${currentStudent?.student_name || ''} 的打字记录`" width="760px">
      <el-table :data="records" stripe v-loading="recordsLoading" max-height="420">
        <el-table-column prop="text_title" label="文章" min-width="140" />
        <el-table-column label="模式" width="100">
          <template #default="{ row }">{{ row.source === 'test' ? '5分钟测试' : '自由练习' }}</template>
        </el-table-column>
        <el-table-column label="评分" width="80">
          <template #default="{ row }"><strong>{{ row.score }}</strong></template>
        </el-table-column>
        <el-table-column label="速度" width="100">
          <template #default="{ row }">{{ row.wpm }} 字/分</template>
        </el-table-column>
        <el-table-column label="准确率" width="90">
          <template #default="{ row }">{{ row.accuracy }}%</template>
        </el-table-column>
        <el-table-column label="等级" width="90">
          <template #default="{ row }">
            <el-tag size="small" :color="levelColor(row.level)" effect="dark">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <ArticleImportDialog v-model="importVisible" @success="loadTexts" />

    <el-dialog v-model="textDialogVisible" :title="editingText ? '编辑练习文章' : '添加练习文章'" width="640px">
      <el-form :model="textForm" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="textForm.title" placeholder="例如：达标练习 — 中考模拟" />
        </el-form-item>
        <el-form-item label="难度">
          <el-select v-model="textForm.difficulty" style="width: 100%">
            <el-option label="入门" value="beginner" />
            <el-option label="基础" value="basic" />
            <el-option label="达标" value="standard" />
            <el-option label="进阶" value="advanced" />
          </el-select>
        </el-form-item>
        <el-form-item label="建议时长">
          <el-input-number v-model="textForm.time_limit" :min="30" :max="600" />
          <span class="form-unit">秒</span>
        </el-form-item>
        <el-form-item label="练习正文" required>
          <el-input v-model="textForm.content" type="textarea" :rows="6" placeholder="学生对照录入的文字内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="textDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="textSaving" @click="saveText">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { typingApi, exportApi } from '@/api'
import ArticleImportDialog from '@/components/ArticleImportDialog.vue'
import ClassFilter from '@/components/ClassFilter.vue'

const loading = ref(true)
const stats = ref([])
const classFilter = ref('')
const levels = ref([])
const dialogVisible = ref(false)
const recordsLoading = ref(false)
const records = ref([])
const currentStudent = ref(null)
const myTexts = ref([])
const textsLoading = ref(false)
const importVisible = ref(false)
const textDialogVisible = ref(false)
const textSaving = ref(false)
const editingText = ref(null)
const textForm = ref({
  title: '',
  content: '',
  difficulty: 'basic',
  time_limit: 120,
})

const levelColors = {
  '卓越': '#7c3aed', '优秀': '#10b981', '良好': '#3b82f6',
  '达标': '#f59e0b', '未达标': '#ef4444',
}

function levelColor(l) { return levelColors[l] || '#6b7280' }
function speedColor(wpm) {
  if (wpm >= 40) return '#7c3aed'
  if (wpm >= 30) return '#10b981'
  if (wpm >= 20) return '#3b82f6'
  if (wpm >= 10) return '#f59e0b'
  return '#ef4444'
}

function formatDate(value) {
  return new Date(value).toLocaleString('zh-CN')
}

function difficultyLabel(d) {
  return { beginner: '入门', basic: '基础', standard: '达标', advanced: '进阶' }[d] || d
}

async function loadTexts() {
  textsLoading.value = true
  try {
    myTexts.value = await typingApi.texts()
  } finally {
    textsLoading.value = false
  }
}

function openCreate() {
  editingText.value = null
  textForm.value = { title: '', content: '', difficulty: 'basic', time_limit: 120 }
  textDialogVisible.value = true
}

function openEdit(row) {
  editingText.value = row
  textForm.value = {
    title: row.title,
    content: row.content,
    difficulty: row.difficulty,
    time_limit: row.time_limit,
  }
  textDialogVisible.value = true
}

async function saveText() {
  if (!textForm.value.title.trim() || !textForm.value.content.trim()) {
    return ElMessage.warning('请填写标题和练习正文')
  }
  textSaving.value = true
  try {
    if (editingText.value) {
      await typingApi.updateText(editingText.value.id, textForm.value)
      ElMessage.success('已更新')
    } else {
      await typingApi.createText(textForm.value)
      ElMessage.success('已添加，本班学生可在打字练习中选用')
    }
    textDialogVisible.value = false
    await loadTexts()
  } finally {
    textSaving.value = false
  }
}

async function removeText(row) {
  await ElMessageBox.confirm(`确定删除「${row.title}」吗？删除后学生将不能再选择这篇文章。`, '删除文章', { type: 'warning' })
  await typingApi.deleteText(row.id)
  ElMessage.success('已删除')
  await loadTexts()
}

async function showRecords(row) {
  currentStudent.value = row
  dialogVisible.value = true
  recordsLoading.value = true
  try {
    records.value = await typingApi.records(row.student_id)
  } finally {
    recordsLoading.value = false
  }
}

async function loadStats() {
  loading.value = true
  try {
    stats.value = await typingApi.classStats(classFilter.value)
  } finally {
    loading.value = false
  }
}

async function handleExport() {
  await exportApi.typingRecords(classFilter.value)
  ElMessage.success('导出成功')
}

onMounted(async () => {
  const std = await typingApi.standards()
  levels.value = std.levels
  await Promise.all([loadStats(), loadTexts()])
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

.toolbar-right,
.toolbar-actions {
  display: flex;
  gap: 12px;
}

.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.section-hint {
  margin: 4px 0 0;
  font-size: 13px;
  color: #9ca3af;
}

.materials-card {
  margin-bottom: 20px;
}

.form-unit {
  margin-left: 8px;
  color: #9ca3af;
}

.muted { color: #9ca3af; }

.standards-card { margin-top: 20px; }
.standards-card h3 { margin-bottom: 16px; }

.std-item {
  border: 2px solid;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  margin-bottom: 12px;
}

.std-level { font-size: 20px; font-weight: 700; }
.std-wpm { font-size: 14px; color: #374151; margin: 4px 0; }
.std-desc { font-size: 12px; color: #9ca3af; }

.std-note {
  margin-top: 12px;
  font-size: 13px;
  color: #6b7280;
  text-align: center;
}
</style>
