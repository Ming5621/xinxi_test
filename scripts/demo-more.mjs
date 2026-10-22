import { chromium } from 'playwright'
import { mkdir } from 'fs/promises'

const BASE = 'http://localhost:8000'
const OUT = '/opt/cursor/artifacts/screenshots'

await mkdir(OUT, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

async function teacherLogin(username, password) {
  await page.goto(`${BASE}/login`)
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.waitForLoadState('networkidle')
  await page.locator('button.mode-btn', { hasText: '教师' }).click()
  await page.locator('input').first().fill(username)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button').filter({ hasText: '登' }).click()
  await page.waitForTimeout(1200)
}

async function studentLogin(name) {
  await page.goto(`${BASE}/login`)
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.waitForLoadState('networkidle')
  await page.locator('input').first().fill(name)
  await page.locator('button').filter({ hasText: '进入系统' }).click()
  await page.waitForTimeout(1200)
}

await teacherLogin('teacher1', 'teacher123')
await page.locator('.el-menu-item').filter({ hasText: '考试管理' }).click()
await page.waitForTimeout(800)
await page.locator('button:has-text("统计")').first().click()
await page.waitForTimeout(1000)
await page.screenshot({ path: `${OUT}/05-teacher-stats.png`, fullPage: true })
console.log('✓ 05-teacher-stats.png')

await page.locator('.el-menu-item').filter({ hasText: '考试管理' }).click()
await page.waitForTimeout(500)
await page.locator('button:has-text("编辑")').first().click()
await page.waitForTimeout(1000)
await page.screenshot({ path: `${OUT}/09-teacher-exam-edit.png`, fullPage: true })
console.log('✓ 09-teacher-exam-edit.png')

await studentLogin('演示学生')
await page.waitForURL('**/student**')
await page.waitForTimeout(1000)
await page.screenshot({ path: `${OUT}/06-student-dashboard.png`, fullPage: true })
console.log('✓ 06-student-dashboard.png')

await page.locator('.nav-item').filter({ hasText: '打字练习' }).click()
await page.waitForTimeout(1000)
await page.screenshot({ path: `${OUT}/07-student-typing.png`, fullPage: true })
console.log('✓ 07-student-typing.png')

const startBtn = page.locator('button:has-text("开始考试")')
if (await startBtn.count()) {
  await page.locator('.nav-item').filter({ hasText: '考试大厅' }).click()
  await page.waitForTimeout(500)
  await startBtn.first().click()
  await page.locator('button:has-text("开始答题")').click({ timeout: 5000 }).catch(() => {})
  await page.waitForTimeout(1000)
  await page.screenshot({ path: `${OUT}/08-student-exam.png`, fullPage: true })
  console.log('✓ 08-student-exam.png')
}

await browser.close()
console.log('done')
