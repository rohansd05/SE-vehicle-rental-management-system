// Licence rules shown and checked in the browser for usability; the server
// re-validates everything (D3, CO-3). Proposed A5: JPG or PNG, 5 MB.

import { z } from 'zod'

import type { LicenceCategory, LicenceStatus } from '@/api/types'
import { todayISO } from '@/lib/dates'

export const LICENCE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
export const LICENCE_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png'] as const
const LICENCE_IMAGE_TYPES = ['image/jpeg', 'image/png']
export const LICENCE_IMAGE_ACCEPT = '.jpg,.jpeg,.png,image/jpeg,image/png'

export const LICENCE_CATEGORIES: readonly LicenceCategory[] = ['Car', 'Two-Wheeler'] // D18

/** null when the file is acceptable, otherwise the reason it is not. */
export function checkLicenceImage(file: File): string | null {
  const extension = file.name.includes('.') ? file.name.split('.').pop()!.toLowerCase() : ''
  const extensionOk = (LICENCE_IMAGE_EXTENSIONS as readonly string[]).includes(extension)
  if (!extensionOk || (file.type && !LICENCE_IMAGE_TYPES.includes(file.type))) {
    return 'Choose a JPG or PNG image.'
  }
  if (file.size > LICENCE_IMAGE_MAX_BYTES) {
    return 'This image is larger than 5 MB. Choose a smaller photo.'
  }
  return null
}

export const licenceDetailsSchema = z
  .object({
    licence_number: z.string().trim().min(1, { error: 'Enter the licence number.' }).max(32),
    issuing_authority: z
      .string()
      .trim()
      .min(1, { error: 'Enter the authority that issued the licence, for example RTO Mumbai.' })
      .max(150),
    issue_date: z
      .string()
      .min(1, { error: 'Enter the issue date.' })
      .refine((value) => value <= todayISO(), { error: 'The issue date cannot be in the future.' }),
    expiry_date: z
      .string()
      .min(1, { error: 'Enter the expiry date.' })
      // BR-2: an already-expired licence is refused.
      .refine((value) => value >= todayISO(), { error: 'This licence has already expired.' }),
    categories: z
      .array(z.enum(['Car', 'Two-Wheeler']))
      .min(1, { error: 'Choose at least one category the licence covers.' }),
  })
  .refine((data) => !data.issue_date || !data.expiry_date || data.issue_date < data.expiry_date, {
    path: ['expiry_date'],
    error: 'The expiry date must be after the issue date.',
  })

export type LicenceDetailsValues = z.infer<typeof licenceDetailsSchema>

export const STATUS_TONE: Record<LicenceStatus, 'neutral' | 'pending' | 'good' | 'bad'> = {
  'Not Submitted': 'neutral',
  'Pending Verification': 'pending',
  Verified: 'good',
  Rejected: 'bad',
  Expired: 'bad',
}

export const rejectSchema = z.object({
  reason: z.string().trim().min(1, { error: 'Give the customer a reason, so they can fix it.' }).max(1000),
})
export type RejectValues = z.infer<typeof rejectSchema>

/** Whole years between a date of birth and today (for the BR-2 age check at a glance). */
export function ageFrom(dateOfBirth: string): number {
  const today = todayISO()
  const years = Number(today.slice(0, 4)) - Number(dateOfBirth.slice(0, 4))
  return today.slice(5) < dateOfBirth.slice(5) ? years - 1 : years
}
