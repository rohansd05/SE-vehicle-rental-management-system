// The optimised photos (D23, docs/design/imagery-brief.md). Files are made by
// scripts/optimise-images.mjs into public/images/<id>/<width>.<ext> and served
// as static files; src/assets/images/manifest.json holds each photo's widths,
// native aspect, subject box, focal point and credit. This module turns them
// into srcsets and fits each photo to its frame without cutting its subject
// (B13).

import manifest from '@/assets/images/manifest.json'

export interface PhotoCredit {
  title: string
  author: string
  source: string
  page: string
  licence: string
  licenceUrl: string
  changes: string
}

export interface PhotoEntry extends PhotoCredit {
  slot: string
  option: number
  kind: 'hero' | 'panel' | 'cta' | 'band' | 'section' | 'small' | 'quiet' | 'vehicle'
  /** AVIF widths. */
  widths: number[]
  /** WebP widths: all but the largest, as WebP is only the fallback for browsers without AVIF. */
  webpWidths: number[]
  /** The one JPEG fallback width. */
  jpg: number
  /** Native size at the largest width (photos are never cropped). */
  width: number
  height: number
  /** The subject's box in the photo, normalised: [x0, y0, x1, y1]. */
  subject: [number, number, number, number]
  /** Optional object-position as fractions; by default the subject is centred. */
  focus?: [number, number]
}

export interface PhotoSources {
  avif: string
  webp: string
  jpg: string
  /** The JPEG fallback, for browsers without AVIF or WebP. */
  fallback: string
  width: number
  height: number
}

// JSON arrays type as number[]; the optimiser writes the tuples PhotoEntry describes.
export const PHOTOS = manifest as unknown as Record<string, PhotoEntry>

const url = (id: string, width: number, ext: string) => `${import.meta.env.BASE_URL}images/${id}/${width}.${ext}`

/** The srcsets for one photo, or null when it is not in the manifest. */
export function photoSources(id: string): PhotoSources | null {
  const entry = PHOTOS[id]
  if (!entry) return null
  const set = (widths: number[], ext: string) => widths.map((w) => `${url(id, w, ext)} ${w}w`).join(', ')
  return {
    avif: set(entry.widths, 'avif'),
    webp: set(entry.webpWidths, 'webp'),
    jpg: `${url(id, entry.jpg, 'jpg')} ${entry.jpg}w`,
    fallback: url(id, entry.jpg, 'jpg'),
    width: entry.width,
    height: entry.height,
  }
}

/** The subject keeps at least this share of the frame as margin on each side (B13). */
export const SUBJECT_MARGIN = 0.04

export interface PhotoFit {
  fit: 'cover' | 'contain'
  /** CSS object-position. */
  position: string
}

/**
 * How to show a photo in a frame of `frameWidth` x `frameHeight` without
 * cutting its subject: `cover` when a crop can keep the whole subject box
 * plus the margin (or the photo's own margin, where the subject runs closer
 * to the photo's edge), positioned at the focal point and clamped to keep
 * the subject inside; otherwise `contain`, so the whole photo shows.
 */
export function fitPhoto(entry: Pick<PhotoEntry, 'width' | 'height' | 'subject' | 'focus'>, frameWidth: number, frameHeight: number): PhotoFit {
  const [x0, y0, x1, y1] = entry.subject
  const imageAspect = entry.width / entry.height
  const frameAspect = frameWidth > 0 && frameHeight > 0 ? frameWidth / frameHeight : imageAspect
  // The visible share of the photo on each axis under `cover`.
  const visibleX = frameAspect < imageAspect ? frameAspect / imageAspect : 1
  const visibleY = frameAspect > imageAspect ? imageAspect / frameAspect : 1
  const axis = (start: number, end: number, visible: number, focus: number | undefined): number | null => {
    if (visible >= 0.999) return 0.5
    const margin = Math.min(SUBJECT_MARGIN * visible, start, 1 - end)
    const lowest = end + margin - visible
    const highest = start - margin
    if (lowest > highest + 1e-6) return null
    const ideal = focus === undefined ? (start + end) / 2 - visible / 2 : focus * (1 - visible)
    const offset = Math.min(Math.max(ideal, lowest, 0), highest, 1 - visible)
    return offset / (1 - visible)
  }
  const px = axis(x0, x1, visibleX, entry.focus?.[0])
  const py = axis(y0, y1, visibleY, entry.focus?.[1])
  if (px === null || py === null) return { fit: 'contain', position: '50% 50%' }
  const pct = (v: number) => `${Math.round(v * 1000) / 10}%`
  return { fit: 'cover', position: `${pct(px)} ${pct(py)}` }
}
