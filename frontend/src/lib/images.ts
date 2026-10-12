// The optimised photos (D23, docs/design/imagery-brief.md). Files are made by
// scripts/optimise-images.mjs into public/images/<id>/<width>.<ext> and served
// as static files; src/assets/images/manifest.json holds each photo's widths,
// aspect and credit. This module turns them into srcsets.

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
  width: number
  height: number
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

export const PHOTOS = manifest as Record<string, PhotoEntry>

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
