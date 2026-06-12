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
          <el-button @click="addQuestion('choice')">
            <el-icon><Plus /></el-icon> 添加选择题
          </el-button>
          <el-button @click="addQuestion('judge')">
            <el-icon><Plus /></el-icon> 添加判断题
          </el-button>
        </div>
      </div>

      <div v-for="(q, index) in form.questions" :key="index" class="question-editor">
        <div class="q-header">
          <span class="q-num">第 {{ index + 1 }} 题</span>
          <el-tag :type="q.type === 'choice' ? '' : 'warning'" size="small">
            {{ q.type === 'choice' ? '选择题' : '判断题' }}
          </el-tag>
          <div class="q-actions">
            <el-input-number v-model="q.score" :min="1" :max="100" size="small" style="width: 100px" />
            <span style="color: #9ca3af; font-size: 13px">分</span>
            <el-button type="danger" link @click="form.questions.splice(index, 1)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>

        <el-input v-model="q.content" type="textarea" :rows="2" placeholder="请输入题目内容" style="margin-bottom: 12px" />

        <template v-if="q.type === 'choice'">
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { examApi } from '@/api'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const loading = ref(false)
const saving = ref(false)

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
    score: 10,
    order_num: form.value.questions.length,
    correct_answer: type === 'choice' ? 'A' : '正确',
    options: type === 'choice' ? ['A. ', 'B. ', 'C. ', 'D. '] : ['正确', '错误'],
  }
  form.value.questions.push(q)
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
        options: [...q.options],
        correct_answer: q.correct_answer,
        score: q.score,
        order_num: q.order_num,
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
    if (isEdit.value) {
      await examApi.update(Number(route.params.id), form.value)
      ElMessage.success('保存成功')
    } else {
      await examApi.create(form.value)
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
</style>
