// UI-1, SE-4: each role reaches its own pages and gets 403 elsewhere.
// (The API enforces the same rules on every request.)

import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Role } from '@/api/types'
import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

const FORBIDDEN = 'You don’t have access to this page'

const NOT_SUBMITTED = {
  id: 1,
  licence_number: '',
  issuing_authority: '',
  issue_date: null,
  expiry_date: null,
  categories: [],
  status: 'Not Submitted',
  rejection_reason: '',
  verified_at: null,
  front_image_url: null,
  back_image_url: null,
  updated_at: '2026-10-01T10:00:00Z',
}

beforeEach(() => {
  server.use(
    http.get(`${API}/licence/`, () => HttpResponse.json(NOT_SUBMITTED)),
    http.get(`${API}/licences/`, () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  )
})

const ALLOWED: [Role, string, string][] = [
  ['CUSTOMER', '/app/licence', 'Driving licence'],
  ['CUSTOMER', '/app/bookings', 'My bookings'],
  ['BRANCH_STAFF', '/app/licences', 'Licence checks'],
  ['BRANCH_STAFF', '/app/handover', 'Handover and return'],
  ['MAINTENANCE_TECHNICIAN', '/app/jobs', 'Maintenance jobs'],
  ['ADMINISTRATOR', '/app/licences', 'Licence checks'],
  ['ADMINISTRATOR', '/app/fleet', 'Fleet'],
  ['BRANCH_MANAGER', '/app/reports', 'Reports'],
  ['BRANCH_MANAGER', '/app/branch-bookings', 'Branch bookings'],
]

const DENIED: [Role, string][] = [
  ['CUSTOMER', '/app/licences'],
  ['CUSTOMER', '/app/fleet'],
  ['BRANCH_STAFF', '/app/licence'],
  ['BRANCH_STAFF', '/app/jobs'],
  ['MAINTENANCE_TECHNICIAN', '/app/licences'],
  ['MAINTENANCE_TECHNICIAN', '/app/licence'],
  ['ADMINISTRATOR', '/app/licence'],
  ['ADMINISTRATOR', '/app/handover'],
  ['BRANCH_MANAGER', '/app/licences'],
  ['BRANCH_MANAGER', '/app/fleet'],
]

describe('role guard', () => {
  it.each(ALLOWED)('%s reaches %s', async (role, route, title) => {
    signedInAs(role)
    renderApp({ route })
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    expect(screen.queryByText(FORBIDDEN)).not.toBeInTheDocument()
  })

  it.each(DENIED)('%s gets 403 at %s', async (role, route) => {
    signedInAs(role)
    renderApp({ route })
    expect(await screen.findByRole('heading', { level: 1, name: FORBIDDEN })).toBeInTheDocument()
    expect(screen.getByText('Error 403')).toBeInTheDocument()
  })

  it.each(['CUSTOMER', 'BRANCH_STAFF', 'MAINTENANCE_TECHNICIAN', 'ADMINISTRATOR', 'BRANCH_MANAGER'] as Role[])(
    '%s can open the profile',
    async (role) => {
      signedInAs(role)
      server.use(
        http.get(`${API}/me/`, () =>
          HttpResponse.json({ id: 1, email: 'x@vrms.test', name: 'X', mobile_no: '+911234567890', address: '', role }),
        ),
      )
      renderApp({ route: '/app/profile' })
      expect(await screen.findByRole('heading', { level: 1, name: 'My profile' })).toBeInTheDocument()
    },
  )

  it('shows each role only its own menu', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    renderApp({ route: '/app' })
    await screen.findByRole('heading', { name: /Welcome/ })
    const menu = screen.getAllByRole('navigation', { name: 'Main' })[0]
    expect(within(menu).getByRole('link', { name: /Maintenance jobs/ })).toBeInTheDocument()
    expect(within(menu).queryByRole('link', { name: /Licence checks/ })).not.toBeInTheDocument()
    expect(within(menu).queryByRole('link', { name: /Fleet/ })).not.toBeInTheDocument()
  })

  it('shows a 404 page for an unknown address', async () => {
    signedInAs('CUSTOMER')
    renderApp({ route: '/app/nowhere' })
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })
})
