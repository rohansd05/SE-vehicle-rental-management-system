import { type ComponentProps, useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

/**
 * Rises its content into view once, the first time it scrolls into the
 * viewport (docs/design/ui-brief.md, section 5). Where IntersectionObserver
 * is missing (jsdom), or before it has reported, nothing is hidden for long:
 * the content is shown at once.
 */
export function Reveal({ className, children, ...props }: ComponentProps<'div'>) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(() => typeof IntersectionObserver === 'undefined')

  useEffect(() => {
    const element = ref.current
    if (shown || !element) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShown(true)
          observer.disconnect()
        }
      },
      { rootMargin: '0px 0px -10% 0px' },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [shown])

  return (
    <div ref={ref} data-in={shown ? '' : undefined} className={cn('reveal', className)} {...props}>
      {children}
    </div>
  )
}
