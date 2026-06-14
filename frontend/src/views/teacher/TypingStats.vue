<template>
  <div class="page-container">
    <div class="page-header">
      <h1>打字练习统计</h1>
      <p>查看学生日常打字练习情况</p>
    </div>

    <div class="content-card" v-loading="loading">
      <el-table :data="stats" stripe>
        <el-table-column prop="student_name" label="姓名" width="100" />
        <el-table-column prop="class_name" label="班级" width="120" />
        <el-table-column prop="practice_count" label="练习次数" width="100" />
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
      <p class="std-note">准确率要求 ≥ 95%（义务教育信息科技课程标准第三学段）· 中考信息技术约 10 字/分钟</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { typingApi } from '@/api'

const loading = ref(true)
const stats = ref([])
const levels = ref([])

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

onMounted(async () => {
  const [s, std] = await Promise.all([typingApi.classStats(), typingApi.standards()])
  stats.value = s
  levels.value = std.levels
  loading.value = false
})
</script>

<style scoped>
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
