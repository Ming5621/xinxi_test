<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-shape shape-1"></div>
      <div class="bg-shape shape-2"></div>
      <div class="bg-shape shape-3"></div>
    </div>

    <div class="login-container">
      <div v-if="!passwordChangeToken" class="login-brand">
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

      <div v-if="passwordChangeToken" class="login-card">
        <h2>修改初始密码</h2>
        <p class="login-subtitle">设置至少 8 个字符的新密码后即可进入系统。</p>
        <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" @submit.prevent="handlePasswordChange">
          <el-form-item prop="newPassword">
            <el-input v-model="passwordForm.newPassword" type="password" placeholder="新密码" autocomplete="new-password" size="large" show-password />
          </el-form-item>
          <el-form-item prop="confirmation">
            <el-input v-model="passwordForm.confirmation" type="password" placeholder="确认新密码" autocomplete="new-password" size="large" show-password />
          </el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" class="login-btn">保存并进入</el-button>
          <el-button text :disabled="loading" class="back-to-login" @click="returnToLogin">返回登录</el-button>
        </el-form>
      </div>

      <div v-else class="login-card">
        <h2>开始使用</h2>
        <p class="login-subtitle">{{ mode === 'student' ? '使用本人姓名和密码登录' : '教师登录' }}</p>

        <div class="mode-switch">
          <button type="button" class="mode-btn" :class="{ active: mode === 'student' }" :disabled="loading" @click="mode = 'student'">学生</button>
          <button type="button" class="mode-btn" :class="{ active: mode === 'teacher' }" :disabled="loading" @click="mode = 'teacher'">教师</button>
        </div>

        <el-form v-if="mode === 'student'" ref="studentFormRef" :model="studentForm" :rules="studentRules" @submit.prevent="handleStudentLogin">
          <el-form-item prop="username">
            <el-input
              v-model="studentForm.username"
              placeholder="用户名（本人姓名）"
              autocomplete="username"
              size="large"
              :prefix-icon="User"
              maxlength="40"
            />
          </el-form-item>
          <el-form-item prop="class_name">
            <el-select v-model="studentForm.class_name" placeholder="选择班级" size="large" filterable style="width: 100%">
              <el-option v-for="name in classes" :key="name" :label="name" :value="name" />
            </el-select>
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="studentForm.password"
              type="password"
              placeholder="密码"
              autocomplete="current-password"
              size="large"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="large" native-type="submit" :loading="loading" class="login-btn">
              进入系统
            </el-button>
          </el-form-item>
        </el-form>

        <el-form v-else ref="teacherFormRef" :model="teacherForm" :rules="teacherRules" @submit.prevent="handleTeacherLogin">
          <el-form-item prop="username">
            <el-input
              v-model="teacherForm.username"
              placeholder="用户名"
              size="large"
              :prefix-icon="User"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="teacherForm.password"
              type="password"
              placeholder="密码"
              size="large"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleTeacherLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="large" :loading="loading" class="login-btn" @click="handleTeacherLogin">
              登 录
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <CopyrightFooter class="login-footer" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api'
import CopyrightFooter from '@/components/CopyrightFooter.vue'

const router = useRouter()
const auth = useAuthStore()
const mode = ref('student')
const studentFormRef = ref()
const teacherFormRef = ref()
const passwordFormRef = ref()
const passwordChangeToken = ref('')
const loading = ref(false)

const classes = ref([])
const studentForm = reactive({ username: '', class_name: '', password: '' })
const teacherForm = reactive({ username: '', password: '' })
const passwordForm = reactive({ newPassword: '', confirmation: '' })

const studentRules = {
  username: [{ required: true, message: '请输入本人姓名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  class_name: [{ required: true, message: '请选择班级', trigger: 'change' }],
}
const passwordRules = {
  newPassword: [{ required: true, min: 8, message: '新密码至少 8 个字符', trigger: 'blur' }],
  confirmation: [{
    validator: (_, value, callback) => {
      if (!value || value !== passwordForm.newPassword) callback(new Error('两次输入的密码不一致'))
      else callback()
    },
    trigger: 'blur',
  }],
}
const teacherRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function homePath(role) {
  if (role === 'admin') return '/admin'
  if (role === 'teacher') return '/teacher'
  return '/student'
}

async function handleStudentLogin() {
  if (loading.value || !await studentFormRef.value.validate().catch(() => false)) return
  loading.value = true
  try {
    const result = await auth.studentLogin(studentForm.username.trim(), studentForm.password, studentForm.class_name)
    studentForm.password = ''
    if (result.password_change_token) {
      passwordChangeToken.value = result.password_change_token
      return
    }
    ElMessage.success(`欢迎，${result.user.name}！`)
    router.push(homePath(result.user.role))
  } catch {
    studentForm.password = ''
  } finally {
    loading.value = false
  }
}

function returnToLogin() {
  passwordChangeToken.value = ''
  passwordForm.newPassword = ''
  passwordForm.confirmation = ''
}

async function handlePasswordChange() {
  if (loading.value || !await passwordFormRef.value.validate().catch(() => false)) return
  loading.value = true
  try {
    await auth.changeStudentPassword(passwordChangeToken.value, passwordForm.newPassword)
    passwordForm.newPassword = ''
    passwordForm.confirmation = ''
    ElMessage.success('密码已更新')
    router.replace('/student')
  } catch (error) {
    if (error.response?.status === 401) returnToLogin()
  } finally {
    loading.value = false
  }
}

async function handleTeacherLogin() {
  await teacherFormRef.value.validate()
  loading.value = true
  try {
    const user = await auth.login(teacherForm.username.trim(), teacherForm.password)
    ElMessage.success(`欢迎回来，${user.name}！`)
    router.push(homePath(user.role))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const result = await authApi.studentClasses()
  classes.value = result.classes
  if (classes.value.includes('课堂')) studentForm.class_name = '课堂'
  else if (classes.value.length === 1) studentForm.class_name = classes.value[0]
})
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
  margin-bottom: 20px;
}

.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 20px;
  padding: 4px;
  background: #f3f4f6;
  border-radius: 12px;
}

.mode-btn {
  border: none;
  background: transparent;
  height: 40px;
  border-radius: 10px;
  font-size: 15px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn.active {
  background: white;
  color: #4f46e5;
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  border-radius: 10px;
}

.back-to-login {
  display: block;
  margin: 10px auto 0;
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
