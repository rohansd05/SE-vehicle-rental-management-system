import { useEffect, useState } from 'react'

/**
 * True once the page has scrolled, so a sticky top bar can show its hairline
 * edge only when content passes under it (docs/design/ui-brief.md, B5).
 */
export function useScrolled(threshold = 4): boolean {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])
  return scrolled
}
