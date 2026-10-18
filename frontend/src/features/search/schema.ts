// Search form rules, checked in the browser for usability only; the server
// re-checks every one (CO-3). The limits are BR-5's.

import { z } from 'zod'

import { now } from '@/lib/dates'

const HOUR = 60 * 60 * 1000
/** BR-5: a rental lasts at least 4 hours and at most 30 days. */
export const MIN_RENTAL_MS = 4 * HOUR
export const MAX_RENTAL_MS = 30 * 24 * HOUR

const time = (value: string) => new Date(value).getTime()

const amount = z.string().refine((value) => value === '' || Number(value) >= 0, {
  error: 'Enter an amount of zero or more.',
})

export const searchSchema = z
  .object({
    branch: z.string().min(1, { error: 'Choose a pickup branch.' }),
    category: z.string(),
    pickup_datetime: z
      .string()
      .min(1, { error: 'Enter the pickup date and time.' })
      .refine((value) => time(value) > now(), { error: 'Choose a pickup time in the future.' }),
    return_datetime: z.string().min(1, { error: 'Enter the return date and time.' }),
    // Search.Filter (Module R4).
    vehicle_type: z.string(),
    brand: z.string(),
    model: z.string(),
    fuel_type: z.string(),
    transmission: z.string(),
    min_seats: z.string(),
    min_price: amount,
    max_price: amount,
    min_rating: z.string(),
    sort: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.min_price && data.max_price && Number(data.max_price) < Number(data.min_price)) {
      ctx.addIssue({
        code: 'custom',
        path: ['max_price'],
        message: 'The highest price must not be below the lowest.',
      })
    }
    if (!data.pickup_datetime || !data.return_datetime) return
    const length = time(data.return_datetime) - time(data.pickup_datetime)
    const message =
      length <= 0
        ? 'The return must be after the pickup.'
        : length < MIN_RENTAL_MS
          ? 'A rental lasts at least 4 hours (BR-5).'
          : length > MAX_RENTAL_MS
            ? 'A rental lasts at most 30 days (BR-5).'
            : null
    if (message) ctx.addIssue({ code: 'custom', path: ['return_datetime'], message })
  })
export type SearchValues = z.infer<typeof searchSchema>

/** A datetime-local value ("2026-10-14T10:00") as a UTC ISO timestamp (CO-6). */
export const localToISO = (value: string) => new Date(value).toISOString()

/** A UTC ISO timestamp as a datetime-local value in the user's time zone. */
export function isoToLocal(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}
