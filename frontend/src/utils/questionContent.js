// Only images and fenced code are interpreted. HTML is always rendered as text.
export function parseQuestionContent(value = '') {
  const parts = []
  const pattern = /```([^\n`]*)\n([\s\S]*?)```|!\[([^\]\n]*)\]\((data:image\/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]+)\)/g
  const text = String(value)
  let cursor = 0
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) parts.push({ type: 'text', text: text.slice(cursor, match.index) })
    if (match[2] !== undefined) parts.push({ type: 'code', language: match[1].trim(), text: match[2].replace(/\n$/, '') })
    else parts.push({ type: 'image', alt: match[3], src: match[4] })
    cursor = match.index + match[0].length
  }
  if (cursor < text.length) parts.push({ type: 'text', text: text.slice(cursor) })
  return parts
}
