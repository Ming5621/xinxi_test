<template>
  <el-container class="admin-layout">
    <el-aside width="240px" class="sidebar">
      <div class="sidebar-brand">
        <el-icon :size="28" color="white"><Setting /></el-icon>
        <div>
          <div class="brand-title">系统管理</div>
          <div class="brand-sub">管理员端</div>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        background-color="#0f172a"
        text-color="#cbd5e1"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/admin">
          <el-icon><UserFilled /></el-icon>
          <span>教师管理</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="user-info">
          <el-avatar :size="36" style="background: #0ea5e9">{{ auth.user?.name?.[0] }}</el-avatar>
          <div>
            <div class="user-name">{{ auth.user?.name }}</div>
            <div class="user-role">管理员</div>
          </div>
        </div>
        <el-button text style="color: #cbd5e1" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon> 退出登录
        </el-button>
        <CopyrightFooter />
      </div>
    </el-aside>

    <el-container>
      <el-header class="top-header">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/admin' }">管理后台</el-breadcrumb-item>
          <el-breadcrumb-item>教师账户</el-breadcrumb-item>
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
import CopyrightFooter from '@/components/CopyrightFooter.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => route.path)

async function handleLogout() {
  await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-layout {
  min-height: 100vh;
}

.sidebar {
  background: #0f172a;
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
  color: #94a3b8;
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
  color: #94a3b8;
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
