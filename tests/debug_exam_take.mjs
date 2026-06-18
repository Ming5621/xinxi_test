import { chromium } from 'playwright'

const BASE = 'http://localhost:8000'

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

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

const errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })

await login(page, 'teacher', 'teacher123')
await page.goto(`${BASE}/teacher/exams`)
await page.waitForTimeout(800)

// publish draft if needed
const publishBtn = page.locator('button:has-text("发布")').first()
if (await publishBtn.count()) {
  await publishBtn.click()
  await page.waitForTimeout(500)
  const confirm = page.locator('.el-message-box button:has-text("确定"), .el-message-box button:has-text("发布")')
  if (await confirm.count()) await confirm.first().click()
  await page.waitForTimeout(800)
}

await login(page, 'student03', '123456')
await page.goto(`${BASE}/student`)
await page.waitForTimeout(1000)

const startBtn = page.locator('button:has-text("开始考试")').first()
console.log('start buttons', await startBtn.count())
if (await startBtn.count()) {
  await startBtn.click()
  await page.waitForTimeout(500)
  await page.locator('.el-message-box button:has-text("开始答题")').click()
  await page.waitForTimeout(2000)
}

console.log('url', page.url())
console.log('question content visible', await page.locator('.question-content').count())
console.log('typing visible', await page.locator('.typing-hint').count())
console.log('question card', await page.locator('.question-card').count())
console.log('progress text', await page.locator('.question-progress').textContent().catch(() => 'none'))
console.log('errors', errors)

await page.screenshot({ path: '/opt/cursor/artifacts/screenshots/exam-take-debug.png' })
await browser.close()
