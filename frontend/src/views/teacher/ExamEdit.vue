<template>
  <div class="page-container">
    <div class="page-header">
      <h1>{{ isEdit ? '编辑考试' : '创建考试' }}</h1>
      <p>设置考试信息和题目内容</p>
    </div>

    <div class="content-card" v-loading="loading">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="考试名称" required>
              <el-input v-model="form.title" placeholder="请输入考试名称" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="考试时长">
              <el-input-number v-model="form.duration_minutes" :min="5" :max="300" />
              <span style="margin-left: 8px; color: #9ca3af">分钟</span>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="及格分数">
              <el-input-number v-model="form.pass_score" :min="0" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="考试说明">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="考试说明（可选）" />
        </el-form-item>
      </el-form>
    </div>

    <div class="content-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
        <h3>题目列表 <el-tag size="small">{{ form.questions.length }} 题 · 满分 {{ totalScore }} 分</el-tag></h3>
        <div>
          <el-button @click="importVisible = true">
            <el-icon><Upload /></el-icon> 批量导入
          </el-button>
          <el-button @click="addQuestion('choice')">
            <el-icon><Plus /></el-icon> 添加选择题
          </el-button>
          <el-button @click="addQuestion('judge')">
            <el-icon><Plus /></el-icon> 添加判断题
          </el-button>
          <el-button type="success" @click="addQuestion('typing')">
            <el-icon><EditPen /></el-icon> 添加打字题
          </el-button>
        </div>
      </div>

      <div v-for="(q, index) in form.questions" :key="index" class="question-editor">
        <div class="q-header">
          <span class="q-num">第 {{ index + 1 }} 题</span>
          <el-tag :type="q.type === 'choice' ? '' : q.type === 'judge' ? 'warning' : 'success'" size="small">
            {{ q.type === 'choice' ? '选择题' : q.type === 'judge' ? '判断题' : '打字题' }}
          </el-tag>
          <div class="q-actions">
            <el-input-number v-model="q.score" :min="1" :max="100" size="small" style="width: 100px" />
            <span style="color: #9ca3af; font-size: 13px">分</span>
            <el-button type="danger" link @click="form.questions.splice(index, 1)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>

        <el-input v-model="q.content" type="textarea" :rows="q.type === 'typing' ? 4 : 2" :placeholder="q.type === 'typing' ? '请输入需要学生录入的文本内容' : '请输入题目内容'" style="margin-bottom: 12px" />

        <template v-if="q.type === 'typing'">
          <el-row :gutter="12">
            <el-col :span="8">
              <span class="config-label">限时（秒）</span>
              <el-input-number v-model="q.typing_config.time_limit" :min="30" :max="600" size="small" />
            </el-col>
            <el-col :span="8">
              <span class="config-label">达标速度（字/分）</span>
              <el-input-number v-model="q.typing_config.min_wpm" :min="5" :max="60" size="small" />
            </el-col>
            <el-col :span="8">
              <span class="config-label">最低准确率（%）</span>
              <el-input-number v-model="q.typing_config.min_accuracy" :min="60" :max="100" size="small" />
            </el-col>
          </el-row>
          <p class="typing-standard-hint">参考标准：中考 10字/分 · 课标达标 30字/分 · 准确率 ≥95%</p>
        </template>

        <template v-else-if="q.type === 'choice'">
          <div v-for="(opt, oi) in q.options" :key="oi" class="option-row">
            <el-radio v-model="q.correct_answer" :value="['A','B','C','D'][oi]">
              {{ ['A','B','C','D'][oi] }}
            </el-radio>
            <el-input v-model="q.options[oi]" :placeholder="`选项 ${['A','B','C','D'][oi]}`" />
          </div>
        </template>

        <template v-else>
          <el-radio-group v-model="q.correct_answer">
            <el-radio value="正确">正确</el-radio>
            <el-radio value="错误">错误</el-radio>
          </el-radio-group>
        </template>
      </div>

      <el-empty v-if="form.questions.length === 0" description="请添加题目" />
    </div>

    <div style="text-align: center; padding: 20px 0">
      <el-button size="large" @click="$router.back()">取消</el-button>
      <el-button size="large" type="primary" :loading="saving" @click="handleSave">
        {{ isEdit ? '保存修改' : '创建考试' }}
      </el-button>
    </div>

    <BatchImportDialog
      v-model="importVisible"
      title="批量导入题目"
      import-mode="parse"
      format-hint="支持 CSV 表格格式或块格式。CSV 适合 Excel 编辑，块格式适合直接粘贴。"
      placeholder="[选择] 以下哪个是计算机的中央处理器？
A. 内存
B. CPU
C. 硬盘
D. 显卡
答案：B
分值：10

[判断] RAM断电后数据不会丢失。
答案：错误
分值：10"
      template-filename="题目导入模板.csv"
      :template-content="questionTemplate"
      :show-default-score="true"
      :preview-columns="[
        { prop: 'type', label: '题型' },
        { prop: 'content', label: '题目' },
        { prop: 'correct_answer', label: '答案' },
        { prop: 'score', label: '分值' },
      ]"
      :on-import="handleBatchImport"
      @success="handleQuestionsImported"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { examApi, importApi } from '@/api'
import BatchImportDialog from '@/components/BatchImportDialog.vue'

const questionTemplate = `类型,题目,选项A,选项B,选项C,选项D,答案,分值
choice,以下哪个是计算机的中央处理器,内存,CPU,硬盘,显卡,B,10
choice,操作系统的主要功能不包括,进程管理,内存管理,文字排版,文件管理,C,10
judge,RAM断电后数据不会丢失,,,,,错误,10
judge,TCP/IP是互联网通信的基础协议族,,,,,正确,10
choice,1GB等于多少MB,100,512,1024,2048,C,10`

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const loading = ref(false)
const saving = ref(false)
const importVisible = ref(false)

const form = ref({
  title: '',
  description: '',
  duration_minutes: 60,
  pass_score: 60,
  questions: [],
})

const totalScore = computed(() => form.value.questions.reduce((s, q) => s + (q.score || 0), 0))

function addQuestion(type) {
  const q = {
    type,
    content: '',
    score: type === 'typing' ? 18 : 10,
    order_num: form.value.questions.length,
    correct_answer: type === 'choice' ? 'A' : type === 'judge' ? '正确' : '',
    options: type === 'choice' ? ['A. ', 'B. ', 'C. ', 'D. '] : type === 'judge' ? ['正确', '错误'] : {
      time_limit: 120, min_wpm: 10, pass_wpm: 20, excellent_wpm: 30, min_accuracy: 95,
    },
    typing_config: type === 'typing' ? {
      time_limit: 120, min_wpm: 10, pass_wpm: 20, excellent_wpm: 30, min_accuracy: 95,
    } : undefined,
  }
  form.value.questions.push(q)
}

function handleQuestionsImported(questions) {
  const startOrder = form.value.questions.length
  for (let i = 0; i < questions.length; i++) {
    const q = questions[i]
    form.value.questions.push({
      type: q.type,
      content: q.content,
      options: [...q.options],
      correct_answer: q.correct_answer,
      score: q.score,
      order_num: startOrder + i,
    })
  }
}

async function handleBatchImport({ text, file, defaultScore }) {
  if (file) {
    return importApi.parseQuestionsFile(file, defaultScore)
  }
  return importApi.parseQuestions({ text, default_score: defaultScore })
}

onMounted(async () => {
  if (isEdit.value) {
    loading.value = true
    const exam = await examApi.get(Number(route.params.id))
    form.value = {
      title: exam.title,
      description: exam.description,
      duration_minutes: exam.duration_minutes,
      pass_score: exam.pass_score,
      questions: exam.questions.map((q) => ({
        type: q.type,
        content: q.content,
        options: q.type === 'typing' ? (typeof q.options === 'object' && !Array.isArray(q.options) ? q.options : {}) : [...(q.options || [])],
        correct_answer: q.correct_answer || q.content,
        score: q.score,
        order_num: q.order_num,
        typing_config: q.type === 'typing' ? {
          time_limit: q.options?.time_limit || 120,
          min_wpm: q.options?.min_wpm || 10,
          pass_wpm: q.options?.pass_wpm || 20,
          excellent_wpm: q.options?.excellent_wpm || 30,
          min_accuracy: q.options?.min_accuracy || 95,
        } : undefined,
      })),
    }
    loading.value = false
  }
})

async function handleSave() {
  if (!form.value.title) return ElMessage.warning('请输入考试名称')
  if (form.value.questions.length === 0) return ElMessage.warning('请至少添加一道题目')
  for (const q of form.value.questions) {
    if (!q.content) return ElMessage.warning('请填写所有题目内容')
  }

  saving.value = true
  try {
    const payload = {
      ...form.value,
      questions: form.value.questions.map((q) => {
        if (q.type === 'typing') {
          return {
            type: q.type,
            content: q.content,
            options: q.typing_config || {},
            correct_answer: q.content,
            score: q.score,
            order_num: q.order_num,
          }
        }
        return {
          type: q.type,
          content: q.content,
          options: q.options,
          correct_answer: q.correct_answer,
          score: q.score,
          order_num: q.order_num,
        }
      }),
    }
    if (isEdit.value) {
      await examApi.update(Number(route.params.id), payload)
      ElMessage.success('保存成功')
    } else {
      await examApi.create(payload)
      ElMessage.success('创建成功')
    }
    router.push('/teacher/exams')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.question-editor {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
  background: #fafafa;
}

.q-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.q-num {
  font-weight: 600;
  color: #4f46e5;
}

.q-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.config-label {
  display: block;
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 4px;
}

.typing-standard-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}
</style>
