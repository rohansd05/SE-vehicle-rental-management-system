import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { StickyRail } from '@/components/sticky-rail'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { describedBy } from '@/lib/form'
import { RAIL_LAYOUT } from '@/lib/layout'

import { newIdempotencyKey } from '@/features/booking/api'

import { type Due, getDue, payDue } from './api'
import { DUE_KEY } from './keys'
import { initialChoice, methodRequest } from './method'
import { MethodPicker } from './MethodPicker'

function DueForm({ due, onPaid }: { due: Due; onPaid: (after: Due) => void }) {
  const { currency } = useAgency()
  const [choice, setChoice] = useState(() => initialChoice())
  const [password, setPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const pay = useMutation({
    // A fresh key per attempt: a repeat of the same request never charges twice (Pay.Idempotent).
    mutationFn: () => payDue({ ...methodRequest(choice), idempotency_key: newIdempotencyKey(), password }),
    onSuccess: onPaid,
    onError: (error) => {
      setPassword('')
      setPasswordError(error instanceof ApiError ? (error.fieldErrors.password?.join(' ') ?? null) : null)
    },
  })

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!password) {
      setPasswordError('Enter your password to confirm the payment.')
      return
    }
    setPasswordError(null)
    pay.mutate()
  }

  const failure = pay.error instanceof ApiError && !pay.error.fieldErrors.password ? pay.error.message : null
  const upiError = pay.error instanceof ApiError ? pay.error.fieldErrors.upi_id?.join(' ') : undefined
  return (
    <form onSubmit={onSubmit} noValidate className="grid gap-6" aria-label="Pay your due">
      <FormAlert message={failure} />
      <MethodPicker value={choice} onChange={setChoice} allowCash={false} upiError={upiError} />
      <Field
        id="due-password"
        label="Your password"
        hint="For your security we ask for your password before every payment."
        error={passwordError ?? undefined}
        className="max-w-sm"
      >
        <Input
          id="due-password"
          type="password"
          autoComplete="current-password"
          value={password}
          aria-invalid={passwordError ? true : undefined}
          aria-describedby={describedBy('due-password', { hint: true, error: Boolean(passwordError) })}
          onChange={(event) => setPassword(event.target.value)}
        />
      </Field>
      <div>
        <SubmitButton busy={pay.isPending} busyLabel="Paying your due…" className="tabular-nums">
          Pay {formatCurrency(due.outstanding_due, currency)}
        </SubmitButton>
      </div>
    </form>
  )
}

/** Pay.Dues: clear an outstanding due on-line; booking is allowed again at once (BR-4). */
export function DuePage() {
  const queryClient = useQueryClient()
  const { currency } = useAgency()
  const [cleared, setCleared] = useState(false)
  const due = useQuery({ queryKey: DUE_KEY, queryFn: getDue })
  const owed = due.data ? Number(due.data.outstanding_due) > 0 : false

  return (
    <section className="stage">
      <PageHeader title="Pay your due" />
      {due.isPending ? (
        <LoadingState label="Loading your due…" />
      ) : due.isError ? (
        <ErrorState title="We couldn’t load your due" error={due.error} onRetry={() => void due.refetch()} />
      ) : cleared ? (
        <div className="grid max-w-3xl gap-6">
          <StatusMessage tone="success" message="Your due is cleared. You can book vehicles again." />
          <div>
            <Button asChild>
              <Link to="/app/search">Find a vehicle</Link>
            </Button>
          </div>
        </div>
      ) : !owed ? (
        <EmptyState
          title="You have no outstanding due"
          description="Nothing is owed on your account, so nothing stops you from booking."
          action={
            <Button asChild variant="outline">
              <Link to="/app/search">Find a vehicle</Link>
            </Button>
          }
        />
      ) : (
        <div className={RAIL_LAYOUT}>
          <div className="min-w-0">
            <DueForm
              due={due.data}
              onPaid={(after) => {
                setCleared(true)
                queryClient.setQueryData(DUE_KEY, { outstanding_due: after.outstanding_due })
              }}
            />
          </div>
          <StickyRail>
            <div className="grid gap-3 lg:pt-1">
              <h2 className="text-section">Outstanding due</h2>
              <p className="num-lg">{formatCurrency(due.data.outstanding_due, currency)}</p>
              <p className="text-sm text-muted-foreground">
                An amount not recovered from a security deposit. New bookings are paused until it is paid; the
                pause ends as soon as the payment goes through.
              </p>
            </div>
          </StickyRail>
        </div>
      )}
    </section>
  )
}
