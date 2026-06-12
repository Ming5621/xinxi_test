<template>
  <el-dialog v-model="visible" :title="title" width="720px" @closed="handleClosed">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="粘贴文本" name="text">
        <el-alert :title="formatHint" type="info" :closable="false" show-icon style="margin-bottom: 12px" />
        <el-input
          v-model="textContent"
          type="textarea"
          :rows="12"
          :placeholder="placeholder"
        />
        <div v-if="showDefaultPassword" style="margin-top: 12px">
          <span style="color: #6b7280; font-size: 14px">默认密码：</span>
          <el-input v-model="defaultPassword" style="width: 200px" placeholder="未填写时使用" />
        </div>
        <div v-if="showDefaultScore" style="margin-top: 12px">
          <span style="color: #6b7280; font-size: 14px">默认分值：</span>
          <el-input-number v-model="defaultScore" :min="1" :max="100" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="上传文件" name="file">
        <el-upload
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
            <div class="el-upload__tip">支持 .csv / .txt / .tsv 文件，UTF-8 或 GBK 编码</div>
          </template>
        </el-upload>
        <div v-if="showDefaultPassword" style="margin-top: 12px">
          <span style="color: #6b7280; font-size: 14px">默认密码：</span>
          <el-input v-model="defaultPassword" style="width: 200px" />
        </div>
        <div v-if="showDefaultScore" style="margin-top: 12px">
          <span style="color: #6b7280; font-size: 14px">默认分值：</span>
          <el-input-number v-model="defaultScore" :min="1" :max="100" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <div v-if="previewItems.length" class="preview-section">
      <h4>预览（前 {{ previewItems.length }} 条）</h4>
      <el-table :data="previewItems" size="small" max-height="200" stripe>
        <el-table-column v-for="col in previewColumns" :key="col.prop" :prop="col.prop" :label="col.label" />
      </el-table>
    </div>

    <div v-if="errors.length" class="error-section">
      <h4>提示信息</h4>
      <ul>
        <li v-for="(err, i) in errors" :key="i" :class="{ warn: err.includes('跳过') }">{{ err }}</li>
      </ul>
    </div>

    <template #footer>
      <el-button @click="downloadTemplate">下载模板</el-button>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleImport">
        {{ importMode === 'parse' ? '解析并添加' : '确认导入' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: Boolean,
  title: { type: String, default: '批量导入' },
  importMode: { type: String, default: 'import' }, // import | parse
  showDefaultPassword: Boolean,
  showDefaultScore: Boolean,
  formatHint: String,
  placeholder: String,
  templateContent: String,
  templateFilename: String,
  previewColumns: { type: Array, default: () => [] },
  onImport: Function,
  onParse: Function,
})

const emit = defineEmits(['update:modelValue', 'success'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const activeTab = ref('text')
const textContent = ref('')
const defaultPassword = ref('123456')
const defaultScore = ref(10)
const selectedFile = ref(null)
const loading = ref(false)
const previewItems = ref([])
const errors = ref([])

watch(() => props.modelValue, (v) => {
  if (v) {
    textContent.value = ''
    selectedFile.value = null
    previewItems.value = []
    errors.value = []
    activeTab.value = 'text'
  }
})

function handleFileChange(file) {
  selectedFile.value = file.raw
}

function handleClosed() {
  previewItems.value = []
  errors.value = []
}

function downloadTemplate() {
  const blob = new Blob([props.templateContent], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = props.templateFilename
  a.click()
  URL.revokeObjectURL(url)
}

async function handleImport() {
  loading.value = true
  try {
    let result
    if (activeTab.value === 'file') {
      if (!selectedFile.value) {
        ElMessage.warning('请选择文件')
        return
      }
      result = await props.onImport({
        file: selectedFile.value,
        defaultPassword: defaultPassword.value,
        defaultScore: defaultScore.value,
      })
    } else {
      if (!textContent.value.trim()) {
        ElMessage.warning('请输入导入内容')
        return
      }
      result = await props.onImport({
        text: textContent.value,
        defaultPassword: defaultPassword.value,
        defaultScore: defaultScore.value,
      })
    }

    errors.value = result.errors || []
    if (props.importMode === 'parse') {
      previewItems.value = (result.questions || []).slice(0, 10).map((q) => ({
        type: q.type === 'choice' ? '选择题' : '判断题',
        content: q.content.length > 30 ? q.content.slice(0, 30) + '...' : q.content,
        correct_answer: q.correct_answer,
        score: q.score,
      }))
      if (result.questions?.length) {
        emit('success', result.questions)
        ElMessage.success(`成功解析 ${result.questions.length} 道题目`)
        visible.value = false
      } else {
        ElMessage.warning('未能解析出有效题目')
      }
    } else {
      previewItems.value = (result.preview || []).map((s) => ({
        username: s.username,
        name: s.name,
        class_name: s.class_name,
      }))
      if (result.success_count > 0) {
        emit('success')
        ElMessage.success(`成功导入 ${result.success_count} 名学生`)
        visible.value = false
      } else {
        ElMessage.warning('没有成功导入任何学生')
      }
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.preview-section, .error-section {
  margin-top: 16px;
}

.preview-section h4, .error-section h4 {
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

.error-section li.warn {
  color: #f59e0b;
}
</style>
