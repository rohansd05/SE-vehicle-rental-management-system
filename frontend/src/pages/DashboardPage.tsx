import { useQuery } from '@tanstack/react-query'
import { ChevronRight, CircleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'

import { type Role, ROLE_LABELS } from '@/api/types'
import { type NavItem, navItemsFor } from '@/app/navigation'
import { PageHeader } from '@/components/page'
import { Photo } from '@/components/photo'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useSignedInUser } from '@/features/auth/auth-context'
import { getDue } from '@/features/payment/api'
import { DUE_KEY } from '@/features/payment/keys'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { stagger } from '@/lib/motion'

/**
 * One photo per destination (B14; photos from the image registry, whole
 * subject in a 3:2 frame). A destination without one keeps the compact row.
 */
const DESTINATION_PHOTOS: Record<string, string> = {
  '/app/search': 'step-search-1',
  '/app/bookings': 'band-bookings-1',
  '/app/licence': 'band-licence-1',
  '/app/profile': 'step-account-1',
  '/app/licences': 'band-licence-checks-1',
  '/app/maintenance': 'band-maintenance-1',
  '/app/jobs': 'band-technician-1',
  '/app/clearances': 'band-clearances-2',
}

/**
 * The home page's header photo per role (Stage 5): the customer's dashboard
 * gauges; a key handover at a branch for staff; the workshop for
 * technicians; the branch office for managers; the dashboard overview for
 * administrators. None repeats a tile photo on the same page.
 */
const HOME_PHOTO: Record<Role, string> = {
  CUSTOMER: 'band-dashboard-1',
  BRANCH_STAFF: 'step-collect-1',
  MAINTENANCE_TECHNICIAN: 'band-maintenance-1',
  BRANCH_MANAGER: 'band-licence-checks-1',
  ADMINISTRATOR: 'band-dashboard-1',
}

const LINK_FOCUS = 'focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none'

/** An image-led destination tile, in the vehicle tiles' family: photo, then icon, label and description. */
function DestinationTile({ item, photo }: { item: NavItem; photo: string }) {
  return (
    <Link
      to={item.to}
      className={`group/tile flex h-full flex-col overflow-hidden rounded-xl border bg-surface transition-[transform,border-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-line-strong ${LINK_FOCUS}`}
    >
      <Photo id={photo} alt="" sizes="(min-width: 1024px) 40vw, 100vw" className="aspect-[3/2]" />
      <span className="flex flex-1 items-start gap-3 p-4 sm:gap-4 sm:p-6">
        <item.icon className="mt-1 size-6 shrink-0 text-primary" aria-hidden="true" />
        <span className="min-w-0 flex-1">
          <span className="heading block text-subsection transition-colors group-hover/tile:text-primary">{item.label}</span>
          <span className="mt-1.5 block text-sm text-muted-foreground">{item.description}</span>
        </span>
        <ChevronRight className="mt-1 hidden size-5 shrink-0 text-muted-foreground sm:block" aria-hidden="true" />
      </span>
    </Link>
  )
}

/** A compact row: a destination without a photo, or one planned for a later release. */
function DestinationRow({ item }: { item: NavItem }) {
  return (
    <Link
      to={item.to}
      className={`flex h-full items-start gap-4 rounded-xl border p-5 transition-colors hover:bg-muted ${LINK_FOCUS}`}
    >
      <item.icon className="mt-1 size-6 shrink-0 text-primary" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2 font-medium">
          {item.label}
          {item.available ? null : <Badge variant="secondary">Not available yet</Badge>}
        </span>
        <span className="mt-1 block text-sm text-muted-foreground">{item.description}</span>
      </span>
      <ChevronRight className="mt-1 size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
    </Link>
  )
}

/** Pay.Dues: "shall display it on the customer's home screen" (BR-4 blocks booking until paid). */
function DueNotice() {
  const { currency } = useAgency()
  const due = useQuery({ queryKey: DUE_KEY, queryFn: getDue })
  if (!due.data || !(Number(due.data.outstanding_due) > 0)) return null
  return (
    <div className="enter mb-6 flex flex-wrap items-start gap-x-4 gap-y-3 rounded-md border-l-2 border-l-signal bg-signal-tint px-4 py-3">
      <CircleAlert className="mt-1 size-4.5 shrink-0 text-signal-ink" aria-hidden="true" />
      <p className="min-w-0 flex-1 text-sm">
        You have an outstanding due of{' '}
        <strong className="num-strong whitespace-nowrap">{formatCurrency(due.data.outstanding_due, currency)}</strong>. New
        bookings are paused until it is paid.
      </p>
      {/* Default size: with size="sm", cn() reads its text-small as a colour and drops text-primary-foreground. */}
      <Button asChild>
        <Link to="/app/due">Pay your due</Link>
      </Button>
    </div>
  )
}

/** The signed-in home page: what this role can do, and what is coming. */
export function DashboardPage() {
  const user = useSignedInUser()
  const items = navItemsFor(user.role).filter((item) => item.to !== '/app')
  const tiles = items.filter((item) => item.available && DESTINATION_PHOTOS[item.to])
  const rows = items.filter((item) => !tiles.includes(item))

  return (
    <section>
      <PageHeader
        title={`Welcome, ${user.name}`}
        description={`Signed in as ${ROLE_LABELS[user.role]}.`}
        photo={HOME_PHOTO[user.role]}
      />
      {user.role === 'CUSTOMER' ? <DueNotice /> : null}
      {tiles.length ? (
        <ul className="grid gap-6 lg:grid-cols-2">
          {tiles.map((item, index) => (
            <li key={item.to} className="enter" style={stagger(index + 2)}>
              <DestinationTile item={item} photo={DESTINATION_PHOTOS[item.to]} />
            </li>
          ))}
        </ul>
      ) : null}
      {rows.length ? (
        <ul className="mt-6 grid gap-4 border-t pt-6 lg:grid-cols-2">
          {rows.map((item) => (
            <li key={item.to}>
              <DestinationRow item={item} />
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
