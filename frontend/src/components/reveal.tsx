import { type HTMLAttributes, type Ref, useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

/**
 * Rises its content into view once, the first time it scrolls into the
 * viewport (docs/design/ui-brief.md, B5). By default the browser drives it
 * with a CSS scroll timeline where supported (`reveal`); `staggered` uses the
 * IntersectionObserver path only (`reveal-io`), so siblings can rise one
 * after another with `--enter-delay`. Where IntersectionObserver is missing
 * (jsdom), or before it has reported, nothing is hidden: the content shows.
 */
export function Reveal({
  className,
  children,
  staggered = false,
  as: Tag = 'div',
  ...props
}: HTMLAttributes<HTMLElement> & { staggered?: boolean; as?: 'div' | 'li' }) {
  const ref = useRef<HTMLElement>(null)
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

  const shared = {
    'data-in': shown ? '' : undefined,
    className: cn(staggered ? 'reveal-io' : 'reveal', className),
    ...props,
  }
  // Two explicit elements rather than a dynamic tag, so each gets a correctly typed ref.
  if (Tag === 'li') {
    return (
      <li ref={ref as Ref<HTMLLIElement>} {...shared}>
        {children}
      </li>
    )
  }
  return (
    <div ref={ref as Ref<HTMLDivElement>} {...shared}>
      {children}
    </div>
  )
}
