import type { CSSProperties } from 'react'

import { TAGLINE, useAgency } from '@/hooks/page'

// Joined, not merged: the class merger reads a custom size token such as
// text-tagline-hero and a colour such as text-primary as one property and
// drops the size. These components never receive conflicting classes.
const join = (...classes: (string | undefined)[]) => classes.filter(Boolean).join(' ')

// The Veyora wordmark and tagline (D24), one component each so every place
// sets them the same way. Sizes come from tokens per context.

const BRAND_SIZE = {
  /** Top bar, sidebar and footer. */
  bar: 'text-brand',
  /** The sign-in and register panel. */
  panel: 'text-display-sm',
  /** The landing hero. */
  hero: 'text-display',
} as const

/**
 * The brand name as a wordmark: Schibsted Grotesk 800, tracked in. The name
 * is the configured one (AGENCY_NAME) or Veyora; pass `name` only to show a
 * different text in its place (the hero's loading and error states).
 */
export function Brand({
  size,
  name,
  className,
}: {
  size: keyof typeof BRAND_SIZE
  name?: string
  className?: string
}) {
  const agency = useAgency()
  return <span className={join('brand', BRAND_SIZE[size], className)}>{name ?? agency.name}</span>
}

const TAGLINE_SIZE = {
  /** Under the hero wordmark, about half its size. */
  hero: 'text-tagline-hero font-medium',
  /** Call to action, footer, sign-in and register panels. */
  medium: 'text-tagline font-medium',
  /** The sidebar brand block (15 px). */
  small: 'text-tagline-sm',
} as const

/** "Your Ride, Your Rules" in IBM Plex Sans italic: plain visible text, no ARIA. */
export function Tagline({
  size,
  className,
  style,
}: {
  size: keyof typeof TAGLINE_SIZE
  className?: string
  style?: CSSProperties
}) {
  return (
    <p className={join('tagline', TAGLINE_SIZE[size], className)} style={style}>
      {TAGLINE}
    </p>
  )
}
