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
import { getBooking } from '@/features/booking/api'
import { bookingKey } from '@/features/booking/keys'
import { BookingStatusBadge } from '@/features/history/BookingStatusBadge'
import { formatDate, formatDateTime } from '@/lib/dates'
import { DETAILS_LIST, RAIL_LAYOUT } from '@/lib/layout'

import { type ConditionReport, getHandover, type HandoverDetail, type Refusal } from './api'
import { HandoverForm } from './HandoverForm'
import { handoverKey } from './keys'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium break-words">{children}</dd>
    </>
  )
}

/** Handover.Refuse: every condition that blocks the handover, in the server's words. */
function Refusals({ refusals }: { refusals: Refusal[] }) {
  return (
    <div role="alert" className="enter flex items-start gap-3 rounded-md border-l-2 border-l-status-unsafe bg-status-unsafe-tint px-4 py-3">
      <CircleAlert className="mt-1 size-5 shrink-0 text-status-unsafe" aria-hidden="true" />
      <div>
        <p className="font-medium">This vehicle cannot be handed over</p>
        <ul className="mt-1 grid list-disc gap-1 pl-5 text-sm text-muted-foreground">
          {refusals.map((refusal) => (
            <li key={refusal.code}>{refusal.message}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

/**
 * Book.Deliver.Location (Module R4): a doorstep delivery's address, display only.
 * Read from the booking, so the rentals API is unchanged.
 */
function DeliveryRow({ bookingId }: { bookingId: number }) {
  const booking = useQuery({ queryKey: bookingKey(bookingId), queryFn: () => getBooking(bookingId) })
  if (!booking.data?.delivery_address) return null
  return (
    <Row label="Doorstep delivery">
      {booking.data.delivery_address}, <span className="num">{booking.data.delivery_pincode}</span>
    </Row>
  )
}

function BookingDetails({ handover }: { handover: HandoverDetail }) {
  const { vehicle, licence } = handover
  return (
    <>
      <section aria-labelledby="handover-booking" className="@container grid gap-4">
        <h2 id="handover-booking">Booking</h2>
        <dl className={DETAILS_LIST}>
          <Row label="Customer">{handover.customer_name}</Row>
          <Row label="Mobile">
            <span className="num">{handover.customer_mobile}</span>
          </Row>
          <Row label="Vehicle">
            {vehicle.brand} {vehicle.model} ({vehicle.category}) ·{' '}
            <span className="num whitespace-nowrap">{vehicle.registration_no}</span>
          </Row>
          <Row label="Branch">{handover.pickup_branch}</Row>
          <DeliveryRow bookingId={handover.id} />
          <Row label="Pickup">
            <span className="num">{formatDateTime(handover.pickup_datetime)}</span>
          </Row>
          <Row label="Return">
            <span className="num">{formatDateTime(handover.return_datetime)}</span>
          </Row>
        </dl>
      </section>
      <section aria-labelledby="handover-licence" className="@container grid gap-4 border-t pt-8">
        <h2 id="handover-licence">Driving licence</h2>
        {licence ? (
          <dl className={DETAILS_LIST}>
            <Row label="Licence number">
              <span className="num">{licence.licence_number || '—'}</span>
            </Row>
            <Row label="Status">{licence.status}</Row>
            <Row label="Expires">
              <span className="num">{formatDate(licence.expiry_date)}</span>
            </Row>
            <Row label="Covers">{licence.categories.join(', ') || '—'}</Row>
          </dl>
        ) : (
          <p className="text-sm text-muted-foreground">The customer has not submitted a licence.</p>
        )}
      </section>
    </>
  )
}

/** Handover.Sign: the stored report, read only. Photos and the signature come through signed links (SI-3). */
function SignedReport({ report }: { report: ConditionReport }) {
  return (
    <section aria-labelledby="handover-report" className="@container grid gap-5 border-t pt-8">
      <h2 id="handover-report">Signed condition report</h2>
      <dl className={DETAILS_LIST}>
        <Row label="Odometer">
          <span className="num">{report.odometer_reading} km</span>
        </Row>
        <Row label="Fuel or charge">
          <span className="num">{Number(report.fuel_level)}%</span>
        </Row>
        <Row label="Accessories issued">
          {report.accessories.length
            ? report.accessories.map((item) => `${item.name} × ${item.quantity}`).join(', ')
            : 'None'}
        </Row>
        <Row label="Existing damage">
          {report.damage_marks.length ? report.damage_marks.map((mark) => mark.note || 'Marked').join('; ') : 'None'}
        </Row>
        <Row label="Recorded by">{report.recorded_by}</Row>
        <Row label="Signed">
          <span className="num">{formatDateTime(report.signed_at)}</span>
        </Row>
      </dl>
      <ul aria-label="Condition photos" className="grid grid-cols-2 gap-3 @xl:grid-cols-4">
        {report.photos.map((photo, index) => (
          <li key={index} className="grid gap-1.5">
            {photo.url ? (
              <img src={photo.url} alt={`${photo.caption} of the vehicle`} className="aspect-[4/3] w-full rounded-md border object-cover" />
            ) : null}
            <span className="text-small text-muted-foreground">{photo.caption}</span>
          </li>
        ))}
      </ul>
      {report.signature_url ? (
        <img src={report.signature_url} alt="Customer signature" className="h-32 w-full max-w-md rounded-md border bg-surface object-contain" />
      ) : null}
    </section>
  )
}

/** Exp 2 use case 7: the booking, the re-verified licence, the checklist and the signature. */
export function HandoverPage() {
  const id = Number(useParams().id)
  const user = useSignedInUser()
  const isStaff = user.role === 'BRANCH_STAFF'
  const [message, setMessage] = useState<string | null>(null)
  const [refused, setRefused] = useState<Refusal[] | null>(null)
  const handover = useQuery({ queryKey: handoverKey(id), queryFn: () => getHandover(id) })

  const back = (
    <Button asChild variant="ghost" className="mb-2 -ml-2 h-10">
      <Link to={isStaff ? '/app/handover' : '/app/branch-bookings'}>
        <ArrowLeft aria-hidden="true" />
        {isStaff ? 'Back to handover and return' : 'Back to branch bookings'}
      </Link>
    </Button>
  )

  if (handover.isPending || handover.isError) {
    return (
      <section>
        {back}
        <PageHeader title="Handover" />
        {handover.isPending ? (
          <LoadingState label="Loading the booking…" />
        ) : (
          <ErrorState title="We couldn’t load this booking" error={handover.error} onRetry={() => void handover.refetch()} />
        )}
      </section>
    )
  }

  const data = handover.data
  const refusals = refused ?? (data.report ? [] : data.refusals)
  return (
    <section>
      {back}
      <PageHeader
        title={`Handover · ${data.booking_reference}`}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <BookingStatusBadge status={data.status} />
            <VehicleStatusBadge status={data.vehicle.status} />
          </span>
        }
      />
      <div className="grid gap-4 has-[[role]>*]:mb-6">
        <StatusMessage message={message} tone="success" />
      </div>
      <div className={RAIL_LAYOUT}>
        <div className="grid min-w-0 content-start gap-8">
          {refusals.length ? <Refusals refusals={refusals} /> : null}
          <BookingDetails handover={data} />
          {data.report ? <SignedReport report={data.report} /> : null}
          {data.status === 'Active' || data.status === 'Completed' ? (
            <div>
              <Button asChild variant={data.status === 'Active' && isStaff ? 'default' : 'outline'} size="lg">
                <Link to={`/app/returns/${data.id}`}>
                  {data.status === 'Active' && isStaff ? 'Record the return' : 'View the return'}
                </Link>
              </Button>
            </div>
          ) : null}
          {!data.report && isStaff && data.can_hand_over && !refused ? (
            <div className="border-t pt-8">
              <HandoverForm
                handover={data}
                onRefused={setRefused}
                onDone={() =>
                  setMessage(
                    'Handover complete. The booking is Active, the vehicle is On Rent and the customer has been e-mailed a copy of the signed report.',
                  )
                }
              />
            </div>
          ) : null}
        </div>
        <StickyRail>
          <dl className="grid gap-4 text-sm lg:pt-1">
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Pickup</dt>
              <dd className="num font-medium">{formatDateTime(data.pickup_datetime)}</dd>
            </div>
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Return</dt>
              <dd className="num font-medium">{formatDateTime(data.return_datetime)}</dd>
            </div>
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Handed over</dt>
              <dd className="num font-medium">{formatDateTime(data.handed_over_at)}</dd>
            </div>
          </dl>
        </StickyRail>
      </div>
    </section>
  )
}
