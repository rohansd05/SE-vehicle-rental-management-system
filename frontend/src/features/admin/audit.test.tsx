import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { AUDIT_ENTRY, customer, page } from './fixtures'

const OPTIONS = {
  actions: ['Cash Payment Recorded', 'Odometer Override Approved', 'Refund Approved'],
  entity_types: ['payments.CashPayment', 'rentals.ConditionReport'],
}

function serveAudit(seen = vi.fn()) {
  server.use(
    http.get(`${API}/audit/filters/`, () => HttpResponse.json(OPTIONS)),
    http.get(`${API}/audit/`, ({ request }) => {
      seen(Object.fromEntries(new URL(request.url).searchParams))
      return HttpResponse.json(page([AUDIT_ENTRY, { ...AUDIT_ENTRY, id: 502, actor: null, action: 'Create' }]))
    }),
  )
  return seen
}

describe('audit log (Fleet.Audit, SE-10)', () => {
  it('shows who did what, when, with the previous and new values; the system too', async () => {
    signedInAs('ADMINISTRATOR')
    serveAudit()
    renderApp({ route: '/app/audit' })
    const entries = await screen.findByRole('list', { name: 'Audit entries' })
    const [first, second] = within(entries).getAllByRole('listitem')
    expect(first).toHaveTextContent('Odometer Override Approved')
    expect(first).toHaveTextContent('rentals.ConditionReport #44')
    expect(first).toHaveTextContent('Meera Manager (Branch Manager, manager@vrms.test)')
    expect(first).toHaveTextContent('"reason": "Outstation trip"')
    expect(second).toHaveTextContent('The system')
    expect(screen.queryByRole('button', { name: /edit|delete/i })).not.toBeInTheDocument() // read-only
    expect(screen.getAllByRole('link', { name: /Audit log/ })[0]).not.toHaveTextContent('Soon')
  })

  it('filters by actor, action, entity and date', async () => {
    signedInAs('ADMINISTRATOR')
    const seen = serveAudit()
    const user = userEvent.setup()
    renderApp({ route: '/app/audit' })
    await screen.findByRole('option', { name: 'Refund Approved' })
    await user.type(screen.getByLabelText('Actor'), 'meera')
    await user.selectOptions(screen.getByLabelText('Action'), 'Odometer Override Approved')
    await user.selectOptions(screen.getByLabelText('Entity'), 'rentals.ConditionReport')
    await user.type(screen.getByLabelText('From'), '2026-10-01')
    await user.type(screen.getByLabelText('To'), '2026-10-18')
    await user.click(screen.getByRole('button', { name: 'Apply filters' }))
    await vi.waitFor(() =>
      expect(seen).toHaveBeenLastCalledWith({
        actor: 'meera',
        action: 'Odometer Override Approved',
        entity_type: 'rentals.ConditionReport',
        date_from: '2026-10-01',
        date_to: '2026-10-18',
      }),
    )
    await user.click(screen.getByRole('button', { name: 'Clear' }))
    await vi.waitFor(() => expect(seen).toHaveBeenLastCalledWith({}))
  })

  it('opens pre-filtered on one booking from the blacklist screen', async () => {
    signedInAs('ADMINISTRATOR')
    const seen = serveAudit()
    server.use(http.get(`${API}/admin/customers/9/`, () => HttpResponse.json(customer())))
    const user = userEvent.setup()
    renderApp({ route: '/app/users/customers/9' })
    await user.click(await screen.findByRole('link', { name: /View the booking's history for VRMS-20261018-0007/ }))
    expect(await screen.findByText(/Showing the history of bookings.Booking/)).toHaveTextContent('#70')
    expect(seen).toHaveBeenCalledWith({ entity_type: 'bookings.Booking', entity_id: '70' })
  })

  it('is open to a Branch Manager, for their own branch', async () => {
    signedInAs('BRANCH_MANAGER')
    serveAudit()
    renderApp({ route: '/app/audit' })
    expect(await screen.findByText(/Every change to your branch’s bookings/)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Audit log/ }).length).toBeGreaterThan(0)
  })

  it('is refused to Branch Staff', async () => {
    signedInAs('BRANCH_STAFF')
    serveAudit()
    renderApp({ route: '/app/audit' })
    expect(await screen.findByText(/don’t have access|do not have access|not allowed/i)).toBeInTheDocument()
  })
})
