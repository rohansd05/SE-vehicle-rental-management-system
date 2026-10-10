import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'

import { ApiError } from '@/api/client'

/** ids for a field's hint and error, joined for aria-describedby. */
export function describedBy(id: string, options: { hint?: boolean; error?: boolean }) {
  const ids = [options.hint ? `${id}-hint` : null, options.error ? `${id}-error` : null]
  return ids.filter(Boolean).join(' ') || undefined
}

/**
 * Put server validation errors next to their fields (UI-4) and return the
 * message for the form-level alert (detail, non_field_errors, or errors for
 * fields the form does not show). The server stays the authority (CO-3).
 */
export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): string | null {
  if (!(error instanceof ApiError)) {
    return 'Something went wrong. Please try again.'
  }
  const leftovers: string[] = [...error.nonFieldErrors]
  let focused = false
  for (const [field, messages] of Object.entries(error.fieldErrors)) {
    if ((fields as readonly string[]).includes(field)) {
      setError(field as Path<T>, { type: 'server', message: messages.join(' ') }, { shouldFocus: !focused })
      focused = true
    } else {
      leftovers.push(...messages)
    }
  }
  if (leftovers.length) return leftovers.join(' ')
  if (!Object.keys(error.fieldErrors).length) return error.message
  return null
}
