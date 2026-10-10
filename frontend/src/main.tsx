import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { followSystemTheme } from './lib/theme'

// Light or dark, following the operating system setting.
followSystemTheme()

// TODO(D8, OE-2): ship as a Progressive Web App (web app manifest, icons and
// a service worker) so the responsive client installs on Android 9+ and
// iOS 14+. A responsive PWA meets OE-2 for Release 1.0.

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
