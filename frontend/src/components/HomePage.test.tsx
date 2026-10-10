import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { API, server, signedInAs } from '@/test/server'
import { renderApp } from '@/test/render'

describe('HomePage', () => {
  it('shows the agency name and currency from the health endpoint (D7)', async () => {
    renderApp({ route: '/' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Test Rentals' })).toBeInTheDocument()
    expect(screen.getByText('INR')).toBeInTheDocument()
    expect(screen.getByText('Online')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Check again' })).toBeEnabled()
  })

  it('offers registration and sign-in when signed out', async () => {
    renderApp({ route: '/' })
    expect(await screen.findByRole('link', { name: 'Create an account' })).toHaveAttribute('href', '/register')
    expect(screen.getAllByRole('link', { name: 'Sign in' })[0]).toHaveAttribute('href', '/login')
  })

  it('offers the account when signed in', async () => {
    signedInAs('CUSTOMER')
    renderApp({ route: '/' })
    expect(await screen.findByRole('link', { name: 'Go to my account' })).toHaveAttribute('href', '/app')
  })

  it('shows a degraded backend from a 503 health body', async () => {
    server.use(
      http.get(`${API}/health/`, () =>
        HttpResponse.json(
          { status: 'degraded', database: 'unreachable', agency_name: 'Test Rentals', currency: 'INR' },
          { status: 503 },
        ),
      ),
    )
    renderApp({ route: '/' })
    expect(await screen.findByText('Degraded')).toBeInTheDocument()
    expect(screen.getByText('Unreachable')).toBeInTheDocument()
  })
})
