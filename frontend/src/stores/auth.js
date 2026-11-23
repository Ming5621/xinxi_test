import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'

function loadStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    localStorage.removeItem('user')
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(loadStoredUser())

  const isLoggedIn = computed(() => !!token.value)
  const isTeacher = computed(() => user.value?.role === 'teacher')
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isStudent = computed(() => user.value?.role === 'student')

  function applySession(res) {
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    return res.user
  }

  async function login(username, password) {
    const res = await authApi.login({ username, password })
    return applySession(res)
  }

  async function studentLogin(username, password, className) {
    const res = await authApi.studentLogin({ username, password, class_name: className })
    if (res.password_change_token) return res
    applySession(res)
    return res
  }

  async function changeStudentPassword(token, newPassword) {
    return applySession(await authApi.changeStudentPassword(token, newPassword))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  function patchUser(partial) {
    if (!user.value || !partial) return
    user.value = { ...user.value, ...partial }
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  return { token, user, isLoggedIn, isTeacher, isAdmin, isStudent, login, studentLogin, changeStudentPassword, logout, patchUser }
})
