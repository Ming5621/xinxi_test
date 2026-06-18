import { createRouter, createWebHistory } from 'vue-router'

function homePath(role) {
  if (role === 'admin') return '/admin'
  if (role === 'teacher') return '/teacher'
  return '/student'
}

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
    meta: { requiresAuth: true, roles: ['student'] },
    children: [
      { path: '', name: 'StudentHome', component: () => import('@/views/student/Dashboard.vue') },
      { path: 'exam/:id', name: 'TakeExam', component: () => import('@/views/student/ExamTake.vue') },
      { path: 'results', name: 'MyResults', component: () => import('@/views/student/MyResults.vue') },
      { path: 'results/:id', name: 'ResultDetail', component: () => import('@/views/student/ResultDetail.vue') },
      { path: 'typing', name: 'TypingPractice', component: () => import('@/views/student/TypingPractice.vue') },
    ],
  },
  {
    path: '/teacher',
    component: () => import('@/layouts/TeacherLayout.vue'),
    meta: { requiresAuth: true, roles: ['teacher', 'admin'] },
    children: [
      { path: '', name: 'TeacherHome', component: () => import('@/views/teacher/Dashboard.vue') },
      { path: 'students', name: 'Students', component: () => import('@/views/teacher/Students.vue') },
      { path: 'exams', name: 'Exams', component: () => import('@/views/teacher/Exams.vue') },
      { path: 'exams/create', name: 'ExamCreate', component: () => import('@/views/teacher/ExamEdit.vue') },
      { path: 'exams/:id/edit', name: 'ExamEdit', component: () => import('@/views/teacher/ExamEdit.vue') },
      { path: 'exams/:id/stats', name: 'ExamStats', component: () => import('@/views/teacher/ExamStats.vue') },
      { path: 'exams/:id/results', name: 'ExamResults', component: () => import('@/views/teacher/ExamResults.vue') },
      { path: 'typing', name: 'TypingStats', component: () => import('@/views/teacher/TypingStats.vue') },
      { path: 'typing/class-test', name: 'TypingClassTest', component: () => import('@/views/teacher/TypingClassTest.vue') },
    ],
  },
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, roles: ['admin'] },
    children: [
      { path: '', name: 'AdminHome', component: () => import('@/views/admin/Teachers.vue') },
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
    return next(homePath(user?.role))
  }
  if (to.meta.requiresAuth && !token) {
    return next('/login')
  }
  if (to.meta.roles && user && !to.meta.roles.includes(user.role)) {
    return next(homePath(user.role))
  }
  next()
})

export default router
