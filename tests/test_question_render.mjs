import { createServer } from '../frontend/node_modules/vite/dist/node/index.js'
import { createSSRApp } from '../frontend/node_modules/vue/dist/vue.runtime.esm-bundler.js'
import { renderToString } from '../frontend/node_modules/@vue/server-renderer/dist/server-renderer.esm-bundler.js'
import assert from 'node:assert/strict'
const server = await createServer({ root: './frontend', optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false }, appType: 'custom' })
try {
  const { default: Content } = await server.ssrLoadModule('/src/components/QuestionContent.vue')
  const html = await renderToString(createSSRApp(Content, { content: '<script>alert(1)</script>\n```python\n    print(1)\n```\n![图片](data:image/png;base64,YQ==)' }))
  assert.ok(html.includes('&lt;script&gt;'))
  assert.match(html, /<code[^>]*>    print\(1\)<\/code>/)
  assert.ok(html.includes('<img src="data:image/png;base64,YQ=="'))
  console.log('Vue image/code rendering and HTML escaping passed')
} finally { await server.close() }
