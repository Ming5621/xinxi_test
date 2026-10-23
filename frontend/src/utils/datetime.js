/**
 * 将后端返回的时间格式化为本地可读字符串。
 * 后端按 UTC 存储；带 Z / 时区偏移的 ISO 字符串可直接解析。
 * 无时区的旧数据按 UTC 处理，避免被当成浏览器本地时间（中国会慢约 8 小时）。
 */
export function formatDateTime(value, fallback = '—') {
  if (!value) return fallback
  const date = parseApiDate(value)
  if (!date) return fallback
  return date.toLocaleString('zh-CN')
}

export function parseApiDate(value) {
  if (!value) return null
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  if (typeof value !== 'string') {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? null : date
  }

  const raw = value.trim()
  if (!raw) return null

  let normalized = raw
  // 无时区标记的 datetime 按 UTC 解析
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(raw) && !/(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(raw)) {
    normalized = `${raw}Z`
  }

  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}
