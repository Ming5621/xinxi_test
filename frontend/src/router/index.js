import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/student',
    component: () => import('@/layouts/StudentLayout.vue'),
    meta: { requiresAuth: true, role: 'student' },
    children: [
      { path: '', name: 'StudentHome', component: () => import('@/views/student/Dashboard.vue') },
      { path: 'exam/:id', name: 'TakeExam', component: () => import('@/views/student/ExamTake.vue') },
      { path: 'results', name: 'MyResults', component: () => import('@/views/student/MyResults.vue') },
      { path: 'results/:id', name: 'ResultDetail', component: () => import('@/views/student/ResultDetail.vue') },
    ],
  },
  {
    path: '/teacher',
    component: () => import('@/layouts/TeacherLayout.vue'),
    meta: { requiresAuth: true, role: 'teacher' },
    children: [
      { path: '', name: 'TeacherHome', component: () => import('@/views/teacher/Dashboard.vue') },
      { path: 'students', name: 'Students', component: () => import('@/views/teacher/Students.vue') },
      { path: 'exams', name: 'Exams', component: () => import('@/views/teacher/Exams.vue') },
      { path: 'exams/create', name: 'ExamCreate', component: () => import('@/views/teacher/ExamEdit.vue') },
      { path: 'exams/:id/edit', name: 'ExamEdit', component: () => import('@/views/teacher/ExamEdit.vue') },
      { path: 'exams/:id/stats', name: 'ExamStats', component: () => import('@/views/teacher/ExamStats.vue') },
      { path: 'exams/:id/results', name: 'ExamResults', component: () => import('@/views/teacher/ExamResults.vue') },
    ],
  },
  {
    path: '/',
    redirect: '/login',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || 'null')

  if (to.meta.guest && token) {
    return next(user?.role === 'teacher' ? '/teacher' : '/student')
  }
  if (to.meta.requiresAuth && !token) {
    return next('/login')
  }
  if (to.meta.role && user?.role !== to.meta.role) {
    return next(user?.role === 'teacher' ? '/teacher' : '/student')
  }
  next()
})

export default router
