import { z } from 'zod'

import { MOBILE_PATTERN, OTP_LENGTH } from '@/features/auth/schemas'

export const detailsSchema = z.object({
  name: z.string().trim().min(1, { error: 'Enter your full name.' }).max(150),
  address: z.string().trim(),
})
export type DetailsValues = z.infer<typeof detailsSchema>

export const mobileSchema = z.object({
  mobile_no: z
    .string()
    .trim()
    .regex(MOBILE_PATTERN, { error: 'Enter a mobile number of 10 to 15 digits, optionally starting with +.' }),
})
export type MobileValues = z.infer<typeof mobileSchema>

export const mobileCodeSchema = z.object({
  code: z
    .string()
    .trim()
    .regex(new RegExp(`^\\d{${OTP_LENGTH}}$`), { error: `Enter the ${OTP_LENGTH}-digit code.` }),
})
export type MobileCodeValues = z.infer<typeof mobileCodeSchema>

export const passwordSchema = z
  .object({
    current_password: z.string().min(1, { error: 'Enter your current password.' }),
    new_password: z
      .string()
      .min(8, { error: 'Use at least 8 characters.' })
      .refine((value) => !/^\d+$/.test(value), { error: 'Use more than just numbers.' }),
    confirm_password: z.string().min(1, { error: 'Enter the new password again.' }),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    path: ['confirm_password'],
    error: 'The passwords do not match.',
  })
export type PasswordValues = z.infer<typeof passwordSchema>
