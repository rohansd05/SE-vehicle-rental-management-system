// Client-side validation that mirrors the backend rules for usability only;
// the server re-checks everything and stays the authority (CO-3).

import { z } from 'zod'

import { todayISO } from '@/lib/dates'

/** Proposed A4: 10-15 digits with an optional leading +. */
export const MOBILE_PATTERN = /^\+?[0-9]{10,15}$/
export const MOBILE_HINT = '10 to 15 digits, for example +919812345678.'

/** Django's password validators, as shown to the user before they type. */
export const PASSWORD_RULES = [
  'At least 8 characters.',
  'Not only numbers.',
  'Not a commonly used password.',
  'Not too similar to your name, e-mail or mobile number.',
] as const

export const OTP_LENGTH = 6 // Proposed A2
export const OTP_LIFETIME_MS = 10 * 60 * 1000 // D15
export const OTP_MAX_ATTEMPTS = 5 // D15
export const OTP_RESEND_COOLDOWN_SECONDS = 60 // Proposed A3

const mobile = z
  .string()
  .trim()
  .regex(MOBILE_PATTERN, { error: 'Enter a mobile number of 10 to 15 digits, optionally starting with +.' })

const newPassword = z
  .string()
  .min(8, { error: 'Use at least 8 characters.' })
  .refine((value) => !/^\d+$/.test(value), { error: 'Use more than just numbers.' })

export const registerSchema = z
  .object({
    name: z.string().trim().min(1, { error: 'Enter your full name.' }).max(150),
    email: z.email({ error: 'Enter a valid e-mail address.' }),
    mobile_no: mobile,
    address: z.string().trim().min(1, { error: 'Enter your address.' }),
    date_of_birth: z
      .string()
      .min(1, { error: 'Enter your date of birth.' })
      .refine((value) => value < todayISO(), { error: 'Enter a date of birth in the past.' }),
    emergency_contact_name: z
      .string()
      .trim()
      .min(1, { error: 'Enter the name of someone we can contact in an emergency.' })
      .max(150),
    emergency_contact_mobile: mobile,
    password: newPassword,
    confirm_password: z.string().min(1, { error: 'Enter your password again.' }),
  })
  .refine((data) => data.password === data.confirm_password, {
    path: ['confirm_password'],
    error: 'The passwords do not match.',
  })

export type RegisterValues = z.infer<typeof registerSchema>

export const loginSchema = z.object({
  email: z.email({ error: 'Enter a valid e-mail address.' }),
  password: z.string().min(1, { error: 'Enter your password.' }),
})

export type LoginValues = z.infer<typeof loginSchema>

export const otpSchema = z.object({
  code: z
    .string()
    .trim()
    .regex(new RegExp(`^\\d{${OTP_LENGTH}}$`), { error: `Enter the ${OTP_LENGTH}-digit code.` }),
})

export type OtpValues = z.infer<typeof otpSchema>
