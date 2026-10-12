// Entry motion helpers (docs/design/ui-brief.md, section 5). Each returns
// the class and inline delay for the `enter` or `reveal` utility, so
// siblings rise into place one after another. Delays are capped so a long
// list never keeps the reader waiting.

import type { CSSProperties } from 'react'

const STEP_MS = 40
const MAX_STEPS = 10

/** Inline style that staggers the `enter`/`reveal` utilities by `index` steps (first 10 rows only, B5). */
export function stagger(index: number, stepMs = STEP_MS): CSSProperties {
  const steps = Math.min(index, MAX_STEPS)
  return { ['--enter-delay' as string]: `${steps * stepMs}ms` } as CSSProperties
}

/** Class and style for an element that rises in on mount, `index` steps late. */
export function enter(index = 0, stepMs = STEP_MS) {
  return { className: 'enter', style: stagger(index, stepMs) }
}
