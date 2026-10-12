import { type ComponentProps, useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

/**
 * The right-hand summary column of a detail page (docs/design/ui-brief.md,
 * 6.6). From 1024 px it sticks below the top bar; while it is docked, a
 * hairline fades in along its top edge so it reads as pinned. Below 1024 px
 * it simply follows the main column.
 */
export function StickyRail({ className, children, ...props }: ComponentProps<'div'>) {
  const sentinel = useRef<HTMLDivElement>(null)
  const [docked, setDocked] = useState(false)

  useEffect(() => {
    const element = sentinel.current
    if (!element || typeof IntersectionObserver === 'undefined') return
    // The sentinel sits just above the rail; once it scrolls under the top
    // bar the rail is docked.
    const observer = new IntersectionObserver(([entry]) => setDocked(!entry.isIntersecting), {
      rootMargin: '-80px 0px 0px 0px',
      threshold: 0,
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return (
    <div className={cn('min-w-0 lg:self-start', className)} {...props}>
      <div ref={sentinel} aria-hidden="true" className="h-px" />
      <div
        data-docked={docked ? '' : undefined}
        className="relative lg:sticky lg:top-20 before:absolute before:inset-x-0 before:-top-px before:h-px before:bg-hairline before:opacity-0 before:transition-opacity before:duration-200 data-docked:before:opacity-100"
      >
        {children}
      </div>
    </div>
  )
}
