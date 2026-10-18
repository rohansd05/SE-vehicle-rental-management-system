import { type ComponentProps, type FormEvent, type ReactNode, useState } from 'react'

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
import { Textarea } from '@/components/ui/textarea'
import { describedBy } from '@/lib/form'

/**
 * A consequential admin action that records why (Fleet.Retire, Fleet.Users disable and
 * re-enable, BR-4 blacklisting): the reason goes into the audit log with the change.
 */
export function ReasonDialog({
  id,
  trigger,
  variant = 'outline',
  title,
  description,
  submitLabel,
  busyLabel,
  cancelLabel,
  onConfirm,
}: {
  id: string
  trigger: string
  variant?: ComponentProps<typeof Button>['variant']
  title: string
  description: ReactNode
  submitLabel: string
  busyLabel: string
  cancelLabel: string
  onConfirm: (reason: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const close = (next: boolean) => {
    setOpen(next)
    if (!next) {
      setReason('')
      setReasonError(null)
      setFormError(null)
    }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!reason.trim()) {
      setReasonError('Give the reason.')
      return
    }
    setReasonError(null)
    setBusy(true)
    try {
      await onConfirm(reason.trim())
      close(false)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  const reasonId = `${id}-reason`
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
          <Field id={reasonId} label="Reason" error={reasonError ?? undefined}>
            <Textarea
              id={reasonId}
              rows={3}
              value={reason}
              aria-invalid={reasonError ? true : undefined}
              aria-describedby={describedBy(reasonId, { error: Boolean(reasonError) })}
              onChange={(event) => setReason(event.target.value)}
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
