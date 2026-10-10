import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'

import { installSessionHooks } from '@/api/client'
import { setAccessToken } from '@/lib/session'

import { server } from './server'

// Forms with several fields re-render many times under jsdom; one second is tight.
configure({ asyncUtilTimeout: 3000 })

// jsdom has no object URLs; the licence image preview needs them.
if (!URL.createObjectURL) {
  URL.createObjectURL = vi.fn(() => 'blob:preview')
  URL.revokeObjectURL = vi.fn()
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

afterEach(() => {
  cleanup()
  server.resetHandlers()
  setAccessToken(null)
  installSessionHooks(null)
  localStorage.clear()
  sessionStorage.clear()
  vi.useRealTimers()
})

afterAll(() => server.close())
