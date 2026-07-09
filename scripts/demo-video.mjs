import { chromium } from 'playwright'
import { mkdir, rename } from 'fs/promises'
import { readdir } from 'fs/promises'
import { join } from 'path'

const BASE = 'http://localhost:8000'
const OUT = '/opt/cursor/artifacts/videos'
const VIDEO_NAME = 'exam-system-usage-demo.webm'

async function pause(page, ms = 1500) {
  await page.waitForTimeout(ms)
}

async function login(page, username, password) {
  await page.goto(`${BASE}/login`)
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.waitForLoadState('networkidle')
  await page.locator('input').first().fill(username)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button').filter({ hasText: '登' }).click()
  await page.waitForLoadState('networkidle')
  await pause(page, 1200)
}

await mkdir(OUT, { recursive: true })

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: {
    dir: OUT,
    size: { width: 1440, height: 900 },
  },
})
const page = await context.newPage()

console.log('开始录制使用演示视频...')

// 1. 登录页
await page.goto(`${BASE}/login`)
await page.waitForLoadState('networkidle')
await pause(page, 2000)

// 2. 教师端
await login(page, 'teacher', 'teacher123')
await pause(page, 1500)

await page.locator('.el-menu-item').filter({ hasText: '学生管理' }).click()
await page.waitForLoadState('networkidle')
await pause(page, 2000)

await page.locator('.el-menu-item').filter({ hasText: '考试管理' }).click()
await page.waitForLoadState('networkidle')
await pause(page, 2000)

const statsBtn = page.locator('button:has-text("统计")').first()
if (await statsBtn.count()) {
  await statsBtn.click()
  await page.waitForLoadState('networkidle')
  await pause(page, 2000)
}

// 3. 学生端
await login(page, 'student01', '123456')
await page.waitForURL('**/student**', { timeout: 10000 })
await pause(page, 1500)

await page.locator('.nav-item').filter({ hasText: '考试大厅' }).click()
await page.waitForLoadState('networkidle')
await pause(page, 1500)

const startBtn = page.locator('button:has-text("开始考试")')
if (await startBtn.count()) {
  await startBtn.first().click()
  await page.locator('button:has-text("开始答题")').click({ timeout: 5000 }).catch(() => {})
  await pause(page, 2500)
}

await page.locator('.nav-item').filter({ hasText: '打字练习' }).click()
await page.waitForLoadState('networkidle')
await pause(page, 1500)

const typingStart = page.locator('button:has-text("开始")').first()
if (await typingStart.count()) {
  await typingStart.click()
  await pause(page, 800)
  await page.locator('textarea.input-box').fill('信息技术改变生活')
  await pause(page, 2000)
}

await page.locator('.nav-item').filter({ hasText: '我的成绩' }).click()
await page.waitForLoadState('networkidle')
await pause(page, 2000)

await context.close()
await browser.close()

const files = await readdir(OUT)
const webm = files.find((f) => f.endsWith('.webm') && f !== VIDEO_NAME)
if (webm) {
  await rename(join(OUT, webm), join(OUT, VIDEO_NAME))
}

console.log(`✓ 视频已保存: ${join(OUT, VIDEO_NAME)}`)
