import assert from 'node:assert/strict'
import { parseQuestionContent } from '../frontend/src/utils/questionContent.js'

const parts = parseQuestionContent('题目\n```python\nif True:\n    print("你好")\n```\n![图片](data:image/png;base64,YQ==)')
assert.equal(parts.find(p => p.type === 'code').text, 'if True:\n    print("你好")')
assert.equal(parts.find(p => p.type === 'image').src, 'data:image/png;base64,YQ==')
for (const unsafe of ['<img src=x onerror=alert(1)>', '![x](javascript:alert(1))', '![x](data:image/svg+xml;base64,YQ==)']) {
  assert.deepEqual(parseQuestionContent(unsafe), [{ type: 'text', text: unsafe }])
}
assert.equal(parseQuestionContent('```html\n![x](data:image/png;base64,YQ==)\n```')[0].type, 'code')
assert.deepEqual(parseQuestionContent('旧题目\n保持换行'), [{ type: 'text', text: '旧题目\n保持换行' }])
console.log('Rich content parsing checks passed')
