import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Self-hosted fonts (D22): no CDN, so the app works on an offline lab
// network. Each file declares its subsets with unicode-range, so the browser
// fetches only Latin and Latin Extended (which holds the rupee sign).
import '@fontsource-variable/schibsted-grotesk/wght.css'
import '@fontsource-variable/ibm-plex-sans/wght.css'
// The real italic of IBM Plex Sans, for the tagline only (D24): one variable
// file holds the 400 and 500 italics it uses; never a synthesised slant.
import '@fontsource-variable/ibm-plex-sans/wght-italic.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './index.css'
import App from './App.tsx'

// The UI is light only, whatever the operating system setting
// (docs/design/ui-brief.md, section 0); there is no theme switch.

// D8, OE-2: a Progressive Web App (public/manifest.webmanifest, public/icons,
// public/sw.js) that installs on Android 9+ and iOS 14+. The service worker
// caches only the app shell and static files, never an API answer. Not in
// development, where it would get in the way of Vite's hot reload.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js')
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
