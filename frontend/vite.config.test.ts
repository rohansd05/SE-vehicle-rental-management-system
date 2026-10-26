import { fileURLToPath, URL as NodeURL } from 'node:url'

import { loadConfigFromFile } from 'vite'
import { expect, test, vi } from 'vitest'

// Signed file links are absolute, built by Django from the Host header (SI-3).
// With the browser's host kept, a vehicle photo comes back through this proxy
// to the same runserver as the JSON, not straight to whatever has port 8000.
test.each(['/api', '/admin', '/static'])('the dev proxy keeps the browser host for %s', async (path) => {
  vi.stubGlobal('URL', NodeURL) // the config resolves its alias with Node's URL, not jsdom's
  const file = fileURLToPath(new NodeURL('./vite.config.ts', import.meta.url))
  const loaded = await loadConfigFromFile({ command: 'serve', mode: 'development' }, file)
  expect(loaded?.config.server?.proxy?.[path]).toMatchObject({ target: 'http://localhost:8000', changeOrigin: false })
})
