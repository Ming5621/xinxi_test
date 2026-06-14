import { chromium } from 'playwright'
import { mkdir } from 'fs/promises'

const BASE = 'http://localhost:8000'
const OUT = '/opt/cursor/artifacts/screenshots'

await mkdir(OUT, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

async function login(username, password) {
  await page.goto(`${BASE}/login`)
  await page.waitForLoadState('networkidle')
  await page.locator('input').first().fill(username)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button').filter({ hasText: '登' }).click()
  await page.waitForTimeout(1200)
}

await login('teacher', 'teacher123')
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

await login('student01', '123456')
await page.waitForURL('**/student**')
await page.waitForTimeout(1000)
await page.screenshot({ path: `${OUT}/06-student-dashboard.png`, fullPage: true })
console.log('✓ 06-student-dashboard.png')

const startBtn = page.locator('button:has-text("开始考试")')
if (await startBtn.count()) {
  await startBtn.click()
  await page.locator('button:has-text("开始答题")').click({ timeout: 5000 })
  await page.waitForTimeout(1200)
  await page.screenshot({ path: `${OUT}/08-student-exam.png`, fullPage: true })
  console.log('✓ 08-student-exam.png')
}

await browser.close()
