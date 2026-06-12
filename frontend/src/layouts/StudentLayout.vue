<template>
  <div class="layout">
    <header class="header">
      <div class="header-left">
        <el-icon :size="28" color="#4f46e5"><Reading /></el-icon>
        <span class="logo-text">在线考试系统</span>
        <el-tag type="info" size="small" effect="plain">学生端</el-tag>
      </div>
      <div class="header-right">
        <span class="user-name">{{ auth.user?.name }}</span>
        <el-tag size="small">{{ auth.user?.class_name }}</el-tag>
        <el-button text @click="handleLogout">
          <el-icon><SwitchButton /></el-icon> 退出
        </el-button>
      </div>
    </header>

    <nav class="nav">
      <router-link to="/student" class="nav-item" :class="{ active: $route.name === 'StudentHome' }">
        <el-icon><HomeFilled /></el-icon> 考试大厅
      </router-link>
      <router-link to="/student/results" class="nav-item" :class="{ active: $route.path.includes('results') }">
        <el-icon><Document /></el-icon> 我的成绩
      </router-link>
    </nav>

    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

async function handleLogout() {
  await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  background: white;
  padding: 0 24px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-name {
  font-weight: 500;
}

.nav {
  background: white;
  border-bottom: 1px solid #f3f4f6;
  padding: 0 24px;
  display: flex;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 20px;
  color: #6b7280;
  text-decoration: none;
  font-size: 14px;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.nav-item:hover {
  color: #4f46e5;
}

.nav-item.active {
  color: #4f46e5;
  border-bottom-color: #4f46e5;
  font-weight: 500;
}

.main {
  flex: 1;
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}
</style>
