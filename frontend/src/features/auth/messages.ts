// User-facing auth messages, shared by the screens and their tests.

import type { SignOutReason } from './auth-context'

export const OTP_MESSAGES = {
  expired: 'This code has expired. Codes are valid for 10 minutes. Request a new code.',
  tooMany: 'Too many incorrect attempts. This code no longer works. Request a new code.',
  wrong: (left: number) =>
    `That code isn’t right. You have ${left} more ${left === 1 ? 'try' : 'tries'} with this code.`,
}

export const SIGN_OUT_MESSAGES: Record<Exclude<SignOutReason, 'signed-out'>, string> = {
  inactivity: 'You were signed out after 30 minutes without activity. Please sign in again.',
  'session-expired': 'Your session has ended. Please sign in again.',
  'password-changed':
    'Your password has been changed and you have been signed out on every device. Sign in with your new password.',
}

/** SE-8: shown for a 403 account_locked answer. */
export const LOCKED_MESSAGE =
  'Your account is locked for 15 minutes after too many failed sign-in attempts. Check your e-mail.'
