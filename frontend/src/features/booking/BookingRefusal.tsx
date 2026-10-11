// The alternative flows of Exp 4 sequence 1, each with a clear message and a
// next step (UI-4). The server's `code` decides which; its `detail` is shown
// as the explanation. Announced at once and focused (role="alert", WCAG 4.1.3).

import { CircleAlert } from 'lucide-react'
import { type ReactNode, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'

const LICENCE_CODES = [
  'licence_not_verified',
  'licence_expired',
  'licence_expires_before_return',
  'licence_category',
]
const REHOLD_CODES = ['hold_expired', 'price_changed', 'discount_unavailable']

interface Explanation {
  title: string
  actions: ReactNode
}

function explain(code: string | undefined, onHoldAgain?: () => void, holding = false): Explanation {
  if (code && LICENCE_CODES.includes(code)) {
    // Book.Eligible.No: submit a licence now, continue browsing, or exit.
    return {
      title: 'Your driving licence doesn’t allow this booking yet',
      actions: (
        <>
          <Button asChild>
            <Link to="/app/licence">Submit your licence</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/app/search">Keep browsing</Link>
          </Button>
          <Button asChild variant="ghost">
            <Link to="/app">Exit</Link>
          </Button>
        </>
      ),
    }
  }
  switch (code) {
    case 'vehicle_unavailable':
      return {
        title: 'This vehicle has just been taken',
        actions: (
          <Button asChild>
            <Link to="/app/search">Choose another vehicle</Link>
          </Button>
        ),
      }
    case 'payment_declined':
      return {
        title: 'Your payment was declined',
        actions: null, // the payment form stays open for another card
      }
    case 'under_age':
    case 'customer_blacklisted':
    case 'outstanding_due':
      return {
        title: 'You can’t make this booking',
        actions: (
          <>
            <Button asChild variant="outline">
              <Link to="/app/search">Keep browsing</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/app">Exit</Link>
            </Button>
          </>
        ),
      }
    default:
      if (code && REHOLD_CODES.includes(code)) {
        return {
          title: code === 'hold_expired' ? 'Your hold on this vehicle has expired' : 'The price needs checking again',
          actions: onHoldAgain ? (
            <Button onClick={onHoldAgain} disabled={holding}>
              {holding ? 'Holding…' : 'Hold the vehicle again'}
            </Button>
          ) : null,
        }
      }
      return { title: 'We couldn’t complete this step', actions: null }
  }
}

/** A refused booking or payment, explained, with what the customer can do next. */
export function BookingRefusal({
  error,
  onHoldAgain,
  holding = false,
}: {
  error: unknown
  onHoldAgain?: () => void
  holding?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (error) ref.current?.focus()
  }, [error])
  if (!error) return null
  const code = error instanceof ApiError ? error.code : undefined
  const message = error instanceof Error ? error.message : 'Please try again.'
  const { title, actions } = explain(code, onHoldAgain, holding)
  return (
    <div
      ref={ref}
      tabIndex={-1}
      role="alert"
      data-code={code}
      className="grid gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4 outline-none"
    >
      <div className="flex items-start gap-2">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
        <div>
          <p className="font-medium">{title}</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  )
}
