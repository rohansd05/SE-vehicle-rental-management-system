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
  // Settings-style rows (ui-brief.md 6.7): inside a form marked
  // `@container/form` that is at least 48 rem wide, the label takes a 12 rem
  // column beside the field; narrower forms stack label above field.
  return (
    <div className={cn('grid gap-1.5 @3xl/form:grid-cols-[12rem_minmax(0,1fr)] @3xl/form:items-start @3xl/form:gap-x-6', className)}>
      <Label htmlFor={id} className="@3xl/form:pt-3">
        {label}
      </Label>
      <div className="min-w-0 @3xl/form:col-start-2">{children}</div>
      {hint ? (
        <div id={`${id}-hint`} className="text-small text-muted-foreground @3xl/form:col-start-2">
          {hint}
        </div>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="enter flex items-start gap-1.5 text-small font-medium text-destructive @3xl/form:col-start-2">
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
          className="enter flex items-start gap-2.5 rounded-md border-l-2 border-l-status-unsafe bg-status-unsafe-tint px-4 py-3 text-sm text-foreground"
        >
          <CircleAlert className="mt-1 size-4.5 shrink-0 text-status-unsafe" aria-hidden="true" />
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
            'enter flex items-start gap-2.5 rounded-md border-l-2 px-4 py-3 text-sm text-foreground',
            tone === 'success' && 'draw',
            tone === 'success'
              ? 'border-l-status-available bg-status-available-tint [&>svg]:text-status-available'
              : 'border-l-primary bg-primary-tint [&>svg]:text-primary',
          )}
        >
          <Icon className="mt-1 size-4.5 shrink-0" aria-hidden="true" />
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
