<template>
  <div v-loading="loading">
    <div class="page-header">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <h1>成绩详情</h1>
    </div>

    <div class="result-summary" v-if="session">
      <div class="summary-score">
        <div class="score-circle" :class="{ passed: session.is_passed }">
          <span class="score-num">{{ session.total_score }}</span>
          <span class="score-total">/ {{ session.max_score }}</span>
        </div>
        <el-tag :type="session.is_passed ? 'success' : 'danger'" size="large" effect="dark">
          {{ session.is_passed ? '及格' : '不及格' }}
        </el-tag>
      </div>
      <div class="summary-info">
        <h2>{{ session.exam_title }}</h2>
        <p>提交时间: {{ formatDate(session.submit_time) }}</p>
        <p>及格线: {{ session.pass_score }} 分</p>
      </div>
    </div>

    <div class="content-card" v-if="session">
      <h3 style="margin-bottom: 16px">答题详情</h3>
      <div v-for="(ans, i) in session.answers" :key="ans.question_id" class="answer-item">
        <div class="answer-header">
          <span class="answer-num">第 {{ i + 1 }} 题</span>
          <el-tag :type="ans.is_correct ? 'success' : 'danger'" size="small">
            {{ ans.is_correct ? '正确' : '错误' }} · {{ ans.score }} 分
          </el-tag>
        </div>
        <p class="answer-question">{{ ans.question_content }}</p>
        <div class="answer-detail">
          <span>你的答案: <strong :class="ans.is_correct ? 'correct' : 'wrong'">{{ ans.student_answer || '未作答' }}</strong></span>
          <span v-if="!ans.is_correct">正确答案: <strong class="correct">{{ ans.correct_answer }}</strong></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { examApi } from '@/api'

const route = useRoute()
const loading = ref(true)
const session = ref(null)

function formatDate(d) {
  return new Date(d).toLocaleString('zh-CN')
}

onMounted(async () => {
  session.value = await examApi.sessionDetail(Number(route.params.id))
  loading.value = false
})
</script>

<style scoped>
.result-summary {
  display: flex;
  align-items: center;
  gap: 32px;
  background: white;
  border-radius: 16px;
  padding: 32px;
  margin-bottom: 20px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.summary-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.score-circle {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  border: 4px solid #ef4444;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.score-circle.passed {
  border-color: #10b981;
}

.score-num {
  font-size: 36px;
  font-weight: 700;
  color: #111827;
  line-height: 1;
}

.score-total {
  font-size: 14px;
  color: #9ca3af;
}

.summary-info h2 {
  font-size: 22px;
  margin-bottom: 8px;
}

.summary-info p {
  color: #6b7280;
  font-size: 14px;
  margin-bottom: 4px;
}

.answer-item {
  padding: 16px 0;
  border-bottom: 1px solid #f3f4f6;
}

.answer-item:last-child {
  border-bottom: none;
}

.answer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.answer-num {
  font-weight: 600;
  color: #4f46e5;
}

.answer-question {
  font-size: 15px;
  line-height: 1.6;
  margin-bottom: 8px;
}

.answer-detail {
  display: flex;
  gap: 24px;
  font-size: 14px;
  color: #6b7280;
}

.correct { color: #10b981; }
.wrong { color: #ef4444; }
</style>
