// Optimise the licence-checked photos (D23, docs/design/imagery-brief.md).
//
// Reads scripts/image-sources.json and the originals in .image-src/<id>.jpg
// (downloaded with scripts/download-images.ps1; that folder is git-ignored),
// then for each photo:
//   1. blurs every number-plate box listed in `plates` (normalised x, y, w, h);
//   2. keeps it at its native aspect: no subject is ever cropped here (B13).
//      Each slot fits the photo at runtime from its `subject` box and
//      optional `focus` (src/lib/images.ts, fitPhoto);
//   3. applies the one shared colour grade, so photos from different
//      photographers read as one set;
//   4. writes AVIF at the role's widths, WebP at all but the largest (it is
//      only the fallback for browsers without AVIF, so it skips the heaviest
//      file), plus one JPEG fallback, into
//      public/images/<id>/<width>.<ext> (static files: importing a thousand
//      files as modules made the dev server crawl).
// It then removes outputs and originals no longer listed, and writes
//   - src/assets/images/manifest.json (sizes and credit) for the app and the
//     public "Photo credits" page, and
//   - docs/design/image-credits.md, from the same data.
//
// Usage: node scripts/optimise-images.mjs [id ...]   (no ids = all)

import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import sharp from 'sharp'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const srcDir = path.join(root, '.image-src')
const outDir = path.join(root, 'public/images')
const manifestFile = path.join(root, 'src/assets/images/manifest.json')
const creditsFile = path.join(root, '../docs/design/image-credits.md')
const sources = JSON.parse(await fs.readFile(path.join(root, 'scripts/image-sources.json'), 'utf8'))
const only = new Set(process.argv.slice(2))

/**
 * One profile per role (imagery-brief.md, 2 and 4): the widths it is served
 * at, the single JPEG fallback width and AVIF quality. Every role keeps the
 * photo's native aspect.
 */
const ROLES = {
  hero: { widths: [960, 1600, 2400], jpg: 1600, avif: 45 },
  panel: { widths: [480, 800, 1200], jpg: 800, avif: 48 },
  cta: { widths: [960, 1600, 2400], jpg: 1600, avif: 46 },
  band: { widths: [480, 960, 1440], jpg: 960, avif: 48 },
  section: { widths: [400, 800], jpg: 800, avif: 50 },
  small: { widths: [320, 640], jpg: 640, avif: 50 },
  quiet: { widths: [320, 640, 960], jpg: 640, avif: 50 },
  vehicle: { widths: [320, 640, 960], jpg: 640, avif: 52 },
}
/** Budget per brief: the largest hero AVIF stays under about 400 KB. */
const HERO_AVIF_BUDGET = 400 * 1024

/** The shared grade: a touch less saturation and a little more contrast, the same for every photo. */
const grade = (image) => image.modulate({ saturation: 0.9 }).linear(1.04, -4)

async function blurPlates(buffer, meta, plates) {
  if (!plates?.length) return buffer
  const overlays = []
  for (const [x, y, w, h] of plates) {
    // Pad each box so no character edge survives, then pixelate and blur it.
    const left = Math.max(0, Math.round((x - w * 0.15) * meta.width))
    const top = Math.max(0, Math.round((y - h * 0.25) * meta.height))
    const width = Math.min(meta.width - left, Math.round(w * 1.3 * meta.width))
    const height = Math.min(meta.height - top, Math.round(h * 1.5 * meta.height))
    const patch = await sharp(buffer)
      .extract({ left, top, width, height })
      .resize(Math.max(4, Math.round(width / 14)), Math.max(2, Math.round(height / 14)))
      .resize(width, height, { kernel: 'nearest' })
      .blur(Math.max(2, Math.round(height / 6)))
      .toBuffer()
    overlays.push({ input: patch, left, top })
  }
  return sharp(buffer).composite(overlays).toBuffer()
}

const exists = (p) => fs.access(p).then(() => true, () => false)
const manifest = JSON.parse(await fs.readFile(manifestFile, 'utf8').catch(() => '{}'))
let processed = 0
for (const s of sources) {
  if (only.size && !only.has(s.id)) continue
  const role = ROLES[s.kind]
  if (!role) throw new Error(`unknown role "${s.kind}" for ${s.id}`)
  const file = path.join(srcDir, `${s.id}.jpg`)
  if (!(await exists(file))) {
    console.warn('missing original, skipped:', s.id)
    continue
  }
  let buffer = await sharp(file).rotate().toBuffer()
  const meta = await sharp(buffer).metadata()
  buffer = await blurPlates(buffer, meta, s.plates)
  if (!s.subject) throw new Error(`no subject box for ${s.id}`)
  buffer = await grade(sharp(buffer)).toBuffer()
  const final = await sharp(buffer).metadata()
  const widths = role.widths.filter((w) => w <= final.width)
  if (!widths.length) widths.push(final.width)
  const jpgWidth = role.jpg <= final.width ? role.jpg : widths.at(-1)
  const dir = path.join(outDir, s.id)
  await fs.rm(dir, { recursive: true, force: true })
  await fs.mkdir(dir, { recursive: true })
  const webpWidths = widths.length > 1 ? widths.slice(0, -1) : widths
  for (const w of widths) {
    const resized = sharp(buffer).resize({ width: w })
    await resized.clone().avif({ quality: role.avif, effort: 6 }).toFile(path.join(dir, `${w}.avif`))
    if (webpWidths.includes(w)) await resized.clone().webp({ quality: 66 }).toFile(path.join(dir, `${w}.webp`))
  }
  await sharp(buffer).resize({ width: jpgWidth }).jpeg({ quality: 72, mozjpeg: true }).toFile(path.join(dir, `${jpgWidth}.jpg`))
  if (s.kind === 'hero') {
    const largest = (await fs.stat(path.join(dir, `${widths.at(-1)}.avif`))).size
    if (largest > HERO_AVIF_BUDGET) console.warn(`hero over budget: ${s.id} ${Math.round(largest / 1024)} KB`)
  }
  manifest[s.id] = {
    slot: s.slot,
    option: s.option,
    kind: s.kind,
    widths,
    webpWidths,
    jpg: jpgWidth,
    width: Math.round((final.width * widths.at(-1)) / final.width),
    height: Math.round((final.height * widths.at(-1)) / final.width),
    title: s.title,
    author: s.author,
    source: s.source,
    page: s.page,
    licence: s.licence,
    licenceUrl: s.licenceUrl,
    subject: s.subject,
    ...(s.focus ? { focus: s.focus } : {}),
    changes: [s.plates?.length ? 'number plate blurred' : null, 'colour graded', 'resized']
      .filter(Boolean)
      .join(', '),
  }
  processed++
}

// Remove outputs, originals and manifest entries that are no longer listed.
const ids = new Set(sources.map((s) => s.id))
for (const id of await fs.readdir(outDir).catch(() => [])) {
  if (!ids.has(id)) await fs.rm(path.join(outDir, id), { recursive: true, force: true })
}
for (const name of await fs.readdir(srcDir).catch(() => [])) {
  if (!ids.has(name.replace(/\.jpg$/, ''))) await fs.rm(path.join(srcDir, name), { force: true })
}
for (const id of Object.keys(manifest)) {
  if (!ids.has(id) || !(await exists(path.join(outDir, id)))) delete manifest[id]
}
await fs.writeFile(manifestFile, JSON.stringify(manifest, null, 2) + '\n')

// docs/design/image-credits.md, from the same data as the /credits page.
const rows = Object.entries(manifest)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([id, p]) => `| ${id} | ${p.title} | ${p.author} | [${p.source}](${p.page}) | [${p.licence}](${p.licenceUrl}) | ${p.changes} |`)
await fs.writeFile(
  creditsFile,
  [
    '# Photo credits',
    '',
    'Generated by `frontend/scripts/optimise-images.mjs` from',
    '`frontend/src/assets/images/manifest.json`, the same data the public',
    '"Photo credits" page (`/credits`) shows. Do not edit by hand. Sources and',
    'licences follow decision D23 (`docs/decisions.md`).',
    '',
    '| Photo | Title | Author | Source | Licence | Changes made |',
    '|---|---|---|---|---|---|',
    ...rows,
    '',
  ].join('\n'),
)
console.log(`optimised ${processed} photo(s); manifest has ${Object.keys(manifest).length}`)
