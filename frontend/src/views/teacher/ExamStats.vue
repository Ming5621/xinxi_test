<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
      <h1>考试统计 - {{ stats?.exam_title }}</h1>
    </div>

    <template v-if="stats">
      <el-row :gutter="20">
        <el-col :xs="12" :sm="6" v-for="item in overviewCards" :key="item.label">
          <div class="stat-card">
            <div class="stat-value">{{ item.value }}</div>
            <div class="stat-label">{{ item.label }}</div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20" style="margin-top: 20px">
        <el-col :span="12">
          <div class="content-card">
            <h3 style="margin-bottom: 16px">分数段分布</h3>
            <div class="distribution">
              <div v-for="(count, range) in stats.score_distribution" :key="range" class="dist-item">
                <span class="dist-label">{{ range }}分</span>
                <div class="dist-bar-bg">
                  <div class="dist-bar" :style="{ width: barWidth(count) + '%' }"></div>
                </div>
                <span class="dist-count">{{ count }}人</span>
              </div>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="content-card">
            <h3 style="margin-bottom: 16px">成绩概览</h3>
            <div class="overview-grid">
              <div class="overview-item">
                <div class="ov-value" style="color: #4f46e5">{{ stats.average_score }}</div>
                <div class="ov-label">平均分</div>
              </div>
              <div class="overview-item">
                <div class="ov-value" style="color: #10b981">{{ stats.max_score }}</div>
                <div class="ov-label">最高分</div>
              </div>
              <div class="overview-item">
                <div class="ov-value" style="color: #f59e0b">{{ stats.min_score }}</div>
                <div class="ov-label">最低分</div>
              </div>
              <div class="overview-item">
                <div class="ov-value" style="color: #ec4899">{{ stats.pass_rate }}%</div>
                <div class="ov-label">及格率</div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>

      <div class="content-card" style="margin-top: 20px">
        <h3 style="margin-bottom: 16px">各题正确率</h3>
        <el-table :data="stats.question_stats" stripe>
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="content" label="题目" min-width="300" />
          <el-table-column label="类型" width="80">
            <template #default="{ row }">
              <el-tag :type="row.type === 'choice' ? '' : 'warning'" size="small">
                {{ row.type === 'choice' ? '选择' : '判断' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="正确/总数" width="120">
            <template #default="{ row }">{{ row.correct_count }} / {{ row.total_count }}</template>
          </el-table-column>
          <el-table-column label="正确率" width="200">
            <template #default="{ row }">
              <el-progress
                :percentage="row.correct_rate"
                :color="row.correct_rate >= 60 ? '#10b981' : '#ef4444'"
                :stroke-width="14"
                :text-inside="true"
              />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { statsApi } from '@/api'

const route = useRoute()
const loading = ref(true)
const stats = ref(null)

const overviewCards = computed(() => {
  if (!stats.value) return []
  return [
    { label: '参加人数', value: stats.value.total_students },
    { label: '已提交', value: stats.value.submitted_count },
    { label: '及格人数', value: stats.value.pass_count },
    { label: '满分', value: stats.value.total_possible_score },
  ]
})

function barWidth(count) {
  const max = Math.max(...Object.values(stats.value.score_distribution), 1)
  return (count / max) * 100
}

onMounted(async () => {
  stats.value = await statsApi.exam(Number(route.params.id))
  loading.value = false
})
</script>

<style scoped>
.distribution {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dist-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dist-label {
  width: 60px;
  font-size: 13px;
  color: #6b7280;
  text-align: right;
}

.dist-bar-bg {
  flex: 1;
  height: 24px;
  background: #f3f4f6;
  border-radius: 6px;
  overflow: hidden;
}

.dist-bar {
  height: 100%;
  background: linear-gradient(90deg, #4f46e5, #818cf8);
  border-radius: 6px;
  transition: width 0.5s;
  min-width: 4px;
}

.dist-count {
  width: 40px;
  font-size: 13px;
  color: #374151;
  font-weight: 500;
}

.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.overview-item {
  text-align: center;
  padding: 20px;
  background: #f9fafb;
  border-radius: 12px;
}

.ov-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 6px;
}

.ov-label {
  font-size: 14px;
  color: #6b7280;
}
</style>
