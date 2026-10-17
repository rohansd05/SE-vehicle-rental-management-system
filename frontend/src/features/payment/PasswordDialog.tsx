import { type ComponentProps, type FormEvent, type ReactNode, useState } from 'react'

import { ApiError } from '@/api/client'
import { Field, FormAlert, SubmitButton } from '@/components/form'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { describedBy } from '@/lib/form'

/**
 * SE-9: "re-authentication shall be required before a payment or a refund".
 * One dialog for every action that moves money: its own fields (a reason,
 * the cash received, an acknowledgement) come in as children, and `check`
 * refuses an incomplete form before anything is sent.
 */
export function PasswordDialog({
  id,
  trigger,
  variant = 'default',
  title,
  description,
  submitLabel,
  busyLabel,
  cancelLabel,
  children,
  check,
  onConfirm,
  onClose,
}: {
  id: string
  trigger: string
  variant?: ComponentProps<typeof Button>['variant']
  title: string
  description: ReactNode
  submitLabel: string
  busyLabel: string
  cancelLabel: string
  children?: ReactNode
  check?: () => string | null
  onConfirm: (password: string) => Promise<void>
  onClose?: () => void
}) {
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const close = (next: boolean) => {
    setOpen(next)
    if (!next) {
      setPassword('')
      setPasswordError(null)
      setFormError(null)
      onClose?.()
    }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const problem = check?.() ?? null
    setFormError(problem)
    if (problem) return
    if (!password) {
      setPasswordError('Enter your password to confirm.')
      return
    }
    setPasswordError(null)
    setBusy(true)
    try {
      await onConfirm(password)
      close(false)
    } catch (error) {
      setPassword('')
      const fieldError = error instanceof ApiError ? error.fieldErrors.password?.join(' ') : undefined
      if (fieldError) setPasswordError(fieldError)
      else setFormError(error instanceof Error ? error.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  const passwordId = `${id}-password`
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogTrigger asChild>
        <Button variant={variant}>{trigger}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="grid gap-4">
          <FormAlert message={formError} />
          {children}
          <Field id={passwordId} label="Your password" error={passwordError ?? undefined}>
            <Input
              id={passwordId}
              type="password"
              autoComplete="current-password"
              value={password}
              aria-invalid={passwordError ? true : undefined}
              aria-describedby={describedBy(passwordId, { error: Boolean(passwordError) })}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => close(false)}>
              {cancelLabel}
            </Button>
            <SubmitButton busy={busy} busyLabel={busyLabel}>
              {submitLabel}
            </SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
