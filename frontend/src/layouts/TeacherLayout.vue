<template>
  <el-container class="teacher-layout">
    <el-aside width="240px" class="sidebar">
      <div class="sidebar-brand">
        <el-icon :size="28" color="white"><Reading /></el-icon>
        <div>
          <div class="brand-title">考试管理系统</div>
          <div class="brand-sub">教师端</div>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        background-color="#1e1b4b"
        text-color="#c7d2fe"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/teacher">
          <el-icon><DataBoard /></el-icon>
          <span>控制台</span>
        </el-menu-item>
        <el-menu-item index="/teacher/students">
          <el-icon><User /></el-icon>
          <span>学生管理</span>
        </el-menu-item>
        <el-menu-item index="/teacher/exams">
          <el-icon><Document /></el-icon>
          <span>考试管理</span>
        </el-menu-item>
        <el-menu-item index="/teacher/typing">
          <el-icon><EditPen /></el-icon>
          <span>打字统计</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="user-info">
          <el-avatar :size="36" style="background: #4f46e5">{{ auth.user?.name?.[0] }}</el-avatar>
          <div>
            <div class="user-name">{{ auth.user?.name }}</div>
            <div class="user-role">教师</div>
          </div>
        </div>
        <el-button text style="color: #c7d2fe" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon> 退出登录
        </el-button>
      </div>
    </el-aside>

    <el-container>
      <el-header class="top-header">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/teacher' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item v-if="breadcrumb">{{ breadcrumb }}</el-breadcrumb-item>
        </el-breadcrumb>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/teacher/exams')) return '/teacher/exams'
  if (path.startsWith('/teacher/students')) return '/teacher/students'
  return '/teacher'
})

const breadcrumbMap = {
  Students: '学生管理',
  Exams: '考试管理',
  ExamCreate: '创建考试',
  ExamEdit: '编辑考试',
  ExamStats: '考试统计',
  ExamResults: '考试成绩',
  TypingStats: '打字统计',
}

const breadcrumb = computed(() => breadcrumbMap[route.name] || '')

async function handleLogout() {
  await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.teacher-layout {
  min-height: 100vh;
}

.sidebar {
  background: #1e1b4b;
  display: flex;
  flex-direction: column;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.brand-title {
  color: white;
  font-size: 16px;
  font-weight: 600;
}

.brand-sub {
  color: #a5b4fc;
  font-size: 12px;
}

.el-menu {
  border-right: none;
  flex: 1;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.user-name {
  color: white;
  font-size: 14px;
  font-weight: 500;
}

.user-role {
  color: #a5b4fc;
  font-size: 12px;
}

.top-header {
  background: white;
  display: flex;
  align-items: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  height: 56px !important;
}

.main-content {
  background: #f0f2f5;
  min-height: calc(100vh - 56px);
}
</style>
