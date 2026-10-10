// Like renderApp (src/test/render.tsx), but the route may carry a query
// string, which the Book Vehicle screens read (the searched period).
// Kept here so the shared test helper stays unchanged.

import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter, parsePath } from 'react-router-dom'

import { AppRoutes } from '@/app/AppRoutes'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { createQueryClient } from '@/lib/query-client'

export function renderAppAt(route: string, state?: unknown) {
  const client = createQueryClient()
  client.setDefaultOptions({ queries: { retry: false }, mutations: { retry: false } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ ...parsePath(route), state }]}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
