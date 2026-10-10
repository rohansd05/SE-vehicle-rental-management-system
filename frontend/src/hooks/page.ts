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
  const { pathname } = useLocation()
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    ref.current?.focus()
  }, [pathname])
  return ref
}
