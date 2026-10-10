/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev only: the browser talks to Vite, and Vite forwards API, admin and
// Django static requests to runserver. Production is same-origin behind
// Caddy (D1), so no CORS package is needed in either case.
const backend = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': backend,
      '/admin': backend,
      // Admin and Swagger UI assets are served by Django under /static/.
      '/static': backend,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    // On slower laptops more workers make jsdom tests time out at random;
    // two workers pass the whole suite and run each test 2-3x faster.
    maxWorkers: 2,
    testTimeout: 20_000,
    hookTimeout: 20_000,
  },
})
