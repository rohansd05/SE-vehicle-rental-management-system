import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Self-hosted fonts (D22): no CDN, so the app works on an offline lab
// network. Each file declares its subsets with unicode-range, so the browser
// fetches only Latin and Latin Extended (which holds the rupee sign).
import '@fontsource-variable/archivo/wdth.css'
import '@fontsource-variable/ibm-plex-sans/wght.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './index.css'
import App from './App.tsx'

// The UI is light only, whatever the operating system setting
// (docs/design/ui-brief.md, section 0); there is no theme switch.

// TODO(D8, OE-2): ship as a Progressive Web App (web app manifest, icons and
// a service worker) so the responsive client installs on Android 9+ and
// iOS 14+. A responsive PWA meets OE-2 for Release 1.0.

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
