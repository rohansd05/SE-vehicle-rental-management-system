// Binding decision B10 (docs/design/ui-brief.md): every colour and type size
// comes from the tokens in src/index.css. This check fails if a file under
// src/ (outside index.css and the components/ui primitives) contains
//   - a raw hex, rgb(), hsl() or oklch() colour,
//   - a Tailwind palette colour class (bg-emerald-600, text-white, ...), or
//   - an arbitrary text size (text-[13px], text-[clamp(...)]).
// Run with `npm run check:design`.

import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const src = path.join(root, 'src')
const SKIP = [path.join(src, 'index.css'), path.join(src, 'components', 'ui') + path.sep, path.join(src, 'api', 'schema.d.ts')]

const PALETTE = 'slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black|white'
const UTILITIES = 'bg|text|border|border-[trblxy]|ring|ring-offset|outline|fill|stroke|from|via|to|decoration|accent|caret|divide|placeholder|shadow'
const RULES = [
  { name: 'raw hex colour', re: /(?<![\w&/-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])/g },
  { name: 'raw colour function', re: /\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\(/g },
  { name: 'Tailwind palette colour class', re: new RegExp(`(?<![\\w-])(?:[a-z-]+:)*(?:${UTILITIES})-(?:${PALETTE})(?:-\\d{2,3})?(?:\\/\\d+)?(?![\\w-])`, 'g') },
  { name: 'arbitrary text size', re: /(?<![\w-])(?:[a-z-]+:)*text-\[(?:\d|\.|clamp|calc|var|min|max)[^\]]*\]/g },
]

// Self-check: the patterns must catch these and leave these alone.
const SHOULD_FAIL = ['color: #1B1C1D', 'rgb(0 0 0 / 10%)', 'bg-emerald-600', 'hover:text-white', 'border-l-red-500/40', 'text-[13px]', 'md:text-[clamp(1rem,2vw,2rem)]']
const SHOULD_PASS = ['href="#main-content"', 'to={`/help#${topic.id}`}', 'bg-status-unsafe-tint', 'text-primary-foreground', 'text-display-sm', 'bg-surface']
for (const sample of SHOULD_FAIL) if (!RULES.some(({ re }) => new RegExp(re.source).test(sample))) throw new Error(`check:design self-check missed: ${sample}`)
for (const sample of SHOULD_PASS) if (RULES.some(({ re }) => new RegExp(re.source).test(sample))) throw new Error(`check:design self-check flagged: ${sample}`)

async function* walk(dir) {
  for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) yield* walk(full)
    else if (/\.(tsx?|css|mjs|js)$/.test(entry.name)) yield full
  }
}

const problems = []
for await (const file of walk(src)) {
  if (SKIP.some((skip) => file === skip || file.startsWith(skip))) continue
  const lines = (await fs.readFile(file, 'utf8')).split('\n')
  lines.forEach((line, index) => {
    for (const { name, re } of RULES) {
      for (const match of line.matchAll(re)) {
        problems.push(`${path.relative(root, file)}:${index + 1}  ${name}: ${match[0]}`)
      }
    }
  })
}

if (problems.length) {
  console.error(`check:design found ${problems.length} problem(s):\n` + problems.join('\n'))
  process.exit(1)
}
console.log('check:design: no raw colours, palette classes or arbitrary text sizes under src/')
