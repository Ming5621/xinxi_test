import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const BASE = 'http://localhost:8000'
async function request(path, token, data, method = 'POST') {
  const response = await fetch(`${BASE}/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
  })
  const body = await response.json()
  assert.ok(response.ok, `${path}: ${response.status} ${JSON.stringify(body)}`)
  return body
}
const teacher = await request('/auth/login', null, { username: 'teacher1', password: 'teacher123' })
const suffix = Date.now()
const accounts = []
async function student(name) {
  const user = await request('/users', teacher.access_token, { username: `typing_${suffix}_${accounts.length}`, name, class_name: '课堂' })
  accounts.push(user.id)
  const challenge = await request('/auth/student-login', null, { username: name, class_name: '课堂', password: '123456' })
  return request('/auth/student-password', challenge.password_change_token, { new_password: 'typing-regression-pass' })
}
const first = await student(`打字回归甲${suffix}`)
const second = await student(`打字回归乙${suffix}`)
const exam = await request('/exams', teacher.access_token, {
  title: `打字状态回归${suffix}`,
  questions: [
    { type: 'typing', content: '第一道打字题的内容', options: { time_limit: 2 }, score: 10 },
    { type: 'typing', content: '第二道打字题的内容', options: { time_limit: 120 }, score: 10 },
    { type: 'judge', content: '确认答案', correct_answer: '正确', score: 10 },
  ],
})
await request(`/exams/${exam.id}/publish`, teacher.access_token)
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage()
const errors = []
page.on('pageerror', error => errors.push(error.message))
let checks = 0
function check(name, condition) {
  assert.ok(condition, name)
  checks++
  console.log(`  ✓ ${name}`)
}
async function applySession(session) {
  await page.goto(`${BASE}/login`)
  await page.evaluate(session => {
    localStorage.setItem('token', session.access_token)
    localStorage.setItem('user', JSON.stringify(session.user))
  }, session)
  await page.goto(`${BASE}/student/exam/${exam.id}`)
  await page.locator('.sheet-item').first().waitFor()
}
async function go(index) {
  await page.locator('.sheet-item').nth(index).click()
}
const input = () => page.locator('textarea.input-box:visible')
const start = () => page.getByRole('button', { name: '开始', exact: true }).filter({ visible: true }).click()
try {
  console.log('多题打字与草稿回归测试')
  await applySession(first)
  await start()
  await input().fill('第一道')
  await page.waitForFunction(() => document.querySelector('textarea.input-box').disabled)
  await go(1)
  check('上一道题完成后，下一道打字题仍可独立开始', await input().inputValue() === '' && await startButtonVisible())
  await start()
  await input().fill('第二道打字')
  await go(2)
  await go(1)
  check('切换普通题后保留未完成打字输入', await input().inputValue() === '第二道打字' && await input().isEnabled())
  await go(0)
  check('返回已完成打字题仍保持锁定和原文', await input().isDisabled() && await input().inputValue() === '第一道')
  await go(1)
  await page.waitForTimeout(1500)
  const speed = () => page.locator('.status-bar:visible span').first().textContent().then(text => parseFloat(text))
  const before = await speed()
  await page.waitForTimeout(1200)
  check('未继续输入时实时速度仍随计时更新', await speed() < before)
  await page.reload()
  await page.locator('.sheet-item').first().waitFor()
  check('刷新恢复未完成输入与计时状态', await input().inputValue() === '第二道打字' && await input().isEnabled())
  await go(0)
  check('刷新后已完成打字题仍不可重做', await input().isDisabled() && await input().inputValue() === '第一道')
  await applySession(second)
  check('同一浏览器切换学生不会读到他人草稿', await input().inputValue() === '' && await input().isDisabled())
  await applySession(first)
  await go(2)
  await page.locator('.judge-option').filter({ hasText: '正确' }).click()
  await page.getByRole('button', { name: '提交试卷' }).click()
  await page.getByRole('button', { name: '确认提交', exact: true }).click()
  await page.waitForURL('**/student/results')
  const sessions = await request('/exams/sessions/my', first.access_token, undefined, 'GET')
  const session = sessions.find(row => row.exam_id === exam.id)
  const detail = await request(`/exams/sessions/${session.id}`, first.access_token, undefined, 'GET')
  check('交卷收齐已完成和进行中的打字答案', detail.answers[0].student_answer === '第一道' && detail.answers[1].student_answer === '第二道打字')
  check('交卷补齐进行中打字题的评分元数据', detail.answers[1].answer_meta.duration_seconds > 0)
  await page.evaluate(session => {
    localStorage.setItem('token', session.access_token)
    localStorage.setItem('user', JSON.stringify(session.user))
  }, teacher)
  await page.goto(`${BASE}/teacher/exams/${exam.id}/edit`)
  await page.getByText('已有学生开始考试，题目、时长与及格分已锁定，仍可修改名称和说明。', { exact: true }).waitFor()
  check('已有答卷的试卷在编辑页锁定题目', await page.locator('fieldset').evaluate(el => el.disabled))
  await page.locator('.el-form-item').filter({ hasText: '考试名称' }).locator('input').fill(`修改名称${suffix}`)
  await page.getByRole('button', { name: '保存修改', exact: true }).click()
  await page.waitForURL('**/teacher/exams')
  const updated = await request(`/exams/${exam.id}`, teacher.access_token, undefined, 'GET')
  check('锁定试卷仍可通过界面修改名称', updated.title === `修改名称${suffix}`)
  const text = await request('/typing/texts', teacher.access_token, { title: `课堂时长回归${suffix}`, content: '课堂测试使用教师指定的文章', time_limit: 30 })
  const classTest = await request('/typing/sessions', teacher.access_token, { text_id: text.id, class_name: '课堂', duration_seconds: 2 })
  await request(`/typing/sessions/${classTest.id}/start`, teacher.access_token)
  await page.evaluate(session => {
    localStorage.setItem('token', session.access_token)
    localStorage.setItem('user', JSON.stringify(session.user))
  }, first)
  await page.goto(`${BASE}/student/typing`)
  await page.getByRole('button', { name: '立即参加', exact: true }).click()
  await page.getByRole('button', { name: '开始打字', exact: true }).click()
  await page.getByRole('button', { name: '开始', exact: true }).click()
  await input().fill('课堂测试')
  await page.locator('.score-card').waitFor({ timeout: 8000 })
  const records = await request('/typing/records/my', first.access_token, undefined, 'GET')
  const record = records.find(row => row.text_id === text.id)
  check('课堂测试按教师设置的时长结束并提交', record?.duration_seconds === 2 && record.source === 'class_test')
  await request(`/typing/sessions/${classTest.id}/end`, teacher.access_token)
  await request(`/typing/texts/${text.id}`, teacher.access_token, undefined, 'DELETE')
  check('页面无 JavaScript 异常', errors.length === 0)
  console.log(`结果: ${checks} 通过, 0 失败`)
} finally {
  await browser.close()
  await request(`/exams/${exam.id}`, teacher.access_token, undefined, 'DELETE')
  for (const id of accounts) await request(`/users/${id}`, teacher.access_token, undefined, 'DELETE')
}
async function startButtonVisible() {
  return page.getByRole('button', { name: '开始', exact: true }).filter({ visible: true }).isVisible()
}
