import { ChevronRight } from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router-dom'

import { cn } from '@/lib/utils'

// Queue and list rows for operational pages (docs/design/ui-brief.md, 6.4.1):
// one hairline between rows, no boxes, a quiet hover, the row's whole width
// a single link with a chevron. Once the list itself is 36 rem wide (a
// container query, so the sidebar is allowed for) a row's cells sit in
// aligned columns; below that they stack, same data, same labels.

/** The list: a hairline above the first row and under every row. */
export function RowList({ children, className }: { children: ReactNode; className?: string }) {
  return <ul className={cn('@container grid grid-cols-[minmax(0,1fr)] border-t', className)}>{children}</ul>
}

/** One row. `columns` is the grid template of the row's cells from a 36 rem list (`@xl:`). */
export function RowLink({
  to,
  state,
  columns,
  srLabel,
  children,
  style,
}: {
  to: string
  state?: LinkProps['state']
  columns: string
  /** Visually hidden text naming the action, kept from the old card ("Open job", "Review"). */
  srLabel: string
  children: ReactNode
  style?: CSSProperties
}) {
  return (
    <li className="enter min-w-0 border-b" style={style}>
      <Link
        to={to}
        state={state}
        className="group -mx-3 flex items-center gap-4 rounded-md px-3 py-5 transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <span className={cn('grid min-w-0 flex-1 gap-x-8 gap-y-2 @xl:items-center', columns)}>{children}</span>
        <span className="sr-only">{srLabel}</span>
        <ChevronRight
          className="size-5 shrink-0 text-ink-subtle transition-colors group-hover:text-primary"
          aria-hidden="true"
        />
      </Link>
    </li>
  )
}
