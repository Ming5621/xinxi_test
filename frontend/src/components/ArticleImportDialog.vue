<template>
  <el-dialog v-model="visible" title="导入练习文章" width="720px" @closed="handleClosed">
    <el-alert :title="formatHint" type="info" :closable="false" show-icon style="margin-bottom: 12px" />

    <el-form label-width="108px" class="import-form">
      <el-form-item label="默认难度">
        <el-select v-model="difficulty" style="width: 220px">
          <el-option label="入门" value="beginner" />
          <el-option label="基础" value="basic" />
          <el-option label="达标" value="standard" />
          <el-option label="进阶" value="advanced" />
        </el-select>
      </el-form-item>
      <el-form-item label="默认时长">
        <el-input-number v-model="timeLimit" :min="30" :max="600" />
        <span class="form-unit">秒（文章未单独指定时使用）</span>
      </el-form-item>
      <el-form-item label="单篇标题">
        <el-input v-model="singleTitle" placeholder="只导入一篇、且正文里没有【标题】时填写；上传 txt 可留空并使用文件名" />
      </el-form-item>
    </el-form>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="粘贴文本" name="text">
        <el-input
          v-model="textContent"
          type="textarea"
          :rows="12"
          placeholder="在此粘贴一篇正文，或按【标题】格式粘贴多篇"
        />
      </el-tab-pane>
      <el-tab-pane label="上传文件" name="file">
        <el-upload
          :key="uploadKey"
          drag
          :auto-upload="false"
          :limit="1"
          accept=".csv,.txt,.tsv"
          :on-change="handleFileChange"
          :on-remove="() => (selectedFile = null)"
        >
          <el-icon :size="40"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">支持 .txt / .csv / .tsv，UTF-8 或 GBK。纯文本文件将整篇导入，标题默认取文件名。</div>
          </template>
        </el-upload>
      </el-tab-pane>
    </el-tabs>

    <div v-if="imported.length" class="preview-section">
      <h4>已导入 {{ imported.length }} 篇</h4>
      <el-table :data="imported" size="small" max-height="200" stripe>
        <el-table-column prop="title" label="标题" min-width="160" />
        <el-table-column prop="char_count" label="字数" width="80" />
        <el-table-column label="难度" width="90">
          <template #default="{ row }">{{ difficultyLabel(row.difficulty) }}</template>
        </el-table-column>
      </el-table>
    </div>

    <div v-if="errors.length" class="error-section">
      <h4>未能导入的内容</h4>
      <ul>
        <li v-for="(err, i) in errors" :key="i">{{ err }}</li>
      </ul>
    </div>

    <template #footer>
      <el-button @click="downloadTemplate('block')">下载分段模板</el-button>
      <el-button @click="downloadTemplate('csv')">下载表格模板</el-button>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleImport">确认导入</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { typingApi } from '@/api'

const props = defineProps({
  modelValue: Boolean,
})

const emit = defineEmits(['update:modelValue', 'success'])

const formatHint = '可一次导入多篇：用【标题】分段，或上传 / 粘贴 CSV（表头：标题,正文,难度,建议时长）。只导入一篇时，直接粘贴正文并填写标题。导入后绑定当前教师，本班学生可在打字练习中选用。'

const blockTemplate = `【标题】春晓
【难度】入门
【时长】60
春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。

【标题】静夜思
【难度】基础
床前明月光，疑是地上霜。举头望明月，低头思故乡。
`

const csvTemplate = `标题,正文,难度,建议时长
春晓,"春眠不觉晓，处处闻啼鸟。",入门,60
静夜思,"床前明月光，疑是地上霜。",基础,90
`

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const activeTab = ref('text')
const textContent = ref('')
const singleTitle = ref('')
const difficulty = ref('basic')
const timeLimit = ref(120)
const selectedFile = ref(null)
const uploadKey = ref(0)
const loading = ref(false)
const errors = ref([])
const imported = ref([])

watch(() => props.modelValue, (open) => {
  if (!open) return
  textContent.value = ''
  singleTitle.value = ''
  difficulty.value = 'basic'
  timeLimit.value = 120
  selectedFile.value = null
  errors.value = []
  imported.value = []
  activeTab.value = 'text'
  uploadKey.value += 1
})

function difficultyLabel(d) {
  return { beginner: '入门', basic: '基础', standard: '达标', advanced: '进阶' }[d] || d
}

function handleFileChange(file) {
  selectedFile.value = file.raw
}

function handleClosed() {
  errors.value = []
  imported.value = []
}

function downloadTemplate(kind) {
  const content = kind === 'csv' ? csvTemplate : blockTemplate
  const filename = kind === 'csv' ? '打字文章导入模板.csv' : '打字文章导入模板.txt'
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function handleImport() {
  loading.value = true
  errors.value = []
  imported.value = []
  try {
    const payload = {
      title: singleTitle.value.trim(),
      difficulty: difficulty.value,
      time_limit: timeLimit.value,
    }
    let result
    if (activeTab.value === 'file') {
      if (!selectedFile.value) {
        ElMessage.warning('请选择文件')
        return
      }
      result = await typingApi.importTextsFile(selectedFile.value, payload)
    } else {
      if (!textContent.value.trim()) {
        ElMessage.warning('请输入导入内容')
        return
      }
      result = await typingApi.importTexts({ ...payload, text: textContent.value })
    }

    errors.value = result.errors || []
    imported.value = result.texts || []
    if (result.success_count > 0) {
      emit('success')
      ElMessage.success(`成功导入 ${result.success_count} 篇文章`)
      if (!errors.value.length) visible.value = false
    } else {
      ElMessage.warning('没有成功导入任何文章')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.import-form {
  margin-bottom: 8px;
}

.form-unit {
  margin-left: 8px;
  color: #9ca3af;
  font-size: 13px;
}

.preview-section,
.error-section {
  margin-top: 16px;
}

.preview-section h4,
.error-section h4 {
  font-size: 14px;
  color: #374151;
  margin-bottom: 8px;
}

.error-section ul {
  max-height: 120px;
  overflow-y: auto;
  padding-left: 20px;
  font-size: 13px;
  color: #ef4444;
}
</style>
