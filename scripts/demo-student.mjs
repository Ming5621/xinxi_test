import { chromium } from 'playwright'
import { mkdir } from 'fs/promises'

const BASE = 'http://localhost:8000'
const OUT = '/opt/cursor/artifacts/screenshots'

await mkdir(OUT, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

await page.goto(`${BASE}/login`)
await page.waitForLoadState('networkidle')
await page.locator('input').first().fill('student01')
await page.locator('input[type="password"]').fill('123456')
await page.locator('button').filter({ hasText: '登' }).click()
await page.waitForURL('**/student**', { timeout: 10000 })
await page.waitForTimeout(1000)
await page.screenshot({ path: `${OUT}/06-student-dashboard.png`, fullPage: true })
console.log('✓ 06-student-dashboard.png')

await page.locator('text=我的成绩').click()
await page.waitForTimeout(1000)
await page.screenshot({ path: `${OUT}/07-student-results.png`, fullPage: true })
console.log('✓ 07-student-results.png')

// 开始考试
await page.locator('text=考试大厅').click()
await page.waitForTimeout(800)
const startBtn = page.locator('button:has-text("开始考试")')
if (await startBtn.count()) {
  await startBtn.click()
  await page.locator('button:has-text("开始答题")').click({ timeout: 5000 }).catch(() => {})
  await page.waitForTimeout(1000)
  await page.screenshot({ path: `${OUT}/08-student-exam.png`, fullPage: true })
  console.log('✓ 08-student-exam.png')
}

await browser.close()
