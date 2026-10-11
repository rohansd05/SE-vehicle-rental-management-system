import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { navItemsFor } from '@/app/navigation'
import { useAuth } from '@/features/auth/auth-context'

/**
 * The side column of the help, 403 and 404 pages (docs/design/ui-brief.md,
 * 6.9): where the reader can go from here. Signed in, it lists the role's
 * available screens with their menu descriptions; signed out, the two
 * public actions. Link names are the ones the menu and home page already use.
 */
export function WhereToGo() {
  const { user } = useAuth()
  const items = user
    ? navItemsFor(user.role)
        .filter((item) => item.available)
        .map((item) => ({ to: item.to, label: item.label, description: item.description }))
    : [
        { to: '/login', label: 'Sign in', description: null },
        { to: '/register', label: 'Create an account', description: null },
      ]

  return (
    <aside aria-labelledby="where-to-go" className="lg:border-l lg:pl-10">
      <h2 id="where-to-go" className="text-section font-semibold">
        Where to go
      </h2>
      <ul className="mt-2 divide-y">
        {items.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              className="group flex items-center gap-3 py-3 text-sm hover:text-primary"
            >
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{item.label}</span>
                {item.description ? (
                  <span className="block text-small text-muted-foreground">{item.description}</span>
                ) : null}
              </span>
              <ChevronRight className="size-4 shrink-0 text-ink-subtle group-hover:text-primary" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  )
}
