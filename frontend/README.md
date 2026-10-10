# VRMS frontend

React 18 + TypeScript + Vite, Tailwind CSS and shadcn/ui. Setup, scripts and
the dev proxy are documented in the repository root `README.md`.

```powershell
npm install
npm run dev            # http://localhost:5173 (proxies /api, /admin, /static to :8000)
npm run build
npm run test -- --run
npm run lint
```

Requires Node.js 22.22 or later.
