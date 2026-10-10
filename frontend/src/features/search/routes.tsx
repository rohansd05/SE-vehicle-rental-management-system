// Search routes, mounted under /app by one line in AppRoutes. Returned as a
// fragment of <Route>s (not a component) so <Routes> can read them.
// The search API itself is public (Search.Browse); RequireRole only shapes
// the signed-in menu, and booking is refused by the server to anyone but a
// customer (SE-4).

import { Route } from 'react-router-dom'

import { RequireRole } from '@/app/guards'

import { SearchPage } from './SearchPage'

export function searchRoutes() {
  return (
    <Route
      path="search"
      element={
        <RequireRole roles={['CUSTOMER']}>
          <SearchPage />
        </RequireRole>
      }
    />
  )
}
