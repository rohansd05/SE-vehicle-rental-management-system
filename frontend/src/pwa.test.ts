// D8, OE-2 (Module N4): the PWA's manifest, the install tags and the service
// worker's caching rules. The worker is public/sw.js, run here in a fake worker
// scope: it must never answer for /api, /admin, /media or /static, so no API
// response with personal data is ever cached.

import { describe, expect, it, vi } from 'vitest'

import indexHtml from '../index.html?raw'
import manifestSource from '../public/manifest.webmanifest?raw'
import swSource from '../public/sw.js?raw'

import tokens from './index.css?raw'

const ORIGIN = 'https://veyora.test'

type Listener = (event: unknown) => void

function fakeCache(entries: Map<string, Response>) {
  return {
    match: vi.fn(async (request: Request | string) => entries.get(typeof request === 'string' ? request : new URL(request.url).pathname)),
    put: vi.fn(async (request: Request, response: Response) => {
      entries.set(new URL(request.url).pathname, response)
    }),
    addAll: vi.fn(async (urls: string[]) => urls.forEach((url) => entries.set(url, new Response(url)))),
    keys: vi.fn(async () => [...entries.keys()]),
    delete: vi.fn(async (key: string) => entries.delete(key)),
  }
}

function loadWorker(fetchImpl: (request: unknown) => Promise<Response>) {
  const listeners: Record<string, Listener> = {}
  const entries = new Map<string, Response>()
  const cache = fakeCache(entries)
  const caches = {
    open: vi.fn(async () => cache),
    match: cache.match,
    keys: vi.fn(async () => ['veyora-shell-v0']),
    delete: vi.fn(async () => true),
  }
  const scope = {
    addEventListener: (type: string, listener: Listener) => {
      listeners[type] = listener
    },
    location: { origin: ORIGIN },
    skipWaiting: vi.fn(async () => undefined),
    clients: { claim: vi.fn(async () => undefined) },
  }
  const fetchMock = vi.fn(fetchImpl)
  new Function('self', 'caches', 'fetch', swSource)(scope, caches, fetchMock)
  return { listeners, cache, caches, entries, fetchMock }
}

function fetchEvent(path: string, { method = 'GET', mode = 'cors', origin = ORIGIN } = {}) {
  const request = { url: `${origin}${path}`, method, mode }
  let answer: Promise<Response> | undefined
  return {
    event: { request, respondWith: vi.fn((response: Promise<Response>) => (answer = response)) },
    answer: () => answer,
  }
}

/** A same-origin 200 (jsdom's Response cannot be given type "basic"). */
function sameOrigin(): Response {
  const response = { ok: true, status: 200, type: 'basic', text: async () => 'body', clone: () => response }
  return response as unknown as Response
}
const ok = () => Promise.resolve(sameOrigin())

describe('service worker (D8)', () => {
  it.each([
    ['/api/v1/bookings/12/', 'cors'],
    ['/api/v1/files/signed-token/', 'no-cors'],
    ['/api/v1/me/', 'navigate'],
    ['/admin/', 'navigate'],
    ['/media/rentals/photos/front.jpg', 'no-cors'],
    ['/static/admin/css/base.css', 'no-cors'],
  ])('never answers for %s (%s), so it never caches personal data', (path, mode) => {
    const { listeners } = loadWorker(ok)
    const { event } = fetchEvent(path, { mode })
    listeners.fetch(event)
    expect(event.respondWith).not.toHaveBeenCalled()
  })

  it('leaves other origins and other methods alone', () => {
    const { listeners } = loadWorker(ok)
    for (const { event } of [fetchEvent('/assets/a.js', { origin: 'https://cdn.example' }), fetchEvent('/assets/a.js', { method: 'POST' })]) {
      listeners.fetch(event)
      expect(event.respondWith).not.toHaveBeenCalled()
    }
  })

  it('caches the hashed bundles, photos and icons after the first load', async () => {
    const { listeners, cache } = loadWorker(ok)
    const { event, answer } = fetchEvent('/assets/index-abc123.js', { mode: 'no-cors' })
    listeners.fetch(event)
    await answer()
    expect(cache.put).toHaveBeenCalledTimes(1)
    expect(new URL(cache.put.mock.calls[0][0].url).pathname).toBe('/assets/index-abc123.js')
  })

  it('does not cache a failed static response', async () => {
    const { listeners, cache } = loadWorker(() => Promise.resolve(new Response('missing', { status: 404 })))
    const { event, answer } = fetchEvent('/images/hero-1/hero-1-1280.webp', { mode: 'no-cors' })
    listeners.fetch(event)
    expect((await answer())?.status).toBe(404)
    expect(cache.put).not.toHaveBeenCalled()
  })

  it('loads pages from the network, never from the cache', async () => {
    const { listeners, cache, fetchMock } = loadWorker(ok)
    const { event, answer } = fetchEvent('/app/bookings', { mode: 'navigate' })
    listeners.fetch(event)
    expect(await (await answer())?.text()).toBe('body')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(cache.put).not.toHaveBeenCalled()
  })

  it('shows the offline page when a page cannot be loaded', async () => {
    const { listeners } = loadWorker(() => Promise.reject(new TypeError('Failed to fetch')))
    const install = { waitUntil: vi.fn() }
    listeners.install(install)
    await install.waitUntil.mock.calls[0][0]
    const { event, answer } = fetchEvent('/app/bookings/12', { mode: 'navigate' })
    listeners.fetch(event)
    expect(await (await answer())?.text()).toBe('/offline.html')
  })

  it('precaches only the offline page and the icons, and drops old caches', async () => {
    const { listeners, cache, caches } = loadWorker(ok)
    const install = { waitUntil: vi.fn() }
    listeners.install(install)
    await install.waitUntil.mock.calls[0][0]
    expect(cache.addAll).toHaveBeenCalledWith(['/offline.html', '/icons/icon-192.png', '/icons/icon-512.png'])
    const activate = { waitUntil: vi.fn() }
    listeners.activate(activate)
    await activate.waitUntil.mock.calls[0][0]
    expect(caches.delete).toHaveBeenCalledWith('veyora-shell-v0')
  })
})

describe('web app manifest (D8, D24)', () => {
  const manifest = JSON.parse(manifestSource) as {
    name: string
    short_name: string
    display: string
    start_url: string
    theme_color: string
    background_color: string
    icons: { src: string; sizes: string; purpose: string }[]
  }

  it('names Veyora with its tagline and opens standalone', () => {
    expect(manifest.name).toBe('Veyora - Your Ride, Your Rules')
    expect(manifest.short_name).toBe('Veyora')
    expect(manifest.display).toBe('standalone')
    expect(manifest.start_url).toBe('/')
  })

  it('takes its colours from the design tokens', () => {
    const token = (name: string) => new RegExp(`(?<![\\w-])--${name}:\\s*([^;]+);`).exec(tokens)?.[1].trim().toLowerCase()
    expect(manifest.theme_color.toLowerCase()).toBe(token('primary'))
    expect(manifest.background_color.toLowerCase()).toBe(token('canvas'))
  })

  it('has 192 and 512 icons and a maskable one', () => {
    const icons = manifest.icons.map((icon) => `${icon.sizes} ${icon.purpose}`)
    expect(icons).toEqual(expect.arrayContaining(['192x192 any', '512x512 any', '512x512 maskable']))
  })

  it('is linked from the page, with the tags iOS needs to install it', () => {
    expect(indexHtml).toContain('<link rel="manifest" href="/manifest.webmanifest" />')
    expect(indexHtml).toContain('<link rel="apple-touch-icon" href="/icons/icon-180.png" />')
    expect(indexHtml).toContain('<meta name="apple-mobile-web-app-capable" content="yes" />')
    expect(indexHtml).toContain('<meta name="apple-mobile-web-app-title" content="Veyora" />')
  })
})
