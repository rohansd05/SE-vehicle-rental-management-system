import { CircleAlert, CircleCheck, Clock, IdCard } from 'lucide-react'

import type { Licence } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatDateTime } from '@/lib/dates'
import { cn } from '@/lib/utils'

import { STATUS_TONE } from './rules'

const TONE_STYLES = {
  neutral: 'bg-muted text-foreground',
  pending: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  good: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  bad: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
} as const

const TONE_ICONS = { neutral: IdCard, pending: Clock, good: CircleCheck, bad: CircleAlert } as const

export function LicenceStatusBadge({ status }: { status: Licence['status'] }) {
  const tone = STATUS_TONE[status]
  const Icon = TONE_ICONS[tone]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-medium',
        TONE_STYLES[tone],
      )}
    >
      <Icon className="size-4" aria-hidden="true" />
      {status}
    </span>
  )
}

function Explanation({ licence }: { licence: Licence }) {
  switch (licence.status) {
    case 'Not Submitted':
      return (
        <p>
          You haven’t submitted a driving licence yet. You need a verified licence before you can
          book a vehicle.
        </p>
      )
    case 'Pending Verification':
      return (
        <p>
          Our staff are checking your licence. We’ll e-mail you as soon as it has been verified.
          Submitted {formatDateTime(licence.updated_at)}.
        </p>
      )
    case 'Verified':
      return (
        <p>
          Your licence was verified on {formatDateTime(licence.verified_at)}. It is valid until{' '}
          {formatDate(licence.expiry_date)}. You can book vehicles in the categories it covers.
        </p>
      )
    case 'Rejected':
      return (
        <div className="grid gap-2">
          <p>We couldn’t verify your licence. Please fix the problem below and submit it again.</p>
          <p className="rounded-md border border-red-600/30 bg-red-600/5 px-3 py-2">
            <span className="font-medium">Reason: </span>
            {licence.rejection_reason || 'No reason was recorded.'}
          </p>
        </div>
      )
    case 'Expired':
      return (
        <p>
          Your licence expired on {formatDate(licence.expiry_date)}. Submit your renewed licence
          to keep booking.
        </p>
      )
  }
}

/** The customer's licence at a glance (Appendix A licence status). */
export function LicenceStatusCard({ licence }: { licence: Licence }) {
  return (
    <Card>
      <CardHeader className="gap-3">
        <CardTitle>
          <h2>Licence status</h2>
        </CardTitle>
        <div>
          <LicenceStatusBadge status={licence.status} />
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 text-sm">
        <Explanation licence={licence} />
        {licence.licence_number ? (
          <dl className="grid gap-2 sm:grid-cols-[10rem_1fr]">
            <dt className="text-muted-foreground">Licence number</dt>
            <dd className="font-medium">{licence.licence_number}</dd>
            <dt className="text-muted-foreground">Issued by</dt>
            <dd className="font-medium">{licence.issuing_authority || '—'}</dd>
            <dt className="text-muted-foreground">Valid</dt>
            <dd className="font-medium">
              {formatDate(licence.issue_date)} to {formatDate(licence.expiry_date)}
            </dd>
            <dt className="text-muted-foreground">Categories</dt>
            <dd className="font-medium">{licence.categories.join(', ') || '—'}</dd>
          </dl>
        ) : null}
      </CardContent>
    </Card>
  )
}
