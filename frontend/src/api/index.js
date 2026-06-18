import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || '请求失败'
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      router.push('/login')
      ElMessage.error('登录已过期，请重新登录')
    } else {
      ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    }
    return Promise.reject(error)
  }
)

async function downloadExport(path, params = {}, filename = 'export.xlsx') {
  const token = localStorage.getItem('token')
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
  const url = `/api/export/${path}${qs ? `?${qs}` : ''}`
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error('导出失败')
  const blob = await res.blob()
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

export const authApi = {
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
}

export const classApi = {
  list: () => api.get('/classes'),
}

export const userApi = {
  list: (params) => api.get('/users', { params }),
  create: (data) => api.post('/users', data),
  update: (id, data) => api.put(`/users/${id}`, data),
  delete: (id) => api.delete(`/users/${id}`),
}

export const importApi = {
  students: (data) => api.post('/import/students', data),
  studentsFile: (file, defaultPassword = '123456') => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/import/students/file?default_password=${defaultPassword}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  parseQuestions: (data) => api.post('/import/questions/parse', data),
  parseQuestionsFile: (file, defaultScore = 10) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/import/questions/file?default_score=${defaultScore}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const examApi = {
  list: () => api.get('/exams'),
  get: (id) => api.get(`/exams/${id}`),
  create: (data) => api.post('/exams', data),
  update: (id, data) => api.put(`/exams/${id}`, data),
  delete: (id) => api.delete(`/exams/${id}`),
  publish: (id) => api.post(`/exams/${id}/publish`),
  end: (id) => api.post(`/exams/${id}/end`),
  start: (id) => api.post(`/exams/${id}/start`),
  questions: (id) => api.get(`/exams/${id}/questions`),
  submit: (id, data) => api.post(`/exams/${id}/submit`, data),
  mySessions: () => api.get('/exams/sessions/my'),
  sessionDetail: (id) => api.get(`/exams/sessions/${id}`),
  examSessions: (id, className) => api.get(`/exams/${id}/sessions`, { params: { class_name: className || undefined } }),
}

export const presenceApi = {
  heartbeat: () => api.post('/presence/heartbeat'),
  students: (className) => api.get('/presence/students', { params: { class_name: className || undefined } }),
  summary: (className) => api.get('/presence/summary', { params: { class_name: className || undefined } }),
}

export const statsApi = {
  dashboard: () => api.get('/stats/dashboard'),
  exam: (id, className) => api.get(`/stats/exam/${id}`, { params: { class_name: className || undefined } }),
}

export const typingApi = {
  standards: () => api.get('/typing/standards'),
  texts: (difficulty) => api.get('/typing/texts', { params: { difficulty } }),
  submit: (data) => api.post('/typing/submit', data),
  myRecords: () => api.get('/typing/records/my'),
  records: (params) => api.get('/typing/records', { params }),
  classStats: (className) => api.get('/typing/records/stats', { params: { class_name: className || undefined } }),
  createText: (data) => api.post('/typing/texts', data),
  deleteText: (id) => api.delete(`/typing/texts/${id}`),
  sessions: () => api.get('/typing/sessions'),
  activeSession: () => api.get('/typing/sessions/active'),
  sessionDetail: (id) => api.get(`/typing/sessions/${id}`),
  createSession: (data) => api.post('/typing/sessions', data),
  startSession: (id) => api.post(`/typing/sessions/${id}/start`),
  endSession: (id) => api.post(`/typing/sessions/${id}/end`),
}

export const exportApi = {
  students: (className) => downloadExport('students', { class_name: className }, `学生名单_${className || '全部'}.xlsx`),
  examResults: (examId, className, title) => downloadExport(`exams/${examId}/results`, { class_name: className }, `考试成绩_${title || examId}.xlsx`),
  typingRecords: (className) => downloadExport('typing/records', { class_name: className }, `打字记录_${className || '全部'}.xlsx`),
}

export default api
