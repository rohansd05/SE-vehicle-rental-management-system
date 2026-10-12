import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ROLE_LABELS } from '@/api/types'
import { type NavItem, navItemsFor } from '@/app/navigation'
import { PageHeader } from '@/components/page'
import { Photo } from '@/components/photo'
import { Badge } from '@/components/ui/badge'
import { useSignedInUser } from '@/features/auth/auth-context'
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
        photo="band-dashboard-1"
      />
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
