import { NavLink } from 'react-router-dom'

import type { NavItem } from '@/app/navigation'
import { cn } from '@/lib/utils'

// Sidebar and drawer menu (docs/design/ui-brief.md, 6.0). The active item has
// the primary tint and an amber bar; planned items are quiet, not loud.
export function NavList({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <ul className="flex flex-col gap-px px-3 py-3">
      {items.map((item) => (
        <li key={item.to}>
          <NavLink
            to={item.to}
            end={item.to === '/app'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'relative flex min-h-9 items-center gap-3 rounded-md px-3 text-sm transition-colors',
                'focus-visible:-outline-offset-2',
                isActive
                  ? 'bg-primary-tint font-medium text-primary before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-signal'
                  : item.available
                    ? 'text-foreground hover:bg-hairline/70'
                    : 'text-ink-subtle hover:text-foreground',
              )
            }
          >
            <item.icon className="size-4 shrink-0" aria-hidden="true" />
            <span className="flex-1 whitespace-nowrap">{item.label}</span>
            {item.available ? null : (
              <span className="text-xs text-ink-subtle">Soon</span>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}
