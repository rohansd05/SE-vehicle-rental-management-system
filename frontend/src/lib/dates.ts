// Timestamps are stored in UTC and shown in local time (CO-6).

const dateFormat = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' })
const dateTimeFormat = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  // A date-only value ("2026-10-07") is a calendar date, not an instant.
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date(value)
  return dateFormat.format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTimeFormat.format(new Date(value)) : '—'
}

/** Today as YYYY-MM-DD in the user's time zone, for date inputs. */
export function todayISO(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

/** The current time in milliseconds; called from event handlers, never during render. */
export function now(): number {
  return Date.now()
}
