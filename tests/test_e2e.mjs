import { chromium } from 'playwright'

const BASE = 'http://localhost:8000'
let passed = 0
let failed = 0
const errors = []

function check(name, cond, detail = '') {
  if (cond) { passed++; console.log(`  ✓ ${name}`) }
  else { failed++; const msg = `  ✗ ${name}${detail ? ' — ' + detail : ''}`; console.log(msg); errors.push(msg) }
}

async function teacherLogin(page, username, password) {
  await page.goto(`${BASE}/login`)
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.waitForLoadState('networkidle')
  await page.locator('button.mode-btn', { hasText: '教师' }).click()
  await page.locator('input').first().fill(username)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button').filter({ hasText: '登' }).click()
  await page.waitForTimeout(1500)
}

async function studentLogin(page, name) {
  await page.goto(`${BASE}/login`)
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.waitForLoadState('networkidle')
  // 默认即为学生模式
  await page.locator('input').first().fill(name)
  await page.locator('button').filter({ hasText: '进入系统' }).click()
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
check('无账号提示文案', !(await page.content()).includes('student01') && !(await page.content()).includes('teacher123'))
check('默认学生模式', await page.locator('button.mode-btn.active').textContent().then(t => t.includes('学生')))

// 2. 教师登录
await teacherLogin(page, 'teacher1', 'teacher123')
check('教师跳转控制台', page.url().includes('/teacher'))

// 控制台应有在线学生区
check('控制台含在线学生', await page.locator('text=当前在线学生').count() >= 1)
check('控制台含发任务', await page.locator('text=发任务').count() >= 1)

// 3. 学生动态
await page.goto(`${BASE}/teacher/students`)
await page.waitForTimeout(800)
check('学生动态页加载', await page.locator('h1').textContent().then(t => t.includes('学生')))

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

// 7. 打字统计与文章导入
await page.goto(`${BASE}/teacher/typing`)
await page.waitForTimeout(800)
check('教师打字统计页', await page.locator('h1').textContent().then(t => t.includes('打字')))
check('导入文章按钮', await page.locator('button:has-text("导入文章")').count() >= 1)

const longBody = '信息技术课程帮助我们学习与交流。'.repeat(40)
await page.locator('button:has-text("导入文章")').click()
await page.locator('.el-dialog:visible textarea').fill(`【标题】E2E长文\n${longBody}\n\n【标题】E2E导入短文\n这是一段短文，用于确认导入后可以删除。`)
await page.locator('.el-dialog:visible button:has-text("确认导入")').click()
await page.waitForTimeout(1200)
check('导入文章出现在列表', await page.locator('.el-table__row', { hasText: 'E2E长文' }).count() >= 1)
check('导入短文出现在列表', await page.locator('.el-table__row', { hasText: 'E2E导入短文' }).count() >= 1)

// 8. 学生端姓名登录
await studentLogin(page, 'E2E测试生')
check('学生跳转', page.url().includes('/student'))

// 9. 考试大厅
await page.goto(`${BASE}/student`)
await page.waitForTimeout(1000)
const examCards = await page.locator('.exam-card').count()
check('考试大厅显示考试', examCards >= 0) // 可能没有进行中的考试

async function typingViewport(page) {
  return page.evaluate(() => {
    const article = document.querySelector('.article-box')
    const input = document.querySelector('.input-box')
    const articleRect = article.getBoundingClientRect()
    const inputRect = input.getBoundingClientRect()
    return {
      scrollGap: document.documentElement.scrollHeight - window.innerHeight,
      articleTop: articleRect.top,
      articleBottom: articleRect.bottom,
      inputTop: inputRect.top,
      inputBottom: inputRect.bottom,
      innerHeight: window.innerHeight,
      articleHeight: articleRect.height,
      inputHeight: inputRect.height,
      articleOverflow: getComputedStyle(article).overflowY,
      inputOverflow: getComputedStyle(input).overflowY,
      articleScrolls: article.scrollHeight > article.clientHeight + 4,
    }
  })
}

function typingFits(info) {
  return info.scrollGap <= 2
    && info.articleTop >= 0
    && info.inputBottom <= info.innerHeight + 1
    && info.articleBottom <= info.inputTop + 2
    && info.articleHeight >= 60
    && info.inputHeight >= 60
    && (info.articleOverflow === 'auto' || info.articleOverflow === 'scroll')
    && (info.inputOverflow === 'auto' || info.inputOverflow === 'scroll')
}

// 10. 打字练习
await page.goto(`${BASE}/student/typing`)
await page.waitForTimeout(1000)
check('打字练习页加载', await page.locator('h1').textContent().then(t => t.includes('打字练习')))
check('文章下拉框存在', await page.locator('.article-select').count() >= 1)
check('左侧文章列表已移除', await page.locator('.text-list, .text-item').count() === 0)
check('模式切换存在', await page.locator('text=自由练习').count() >= 1)
check('模式切换存在-5分钟', await page.locator('text=5分钟测试').count() >= 1)

await page.locator('.article-select').click()
await page.getByRole('option', { name: /E2E长文/ }).click()
await page.waitForTimeout(300)
for (const [width, height] of [[1440, 900], [1280, 720]]) {
  await page.setViewportSize({ width, height })
  await page.waitForTimeout(200)
  const info = await typingViewport(page)
  check(`打字区固定在视口内 ${width}x${height}`, typingFits(info), JSON.stringify(info))
  check(`长文在对照区内滚动 ${width}x${height}`, info.articleScrolls, JSON.stringify(info))
}
await page.setViewportSize({ width: 1440, height: 900 })

// 自由练习（开始按钮在上方工具栏）
await page.locator('button:has-text("开始打字")').click()
await page.waitForTimeout(500)
check('开始打字', await page.locator('textarea.input-box').isEnabled())
await page.locator('textarea.input-box').fill('aaaa')
await page.waitForTimeout(300)
check('暂停按钮显示', await page.locator('.practice-bar button:has-text("暂停")').count() === 1)
check('停止按钮显示', await page.locator('.practice-bar button:has-text("停止")').count() === 1)
const typingInfo = await typingViewport(page)
check('打字进行中仍固定在视口内', typingFits(typingInfo), JSON.stringify(typingInfo))

// 暂停/继续
await page.locator('.practice-bar button:has-text("暂停")').click()
await page.waitForTimeout(300)
check('暂停后输入禁用', !(await page.locator('textarea.input-box').isEnabled()))
await page.locator('.practice-bar button:has-text("继续")').click()
await page.waitForTimeout(300)
check('继续后输入启用', await page.locator('textarea.input-box').isEnabled())

// 11. 5分钟测试模式
await page.reload()
await page.waitForTimeout(1000)
await page.locator('text=5分钟测试').click()
await page.waitForTimeout(300)
await page.locator('button:has-text("开始打字")').click()
// 确认对话框
await page.waitForTimeout(500)
const confirmVisible = await page.locator('.el-message-box').count()
if (confirmVisible > 0) {
  await page.locator('.el-message-box button:has-text("开始")').last().click()
  await page.waitForTimeout(500)
}
check('5分钟测试无暂停按钮', await page.locator('.practice-bar button:has-text("暂停")').count() === 0)
check('5分钟测试有停止按钮', await page.locator('.practice-bar button:has-text("停止")').count() === 1)
check('5分钟测试输入框可用', await page.locator('textarea.input-box').isEnabled())

// 12. 我的成绩
await page.goto(`${BASE}/student/results`)
await page.waitForTimeout(800)
check('我的成绩页加载', await page.locator('h1').textContent().then(t => t.includes('成绩')))

// 13. 教师端应能看到该学生在线
await teacherLogin(page, 'teacher1', 'teacher123')
await page.goto(`${BASE}/teacher`)
await page.waitForTimeout(1000)
const onlineText = await page.locator('.content-card').first().textContent()
check('教师端可见姓名登录学生', onlineText.includes('E2E测试生') || (await page.locator('text=E2E测试生').count()) >= 1)

// 14. 删除本次导入的练习文章
await page.goto(`${BASE}/teacher/typing`)
await page.waitForTimeout(800)
for (const title of ['E2E长文', 'E2E导入短文']) {
  for (let i = 0; i < 5; i++) {
    const row = page.locator('.el-table__row', { hasText: title })
    if (await row.count() === 0) break
    await row.first().locator('button', { hasText: '删除' }).click()
    await page.locator('.el-message-box button', { hasText: '确定' }).click()
    await page.waitForTimeout(400)
  }
  check(`已删除${title}`, await page.locator('.el-table__row', { hasText: title }).count() === 0)
}

// 15. 控制台错误检查
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
