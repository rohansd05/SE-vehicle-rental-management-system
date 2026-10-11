// Accessible form building blocks (UI-4, UI-8, WCAG 2.1 AA):
// every input has a visible label, hints and errors are tied to it with
// aria-describedby, form-level errors are announced and take focus, and the
// submit button is disabled with a progress indicator while working.

import { CircleAlert, CircleCheck, Info, LoaderCircle } from 'lucide-react'
import { type ReactNode, useEffect, useRef } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

export function Field({
  id,
  label,
  hint,
  error,
  children,
  className,
}: {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('grid gap-1.5', className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint ? (
        <div id={`${id}-hint`} className="text-small text-muted-foreground">
          {hint}
        </div>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="flex items-start gap-1.5 text-small font-medium text-destructive">
          <CircleAlert className="mt-[3px] size-3.5 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  )
}

/** A form-level error: announced at once and focused so keyboard users land on it. */
export function FormAlert({ message }: { message: string | null | undefined }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (message) ref.current?.focus()
  }, [message])
  return (
    <div ref={ref} tabIndex={-1} aria-live="assertive" className="outline-none">
      {message ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border-l-2 border-l-status-unsafe bg-status-unsafe-tint px-3 py-2.5 text-sm text-foreground"
        >
          <CircleAlert className="mt-[3px] size-4 shrink-0 text-status-unsafe" aria-hidden="true" />
          <span>{message}</span>
        </div>
      ) : null}
    </div>
  )
}

/** A polite status message (success or information). */
export function StatusMessage({
  message,
  tone = 'info',
}: {
  message: ReactNode | null | undefined
  tone?: 'info' | 'success'
}) {
  const Icon = tone === 'success' ? CircleCheck : Info
  return (
    <div role="status" aria-live="polite">
      {message ? (
        <div
          className={cn(
            'flex items-start gap-2 rounded-md border-l-2 px-3 py-2.5 text-sm text-foreground',
            tone === 'success'
              ? 'border-l-status-available bg-status-available-tint [&>svg]:text-status-available'
              : 'border-l-primary bg-primary-tint [&>svg]:text-primary',
          )}
        >
          <Icon className="mt-[3px] size-4 shrink-0" aria-hidden="true" />
          <span>{message}</span>
        </div>
      ) : null}
    </div>
  )
}

export function SubmitButton({
  busy,
  children,
  busyLabel,
  className,
  disabled,
}: {
  busy: boolean
  children: ReactNode
  busyLabel?: string
  className?: string
  disabled?: boolean
}) {
  return (
    <Button
      type="submit"
      size="lg"
      disabled={busy || disabled}
      aria-busy={busy}
      className={cn('w-full sm:w-auto sm:justify-self-start', className)}
    >
      {busy ? <LoaderCircle className="animate-spin" aria-hidden="true" /> : null}
      {busy ? (busyLabel ?? 'Please wait…') : children}
    </Button>
  )
}
