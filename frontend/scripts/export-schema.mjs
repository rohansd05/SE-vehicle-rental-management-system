// Export the backend OpenAPI schema to docs/api/openapi.yaml, the source of
// the generated TypeScript types (npm run api:types). Uses the backend venv's
// Python on Windows (venv\Scripts) or Linux/macOS (venv/bin).
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const backend = path.join(root, 'backend')
const candidates = [
  path.join(backend, 'venv', 'Scripts', 'python.exe'),
  path.join(backend, 'venv', 'bin', 'python'),
]
const python = candidates.find((candidate) => existsSync(candidate))
if (!python) {
  console.error('backend/venv not found; create it first (see README).')
  process.exit(1)
}

const output = path.join(root, 'docs', 'api', 'openapi.yaml')
const result = spawnSync(
  python,
  [path.join(backend, 'manage.py'), 'spectacular', '--validate', '--fail-on-warn', '--file', output],
  { stdio: 'inherit' },
)
process.exit(result.status ?? 1)
