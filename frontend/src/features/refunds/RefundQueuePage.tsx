import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Field, StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDateTime } from '@/lib/dates'
import { stagger } from '@/lib/motion'

import { BOOKINGS_KEY } from '@/features/booking/keys'
import { approveRefund, listRefunds, type Refund, rejectRefund } from '@/features/payment/api'
import { REFUNDS_KEY, refundsKey } from '@/features/payment/keys'
import { PasswordDialog } from '@/features/payment/PasswordDialog'

/** What the Administrator's decision did, in words (UC 13 step 3). */
function outcome(refund: Refund, amount: string): string {
  if (refund.status === 'Issued') return `Refund of ${amount} approved and issued to the original payment method.`
  if (refund.status === 'Approved') return `Refund of ${amount} approved. The branch pays it out in cash.`
  return `The payment gateway refused the refund: ${refund.failure_reason}`
}

function RejectRefundDialog({ refund, onDone }: { refund: Refund; onDone: (message: string) => void }) {
  const [reason, setReason] = useState('')
  const id = `reject-${refund.id}`
  return (
    <PasswordDialog
      id={id}
      trigger="Reject"
      variant="destructive"
      title="Reject this refund?"
      description={`${refund.customer_name} will receive this reason by e-mail.`}
      submitLabel="Reject refund"
      busyLabel="Rejecting…"
      cancelLabel="Keep it pending"
      check={() => (reason.trim() ? null : 'Give the reason for rejecting the refund.')}
      onClose={() => setReason('')}
      onConfirm={async (password) => {
        await rejectRefund(refund.id, reason.trim(), password)
        onDone('Refund rejected. The customer has been told why.')
      }}
    >
      <Field id={`${id}-reason`} label="Reason">
        <Textarea id={`${id}-reason`} rows={4} value={reason} onChange={(event) => setReason(event.target.value)} />
      </Field>
    </PasswordDialog>
  )
}

function RefundRow({ refund, index, onDone }: { refund: Refund; index: number; onDone: (message: string) => void }) {
  const { currency } = useAgency()
  const amount = formatCurrency(refund.amount, currency)
  return (
    <li
      className="enter grid min-w-0 gap-x-8 gap-y-3 border-b py-5 @xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_auto] @xl:items-center"
      style={stagger(index)}
    >
      <span className="grid min-w-0 gap-1.5">
        <span className="font-medium">{refund.customer_name}</span>
        <span className="num text-sm whitespace-nowrap text-muted-foreground">{refund.booking_reference}</span>
      </span>
      <span className="grid min-w-0 gap-1.5 text-sm">
        <span>
          <span className="num-strong whitespace-nowrap">{amount}</span> of the {refund.purpose.toLowerCase()} ·{' '}
          {refund.method}
        </span>
        <span>{refund.reason}</span>
        <span className="text-muted-foreground">
          Asked <span className="num whitespace-nowrap">{formatDateTime(refund.requested_at)}</span>
          {refund.requested_by_name ? ` by ${refund.requested_by_name}` : ''}
        </span>
      </span>
      <span className="flex flex-wrap gap-3">
        <PasswordDialog
          id={`approve-${refund.id}`}
          trigger="Approve"
          title="Approve this refund?"
          description={`${amount} goes back to ${refund.customer_name}’s original payment method, and you are recorded as the approver.`}
          submitLabel="Approve and issue"
          busyLabel="Issuing the refund…"
          cancelLabel="Keep it pending"
          onConfirm={async (password) => onDone(outcome(await approveRefund(refund.id, password), amount))}
        />
        <RejectRefundDialog refund={refund} onDone={onDone} />
      </span>
    </li>
  )
}

/** Exp 2 UC 13 Approve Refund: refunds above the automatic approval limit, oldest first. */
export function RefundQueuePage() {
  const queryClient = useQueryClient()
  const [flash, setFlash] = useState<string | null>(null)
  const queue = useQuery({ queryKey: refundsKey('Pending Approval'), queryFn: () => listRefunds('Pending Approval') })

  const done = (message: string) => {
    setFlash(message)
    void queryClient.invalidateQueries({ queryKey: REFUNDS_KEY })
    void queryClient.invalidateQueries({ queryKey: BOOKINGS_KEY })
  }

  return (
    <section>
      <PageHeader
        title="Refunds"
        photo="band-payment-1"
        variant="compact"
        description="Refunds above the automatic approval limit wait here. Approve to issue them to the original payment method, or reject with a reason."
        actions={
          <Button variant="outline" onClick={() => void queue.refetch()} disabled={queue.isFetching}>
            {queue.isFetching ? 'Refreshing…' : 'Refresh'}
          </Button>
        }
      />
      <div className="mb-4">
        <StatusMessage message={flash} tone="success" />
      </div>
      {queue.isPending ? (
        <LoadingState label="Loading the refund queue…" rows={2} />
      ) : queue.isError ? (
        <ErrorState title="We couldn’t load the queue" error={queue.error} onRetry={() => void queue.refetch()} />
      ) : queue.data.results.length === 0 ? (
        <EmptyState title="Nothing to approve" description="No refunds are waiting for an Administrator’s approval." />
      ) : (
        <>
          <p className="mb-3 text-sm text-muted-foreground">
            {queue.data.count} {queue.data.count === 1 ? 'refund is' : 'refunds are'} waiting.
          </p>
          <ul className="@container border-t">
            {queue.data.results.map((refund, index) => (
              <RefundRow key={refund.id} refund={refund} index={index} onDone={done} />
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
