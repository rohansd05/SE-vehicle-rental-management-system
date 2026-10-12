import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'

import { getHealth } from '@/api/health'

/** The product name, used only until the agency name has loaded. */
export const PRODUCT_NAME = 'Vehicle Rental Management System'

/** The agency name comes only from the health endpoint (D7). */
export function useAgency() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, staleTime: 5 * 60_000 })
  return {
    name: health.data?.agency_name || PRODUCT_NAME,
    currency: health.data?.currency ?? 'INR',
    health,
  }
}

export function usePageTitle(title: string) {
  const { name } = useAgency()
  useEffect(() => {
    document.title = `${title} · ${name}`
  }, [title, name])
}

/** Move focus to the main region after each navigation, so screen readers start there. */
export function useRouteFocus<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const { pathname, hash } = useLocation()
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    // Focusing <main> must not scroll its top under the sticky top bar; the
    // new page starts at the top instead, unless it opens at a #topic.
    ref.current?.focus({ preventScroll: true })
    if (!hash) document.documentElement.scrollTop = 0
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only a new page moves focus
  }, [pathname])
  return ref
}
