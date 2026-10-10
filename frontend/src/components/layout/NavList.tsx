import { NavLink } from 'react-router-dom'

import type { NavItem } from '@/app/navigation'
import { cn } from '@/lib/utils'

export function NavList({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <ul className="flex flex-col gap-0.5 p-2">
      {items.map((item) => (
        <li key={item.to}>
          <NavLink
            to={item.to}
            end={item.to === '/app'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex min-h-10 items-center gap-3 rounded-md px-3 text-sm transition-colors',
                'hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                isActive ? 'bg-primary/10 font-medium text-primary' : 'text-foreground',
              )
            }
          >
            <item.icon className="size-4 shrink-0" aria-hidden="true" />
            <span className="flex-1">{item.label}</span>
            {item.available ? null : (
              <span className="text-xs text-muted-foreground">Soon</span>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}
