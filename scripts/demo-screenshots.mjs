import { chromium } from 'playwright'
import { mkdir } from 'fs/promises'

const BASE = 'http://localhost:8000'
const OUT = '/opt/cursor/artifacts/screenshots'

async function shot(page, name) {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  console.log(`✓ ${name}.png`)
}

async function login(page, username, password) {
  await page.goto(`${BASE}/login`)
  await page.waitForLoadState('networkidle')
  await page.fill('input[placeholder="用户名"]', username)
  await page.fill('input[placeholder="密码"]', password)
  await page.click('button:has-text("登")')
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(800)
}

await mkdir(OUT, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

// 1. 登录页
await page.goto(`${BASE}/login`)
await page.waitForLoadState('networkidle')
await shot(page, '01-login')

// 2. 教师端
await login(page, 'teacher', 'teacher123')
await shot(page, '02-teacher-dashboard')

await page.click('text=学生管理')
await page.waitForLoadState('networkidle')
await page.waitForTimeout(500)
await shot(page, '03-teacher-students')

await page.click('text=考试管理')
await page.waitForLoadState('networkidle')
await page.waitForTimeout(500)
await shot(page, '04-teacher-exams')

await page.click('text=统计', { timeout: 3000 }).catch(() => {})
const statsBtn = page.locator('button:has-text("统计")').first()
if (await statsBtn.count()) {
  await statsBtn.click()
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(800)
  await shot(page, '05-teacher-stats')
}

// 3. 学生端
await page.goto(`${BASE}/login`)
await login(page, 'student01', '123456')
await shot(page, '06-student-dashboard')

await page.click('text=我的成绩')
await page.waitForLoadState('networkidle')
await page.waitForTimeout(500)
await shot(page, '07-student-results')

await browser.close()
console.log('Done')
