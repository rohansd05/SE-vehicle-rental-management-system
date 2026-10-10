import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { type ReactNode, useState } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { AppRoutes } from '@/app/AppRoutes'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { createQueryClient } from '@/lib/query-client'

interface Options {
  route?: string
  state?: unknown
}

function Providers({ children, route = '/', state }: Options & { children: ReactNode }) {
  const [client] = useState(() => {
    const queryClient = createQueryClient()
    queryClient.setDefaultOptions({ queries: { retry: false }, mutations: { retry: false } })
    return queryClient
  })
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: route, state }]}>
        <AuthProvider>{children}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

/** The whole app (routes, guards, shell) at `route`, against the MSW API. */
export function renderApp(options: Options = {}) {
  return render(
    <Providers {...options}>
      <AppRoutes />
    </Providers>,
  )
}

/** One component inside the same providers, for focused tests. */
export function renderWithProviders(ui: ReactNode, options: Options = {}) {
  return render(<Providers {...options}>{ui}</Providers>)
}
