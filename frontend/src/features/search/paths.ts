import { useLocation } from 'react-router-dom'

/**
 * Search.Browse: the catalogue runs at /search and /vehicles/:id for a guest
 * and at /app/search and /app/vehicles/:id inside the signed-in app. Links
 * between its pages stay on the side they started from.
 */
export function useCatalogueBase(): '' | '/app' {
  return useLocation().pathname.startsWith('/app/') ? '/app' : ''
}
