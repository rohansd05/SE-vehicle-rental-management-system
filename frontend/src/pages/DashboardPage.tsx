import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ROLE_LABELS } from '@/api/types'
import { navItemsFor } from '@/app/navigation'
import { PageHeader } from '@/components/page'
import { Badge } from '@/components/ui/badge'
import { useSignedInUser } from '@/features/auth/auth-context'

/** The signed-in home page: what this role can do, and what is coming. */
export function DashboardPage() {
  const user = useSignedInUser()
  const items = navItemsFor(user.role).filter((item) => item.to !== '/app')

  return (
    <section>
      <PageHeader
        title={`Welcome, ${user.name}`}
        description={`Signed in as ${ROLE_LABELS[user.role]}.`}
      />
      <ul className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              className="flex h-full items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <item.icon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2 font-medium">
                  {item.label}
                  {item.available ? null : <Badge variant="secondary">Not available yet</Badge>}
                </span>
                <span className="mt-1 block text-sm text-muted-foreground">{item.description}</span>
              </span>
              <ChevronRight className="mt-0.5 size-4 text-muted-foreground" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
