<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-shape shape-1"></div>
      <div class="bg-shape shape-2"></div>
      <div class="bg-shape shape-3"></div>
    </div>

    <div class="login-container">
      <div class="login-brand">
        <div class="brand-icon">
          <el-icon :size="48"><Reading /></el-icon>
        </div>
        <h1>微机教室在线考试系统</h1>
        <p>Computer Lab Online Examination System</p>
        <div class="features">
          <div class="feature-item">
            <el-icon><Document /></el-icon>
            <span>选择题 & 判断题</span>
          </div>
          <div class="feature-item">
            <el-icon><Monitor /></el-icon>
            <span>局域网部署</span>
          </div>
          <div class="feature-item">
            <el-icon><DataAnalysis /></el-icon>
            <span>自动统计分析</span>
          </div>
        </div>
      </div>

      <div class="login-card">
        <h2>用户登录</h2>
        <p class="login-subtitle">请输入您的账号和密码</p>

        <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="用户名"
              size="large"
              :prefix-icon="User"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              size="large"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              class="login-btn"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>

        <div class="login-hint">
          <p>管理员: <code>admin</code> / <code>admin123</code></p>
          <p>教师账号: <code>teacher</code> / <code>teacher123</code></p>
          <p>学生账号: <code>student01</code> / <code>123456</code></p>
        </div>
      </div>
    </div>

    <CopyrightFooter class="login-footer" />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import CopyrightFooter from '@/components/CopyrightFooter.vue'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)

const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function homePath(role) {
  if (role === 'admin') return '/admin'
  if (role === 'teacher') return '/teacher'
  return '/student'
}

async function handleLogin() {
  await formRef.value.validate()
  loading.value = true
  try {
    const user = await auth.login(form.username, form.password)
    ElMessage.success(`欢迎回来，${user.name}！`)
    router.push(homePath(user.role))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  position: relative;
  overflow: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.bg-shape {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
}

.shape-1 { width: 400px; height: 400px; top: -100px; right: -100px; }
.shape-2 { width: 300px; height: 300px; bottom: -80px; left: -80px; }
.shape-3 { width: 200px; height: 200px; top: 50%; left: 30%; }

.login-container {
  display: flex;
  gap: 60px;
  align-items: center;
  z-index: 1;
  padding: 20px;
}

.login-brand {
  color: white;
  max-width: 400px;
}

.brand-icon {
  width: 80px;
  height: 80px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
  backdrop-filter: blur(10px);
}

.login-brand h1 {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 8px;
}

.login-brand > p {
  opacity: 0.8;
  font-size: 14px;
  margin-bottom: 32px;
}

.features {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  opacity: 0.9;
}

.login-card {
  background: white;
  border-radius: 20px;
  padding: 40px;
  width: 400px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.login-card h2 {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 4px;
}

.login-subtitle {
  color: #6b7280;
  font-size: 14px;
  margin-bottom: 28px;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  border-radius: 10px;
}

.login-hint {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #f3f4f6;
  font-size: 13px;
  color: #9ca3af;
}

.login-hint code {
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
  color: #4f46e5;
}

.login-footer {
  position: relative;
  z-index: 1;
  color: rgba(255, 255, 255, 0.75) !important;
  padding-bottom: 20px;
}

@media (max-width: 900px) {
  .login-container {
    flex-direction: column;
    gap: 30px;
  }
  .login-brand {
    text-align: center;
  }
  .brand-icon {
    margin: 0 auto 24px;
  }
  .features {
    align-items: center;
  }
}
</style>
