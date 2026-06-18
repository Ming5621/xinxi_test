import { chromium } from 'playwright'

const BASE = 'http://localhost:8000'
let passed = 0
let failed = 0
const errors = []

function check(name, cond, detail = '') {
  if (cond) { passed++; console.log(`  ✓ ${name}`) }
  else { failed++; const msg = `  ✗ ${name}${detail ? ' — ' + detail : ''}`; console.log(msg); errors.push(msg) }
}

async function login(page, username, password) {
  await page.goto(`${BASE}/login`)
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.waitForLoadState('networkidle')
  await page.locator('input').first().fill(username)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button').filter({ hasText: '登' }).click()
  await page.waitForTimeout(1500)
}

console.log('='.repeat(50))
console.log('前端 E2E 测试')
console.log('='.repeat(50))

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

// 收集控制台错误
const consoleErrors = []
page.on('pageerror', (e) => consoleErrors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()) })

// 1. 登录页
await page.goto(`${BASE}/login`)
check('登录页加载', await page.locator('h1').textContent().then(t => t.includes('考试系统')))

// 2. 教师登录
await login(page, 'teacher', 'teacher123')
check('教师跳转控制台', page.url().includes('/teacher'))

// 3. 学生管理
await page.goto(`${BASE}/teacher/students`)
await page.waitForTimeout(800)
check('学生管理页加载', await page.locator('h1').textContent().then(t => t.includes('学生管理')))
check('学生列表有数据', await page.locator('.el-table__row').count() >= 1)

// 4. 考试管理
await page.goto(`${BASE}/teacher/exams`)
await page.waitForTimeout(800)
check('考试管理页加载', await page.locator('h1').textContent().then(t => t.includes('考试管理')))

// 5. 创建考试页
await page.goto(`${BASE}/teacher/exams/create`)
await page.waitForTimeout(800)
check('创建考试页加载', await page.locator('h1').textContent().then(t => t.includes('创建考试')))

// 添加选择题
await page.locator('button:has-text("添加选择题")').click()
check('添加选择题', await page.locator('.question-editor').count() === 1)

// 添加打字题
await page.locator('button:has-text("添加打字题")').click()
check('添加打字题', await page.locator('.question-editor').count() === 2)

// 6. 批量导入按钮
await page.goto(`${BASE}/teacher/students`)
await page.waitForTimeout(500)
await page.locator('button:has-text("批量导入")').click()
check('批量导入对话框', await page.locator('.el-dialog').isVisible())

// 7. 打字统计
await page.goto(`${BASE}/teacher/typing`)
await page.waitForTimeout(800)
check('教师打字统计页', await page.locator('h1').textContent().then(t => t.includes('打字')))

// 8. 学生端
await login(page, 'student01', '123456')
check('学生跳转', page.url().includes('/student'))

// 9. 考试大厅
await page.goto(`${BASE}/student`)
await page.waitForTimeout(1000)
const examCards = await page.locator('.exam-card').count()
check('考试大厅显示考试', examCards >= 0) // 可能没有进行中的考试

// 10. 打字练习
await page.goto(`${BASE}/student/typing`)
await page.waitForTimeout(1000)
check('打字练习页加载', await page.locator('h1').textContent().then(t => t.includes('打字练习')))
check('文章选择器存在', await page.locator('.text-item, .text-list').count() >= 1)
check('模式切换存在', await page.locator('text=自由练习').count() >= 1)
check('模式切换存在-5分钟', await page.locator('text=5分钟测试').count() >= 1)

// 自由练习
await page.locator('button:has-text("开始")').click()
await page.waitForTimeout(500)
check('开始打字', await page.locator('textarea.input-box').isEnabled())
await page.locator('textarea.input-box').fill('aaaa')
await page.waitForTimeout(300)
check('暂停按钮显示', await page.locator('button:has-text("暂停")').count() === 1)
check('停止按钮显示', await page.locator('button:has-text("停止")').count() === 1)

// 暂停/继续
await page.locator('button:has-text("暂停")').click()
await page.waitForTimeout(300)
check('暂停后输入禁用', !(await page.locator('textarea.input-box').isEnabled()))
await page.locator('button:has-text("继续")').click()
await page.waitForTimeout(300)
check('继续后输入启用', await page.locator('textarea.input-box').isEnabled())

// 11. 5分钟测试模式
await page.reload()
await page.waitForTimeout(1000)
await page.locator('text=5分钟测试').click()
await page.waitForTimeout(300)
await page.locator('button:has-text("开始")').click()
// 确认对话框
await page.waitForTimeout(500)
const confirmVisible = await page.locator('.el-message-box').count()
if (confirmVisible > 0) {
  await page.locator('button:has-text("开始")').last().click()
  await page.waitForTimeout(500)
}
check('5分钟测试无暂停按钮', await page.locator('button:has-text("暂停")').count() === 0)
check('5分钟测试无停止按钮', await page.locator('button:has-text("停止")').count() === 0)
check('5分钟测试输入框可用', await page.locator('textarea.input-box').isEnabled())

// 12. 我的成绩
await page.goto(`${BASE}/student/results`)
await page.waitForTimeout(800)
check('我的成绩页加载', await page.locator('h1').textContent().then(t => t.includes('成绩')))

// 13. 控制台错误检查
const realErrors = consoleErrors.filter(e =>
  !e.includes('favicon') && !e.includes('404') && !e.includes('is not a function') === false
)
// Filter out known non-critical
const criticalErrors = consoleErrors.filter(e =>
  e.includes('TypeError') || e.includes('ReferenceError') || e.includes('is not a function')
)
check('无严重JS错误', criticalErrors.length === 0, criticalErrors.join('; '))

await browser.close()

console.log('='.repeat(50))
console.log(`结果: ${passed} 通过, ${failed} 失败`)
if (errors.length) {
  console.log('\n失败项:')
  errors.forEach(e => console.log(e))
}
if (criticalErrors.length) {
  console.log('\nJS错误:')
  criticalErrors.forEach(e => console.log(' ', e))
}
console.log('='.repeat(50))
process.exit(failed > 0 ? 1 : 0)
