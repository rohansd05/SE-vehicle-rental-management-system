import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'

import { getHealth } from '@/api/health'

/** The product name, Veyora (D24): the fallback until the health endpoint sends the configured name. */
export const PRODUCT_NAME = 'Veyora'
/** The product tagline (D24), shown in italics by the shared Tagline component. */
export const TAGLINE = 'Your Ride, Your Rules'
/** The backend's default AGENCY_NAME is a placeholder in square brackets: treated as "not set" (D24). */
const isPlaceholder = (name: string) => /^\[.*\]$/.test(name.trim())

/** The brand name comes from the health endpoint (D7, AGENCY_NAME), with Veyora as the fallback (D24). */
export function brandName(fromApi: string | undefined): string {
  return fromApi && !isPlaceholder(fromApi) ? fromApi : PRODUCT_NAME
}

export function useAgency() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, staleTime: 5 * 60_000 })
  return {
    name: brandName(health.data?.agency_name),
    currency: health.data?.currency ?? 'INR',
    health,
  }
}

export function usePageTitle(title: string) {
  const { name } = useAgency()
  useEffect(() => {
    document.title = `${title} - ${name}`
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
