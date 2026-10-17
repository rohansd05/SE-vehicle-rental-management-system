import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CircleAlert } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { StickyRail } from '@/components/sticky-rail'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { useSignedInUser } from '@/features/auth/auth-context'
import { TermsList } from '@/features/booking/PriceSummary'
import { BookingStatusBadge } from '@/features/history/BookingStatusBadge'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDateTime } from '@/lib/dates'
import { DETAILS_LIST, RAIL_LAYOUT } from '@/lib/layout'

import { getReturn, type Refusal, type ReturnDetail, type SettlementRecord } from './api'
import { returnKey } from './keys'
import { PhotoCompare } from './PhotoCompare'
import { ReturnForm } from './ReturnForm'
import { SettlementSummary } from './SettlementSummary'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium break-words">{children}</dd>
    </>
  )
}

function Refusals({ refusals }: { refusals: Refusal[] }) {
  return (
    <div role="alert" className="enter flex items-start gap-3 rounded-md border-l-2 border-l-status-unsafe bg-status-unsafe-tint px-4 py-3">
      <CircleAlert className="mt-1 size-5 shrink-0 text-status-unsafe" aria-hidden="true" />
      <div>
        <p className="font-medium">This vehicle cannot be returned</p>
        <ul className="mt-1 grid list-disc gap-1 pl-5 text-sm text-muted-foreground">
          {refusals.map((refusal) => (
            <li key={refusal.code}>{refusal.message}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

/** UC 13: a deposit refund above the approval limit waits for an Administrator. */
function refundText(settlement: SettlementRecord): string | null {
  switch (settlement.refund_status) {
    case 'Pending Approval':
      return 'Refund awaiting approval'
    case 'Issued':
      return settlement.refund_paid_out_by ? `Refunded in cash by ${settlement.refund_paid_out_by}` : 'Refunded'
    case 'Approved':
      return 'Refund to be paid out in cash at the branch'
    case 'Rejected':
      return 'Refund rejected'
    case 'Failed':
      return 'Refund failed'
    default:
      return null
  }
}

function Settled({ booking }: { booking: ReturnDetail }) {
  const { currency } = useAgency()
  const settlement = booking.settlement as SettlementRecord
  const report = booking.return_report
  const refund = refundText(settlement)
  return (
    <>
      <section aria-labelledby="return-settlement" className="grid gap-5 border-t pt-8">
        <h2 id="return-settlement">Signed settlement</h2>
        <SettlementSummary settlement={settlement} paid={booking.rental_paid} rentalTotal={booking.total_amount} />
        <dl className="@container grid gap-4">
          <div className={DETAILS_LIST}>
            {refund ? <Row label="Deposit balance">{refund}</Row> : null}
            {Number(settlement.due) > 0 ? (
              <Row label="Due">
                <span className="num">{formatCurrency(settlement.due, currency)}</span> recorded against the customer
              </Row>
            ) : null}
            {settlement.maintenance_job ? (
              <Row label="Maintenance">
                Job <span className="num">#{settlement.maintenance_job}</span> raised for the problem found at return
              </Row>
            ) : null}
          </div>
        </dl>
      </section>
      {report ? (
        <section aria-labelledby="return-report" className="@container grid gap-5 border-t pt-8">
          <h2 id="return-report">Return condition report</h2>
          <dl className={DETAILS_LIST}>
            <Row label="Odometer">
              <span className="num">{report.odometer_reading} km</span>
            </Row>
            <Row label="Distance travelled">
              <span className="num">{booking.distance_travelled} km</span>
            </Row>
            <Row label="Fuel or charge">
              <span className="num">{Number(report.fuel_level)}%</span>
            </Row>
            <Row label="Accessories returned">
              {report.accessories.length
                ? report.accessories.map((item) => `${item.name} × ${item.quantity}`).join(', ')
                : 'None'}
            </Row>
            <Row label="New damage">
              {report.damage_marks.length ? report.damage_marks.map((mark) => mark.note || 'Marked').join('; ') : 'None'}
            </Row>
            <Row label="Recorded by">{report.recorded_by}</Row>
            <Row label="Signed">
              <span className="num">{formatDateTime(report.signed_at)}</span>
            </Row>
          </dl>
          <PhotoCompare sides={booking.photo_sides} handover={booking.handover_report} returned={report} />
          {report.signature_url ? (
            <img src={report.signature_url} alt="Customer signature" className="h-32 w-full max-w-md rounded-md border bg-surface object-contain" />
          ) : null}
        </section>
      ) : null}
    </>
  )
}

/** Exp 2 use case 8: the rental, the return checklist and the settlement. */
export function ReturnPage() {
  const id = Number(useParams().id)
  const user = useSignedInUser()
  const { currency } = useAgency()
  const isStaff = user.role === 'BRANCH_STAFF'
  const [message, setMessage] = useState<string | null>(null)
  const [refused, setRefused] = useState<Refusal[] | null>(null)
  const detail = useQuery({ queryKey: returnKey(id), queryFn: () => getReturn(id) })

  const back = (
    <Button asChild variant="ghost" className="mb-2 -ml-2 h-10">
      <Link to={isStaff ? '/app/handover' : '/app/branch-bookings'}>
        <ArrowLeft aria-hidden="true" />
        {isStaff ? 'Back to handover and return' : 'Back to branch bookings'}
      </Link>
    </Button>
  )

  if (detail.isPending || detail.isError) {
    return (
      <section>
        {back}
        <PageHeader title="Return" />
        {detail.isPending ? (
          <LoadingState label="Loading the booking…" />
        ) : (
          <ErrorState title="We couldn’t load this booking" error={detail.error} onRetry={() => void detail.refetch()} />
        )}
      </section>
    )
  }

  const data = detail.data
  const refusals = refused ?? (data.settlement ? [] : data.refusals)
  const { vehicle } = data
  return (
    <section>
      {back}
      <PageHeader
        title={`Return · ${data.booking_reference}`}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <BookingStatusBadge status={data.status} />
            <VehicleStatusBadge status={vehicle.status} />
          </span>
        }
      />
      <div className="grid gap-4 has-[[role]>*]:mb-6">
        <StatusMessage message={message} tone="success" />
      </div>
      <div className={RAIL_LAYOUT}>
        <div className="grid min-w-0 content-start gap-8">
          {refusals.length ? <Refusals refusals={refusals} /> : null}
          <section aria-labelledby="return-booking" className="@container grid gap-4">
            <h2 id="return-booking">Booking</h2>
            <dl className={DETAILS_LIST}>
              <Row label="Customer">{data.customer_name}</Row>
              <Row label="Mobile">
                <span className="num">{data.customer_mobile}</span>
              </Row>
              <Row label="Vehicle">
                {vehicle.brand} {vehicle.model} ({vehicle.category}) ·{' '}
                <span className="num whitespace-nowrap">{vehicle.registration_no}</span>
              </Row>
              <Row label="Branch">{data.pickup_branch}</Row>
              <Row label="Return due">
                <span className="num">{formatDateTime(data.return_datetime)}</span>
              </Row>
            </dl>
          </section>
          {!data.settlement ? (
            <section aria-labelledby="return-terms" className="grid gap-4 border-t pt-8">
              <h2 id="return-terms">Rental terms</h2>
              <TermsList terms={data.terms} />
            </section>
          ) : null}
          {data.settlement ? <Settled booking={data} /> : null}
          {!data.settlement && isStaff && data.can_return && !refused ? (
            <div className="border-t pt-8">
              <ReturnForm
                booking={data}
                onRefused={setRefused}
                onDone={(next) =>
                  setMessage(
                    `Return complete. The booking is Completed and the vehicle is ${next.vehicle.status}. The customer has been e-mailed the settlement.`,
                  )
                }
              />
            </div>
          ) : null}
        </div>
        <StickyRail>
          <dl className="grid gap-4 text-sm lg:pt-1">
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Handed over</dt>
              <dd className="num font-medium">{formatDateTime(data.handed_over_at)}</dd>
            </div>
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Return due</dt>
              <dd className="num font-medium">{formatDateTime(data.return_datetime)}</dd>
            </div>
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Returned</dt>
              <dd className="num font-medium">{formatDateTime(data.returned_at)}</dd>
            </div>
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Security deposit</dt>
              <dd className="font-medium">
                <span className="num">{formatCurrency(data.security_deposit, currency)}</span>
                {data.deposit_method ? `, paid by ${data.deposit_method.toLowerCase()}` : ''}
              </dd>
            </div>
          </dl>
        </StickyRail>
      </div>
    </section>
  )
}
