import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

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

import { type RejectValues, rejectSchema } from './rules'

/** Rejecting needs a reason the customer can act on (SE-10, D-licence rules). */
export function RejectDialog({
  customerName,
  onReject,
}: {
  customerName: string
  onReject: (reason: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<RejectValues>({ resolver: zodResolver(rejectSchema) })

  const onSubmit = handleSubmit(async ({ reason }) => {
    setFormError(null)
    try {
      await onReject(reason)
      setOpen(false)
      reset()
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Something went wrong.')
    }
  })

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          reset()
          setFormError(null)
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="destructive" size="lg" className="h-10">
          Reject
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reject this licence?</DialogTitle>
          <DialogDescription>
            {customerName} will receive this reason by e-mail and can submit the licence again.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} noValidate className="grid gap-4">
          <FormAlert message={formError} />
          <Field id="reject-reason" label="Reason" error={errors.reason?.message}>
            <Textarea
              id="reject-reason"
              rows={4}
              aria-invalid={errors.reason ? true : undefined}
              aria-describedby={describedBy('reject-reason', { error: Boolean(errors.reason) })}
              placeholder="For example: the photo of the back is too blurred to read the categories."
              {...register('reason')}
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" size="lg" className="h-10" onClick={() => setOpen(false)}>
              Keep it pending
            </Button>
            <SubmitButton busy={isSubmitting} busyLabel="Rejecting…">
              Reject licence
            </SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
