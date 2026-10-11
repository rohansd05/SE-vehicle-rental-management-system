// The five status colours (docs/design/ui-brief.md, section 3.3). Every
// status pill, dot and status note in the app takes its colours from here,
// so the same meaning always looks the same. Colour only reinforces the
// status name and icon, which are always shown (WCAG 2.1 1.4.1).

export type StatusTone = 'available' | 'booked' | 'maintenance' | 'unsafe' | 'inactive'

/** Pill and note colours: the status ink on its tint. */
export const TONE_PILL: Record<StatusTone, string> = {
  available: 'bg-status-available-tint text-status-available',
  booked: 'bg-status-booked-tint text-status-booked',
  maintenance: 'bg-status-maintenance-tint text-status-maintenance',
  unsafe: 'bg-status-unsafe-tint text-status-unsafe',
  inactive: 'bg-status-inactive-tint text-status-inactive',
}

/** A small solid dot in the status ink, for quiet secondary statuses. */
export const TONE_DOT: Record<StatusTone, string> = {
  available: 'bg-status-available',
  booked: 'bg-status-booked',
  maintenance: 'bg-status-maintenance',
  unsafe: 'bg-status-unsafe',
  inactive: 'bg-status-inactive',
}
