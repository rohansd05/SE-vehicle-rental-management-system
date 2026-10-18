// Veyora service worker (D8: the PWA that meets OE-2 on Android 9+ and iOS 14+).
//
// Caches only the app shell and static files: the offline page and the icons,
// and the hashed bundles, photos and fonts the app loads. Never /api, /admin,
// /media or /static: API answers (including signed file links) carry personal
// data and always go to the network. index.html and the manifest are not cached
// either, so a deploy reaches every installed app on its next start.

const SHELL = 'veyora-shell-v1'
const ASSETS = 'veyora-assets-v1'
const OFFLINE_URL = '/offline.html'
const PRECACHE = [OFFLINE_URL, '/icons/icon-192.png', '/icons/icon-512.png']
// Hashed bundles (/assets), the public photos (/images) and the icons never change in place.
const STATIC_PREFIXES = ['/assets/', '/images/', '/icons/']
const NEVER_CACHED = ['/api/', '/admin', '/media/', '/static/']
// Old bundles pile up after each deploy; keep only the newest entries.
const MAX_ASSETS = 120

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== SHELL && key !== ASSETS).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

async function cacheFirst(request) {
  const cached = await caches.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok && response.type === 'basic') {
    const cache = await caches.open(ASSETS)
    await cache.put(request, response.clone())
    const keys = await cache.keys()
    await Promise.all(keys.slice(0, Math.max(0, keys.length - MAX_ASSETS)).map((key) => cache.delete(key)))
  }
  return response
}

async function networkOrOffline(request) {
  try {
    return await fetch(request)
  } catch {
    return (await caches.match(OFFLINE_URL)) ?? Response.error()
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin) return
  if (NEVER_CACHED.some((prefix) => url.pathname.startsWith(prefix))) return
  if (request.mode === 'navigate') {
    event.respondWith(networkOrOffline(request))
  } else if (STATIC_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    event.respondWith(cacheFirst(request))
  }
})
