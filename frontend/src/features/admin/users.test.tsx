import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { BRANCHES, customer, page, staffAccount } from './fixtures'

describe('staff accounts (Fleet.Users, UC 12 step 1)', () => {
  it('lists the accounts with their role, branch and state', async () => {
    signedInAs('ADMINISTRATOR')
    server.use(
      http.get(`${API}/admin/users/`, () =>
        HttpResponse.json(
          page([
            staffAccount(),
            staffAccount({
              id: 41,
              name: 'Tara Tech',
              role: 'MAINTENANCE_TECHNICIAN',
              branch: null,
              branch_name: null,
              workshop: 'Agency workshop',
              technician_id: 3,
              authorised_to_clear_unsafe: true,
              is_active: false,
            }),
          ]),
        ),
      ),
      http.get(`${API}/admin/customers/`, () => HttpResponse.json(page([]))),
    )
    renderApp({ route: '/app/users' })
    const tara = await screen.findByRole('link', { name: /Tara Tech/ })
    expect(within(tara).getByText('Disabled')).toBeInTheDocument()
    expect(within(tara).getByText('May clear Unsafe (BR-16)')).toBeInTheDocument()
    expect(within(tara).getByText('Agency workshop')).toBeInTheDocument()
    expect(within(screen.getByRole('link', { name: /Neha Kulkarni/ })).getByText('Andheri')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Users/ })[0]).not.toHaveTextContent('Soon')
  })

  it('creates a technician with a workshop instead of a branch', async () => {
    signedInAs('ADMINISTRATOR')
    let sent: unknown
    const created = staffAccount({ id: 42, name: 'Ravi Rao', role: 'MAINTENANCE_TECHNICIAN', branch: null, branch_name: null, workshop: 'Thane workshop', technician_id: 8 })
    server.use(
      http.get(`${API}/fleet/admin/branches/`, () => HttpResponse.json(BRANCHES)),
      http.post(`${API}/admin/users/`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json(created, { status: 201 })
      }),
      http.get(`${API}/admin/users/42/`, () => HttpResponse.json(created)),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/users/new' })

    await user.click(await screen.findByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Choose the role.')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Role'), 'MAINTENANCE_TECHNICIAN')
    expect(screen.queryByLabelText('Branch')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Full name'), 'Ravi Rao')
    await user.type(screen.getByLabelText('E-mail'), 'ravi@vrms.test')
    await user.type(screen.getByLabelText('Mobile number'), '+919812345670')
    await user.type(screen.getByLabelText('Workshop'), 'Thane workshop')
    await user.type(screen.getByLabelText('First password'), 'Str0ng!Passw0rd')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText(/Maintenance Technician account created for Ravi Rao/)).toBeInTheDocument()
    expect(sent).toMatchObject({
      role: 'MAINTENANCE_TECHNICIAN',
      email: 'ravi@vrms.test',
      branch: null,
      workshop: 'Thane workshop',
      password: 'Str0ng!Passw0rd',
    })
  })

  it('disables an account with a reason, and authorises a technician (BR-16)', async () => {
    signedInAs('ADMINISTRATOR')
    const tech = staffAccount({ id: 41, name: 'Tara Tech', role: 'MAINTENANCE_TECHNICIAN', branch: null, branch_name: null, workshop: 'Agency workshop', technician_id: 3 })
    const state = { account: tech }
    const calls: string[] = []
    server.use(
      http.get(`${API}/admin/users/41/`, () => HttpResponse.json(state.account)),
      http.get(`${API}/fleet/admin/branches/`, () => HttpResponse.json(BRANCHES)),
      http.put(`${API}/maintenance/technicians/3/authorisation/`, () => {
        calls.push('authorise')
        state.account = { ...state.account, authorised_to_clear_unsafe: true }
        return HttpResponse.json({})
      }),
      http.post(`${API}/admin/users/41/disable/`, async ({ request }) => {
        calls.push(`disable ${JSON.stringify(await request.json())}`)
        state.account = { ...state.account, is_active: false }
        return HttpResponse.json(state.account)
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/users/41' })

    await user.click(await screen.findByRole('button', { name: 'Authorise to clear Unsafe' }))
    expect(await screen.findByText('Technician authorised to clear Unsafe flags.')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Revoke authorisation' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Disable account' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Reason'), 'Left the agency.')
    await user.click(within(dialog).getByRole('button', { name: 'Disable account' }))
    expect(await screen.findByText('Account disabled; every session has ended.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-enable account' })).toBeInTheDocument()
    expect(calls).toEqual(['authorise', 'disable {"reason":"Left the agency."}'])
  })
})

describe('the blacklist (BR-4, UC 12 step 2 and extension 2a)', () => {
  it('blacklists with a reason, then lists the Confirmed booking to decide on and the rental as return pending', async () => {
    signedInAs('ADMINISTRATOR')
    const state = { customer: customer() }
    let reason: unknown
    server.use(
      http.get(`${API}/admin/customers/9/`, () => HttpResponse.json(state.customer)),
      http.post(`${API}/admin/customers/9/blacklist/`, async ({ request }) => {
        reason = await request.json()
        state.customer = customer({
          is_blacklisted: true,
          blacklist_reason: 'False plates.',
          blacklisted_by: 'Anil Admin',
          blacklisted_at: '2026-10-18T06:00:00Z',
        })
        return HttpResponse.json(state.customer)
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/users/customers/9' })

    const bookings = await screen.findByRole('list', { name: 'Open bookings' })
    expect(within(bookings).queryByRole('button', { name: 'Cancel booking' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Blacklist customer' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Reason'), 'False plates.')
    await user.click(within(dialog).getByRole('button', { name: 'Blacklist customer' }))

    expect(await screen.findByText('Kiran Desai is blacklisted.')).toBeInTheDocument()
    expect(reason).toEqual({ reason: 'False plates.' })
    expect(screen.getByText('False plates.')).toBeInTheDocument()
    const rows = within(screen.getByRole('list', { name: 'Open bookings' })).getAllByRole('listitem')
    expect(within(rows[0]).getByRole('button', { name: 'Cancel booking' })).toBeInTheDocument()
    expect(within(rows[0]).getByRole('link', { name: /View the booking's history for VRMS-20261018-0007/ })).toHaveAttribute(
      'href',
      '/app/audit?entity_type=bookings.Booking&entity_id=70',
    )
    expect(within(rows[1]).getByText('Return pending')).toBeInTheDocument()
    expect(within(rows[1]).queryByRole('button', { name: 'Cancel booking' })).not.toBeInTheDocument()
  })

  it('cancels a Confirmed booking through R2 with the refund shown and the password', async () => {
    signedInAs('ADMINISTRATOR')
    const blacklisted = customer({ is_blacklisted: true, blacklist_reason: 'Fraud' })
    const state = { customer: blacklisted }
    let sent: unknown
    server.use(
      http.get(`${API}/admin/customers/9/`, () => HttpResponse.json(state.customer)),
      http.get(`${API}/admin/customers/9/bookings/70/cancel/`, () =>
        HttpResponse.json({
          notice_hours: 60,
          refund_percent: '100.00',
          rental_amount: '4248.00',
          rental_refund: '4248.00',
          deposit_refund: '5000.00',
          total_refund: '9248.00',
          awaits_approval: true,
        }),
      ),
      http.post(`${API}/admin/customers/9/bookings/70/cancel/`, async ({ request }) => {
        sent = await request.json()
        state.customer = { ...blacklisted, open_bookings: blacklisted.open_bookings.slice(1) }
        return HttpResponse.json({ ...blacklisted.open_bookings[0], status: 'Cancelled' })
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/users/customers/9' })

    await user.click(await screen.findByRole('button', { name: 'Cancel booking' }))
    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByText(/Refund now \(BR-8\)/)).toHaveTextContent('₹9,248.00')
    expect(within(dialog).getByText(/waits for an Administrator’s approval/)).toBeInTheDocument()
    await user.type(within(dialog).getByLabelText('Your password'), 'Demo@1234')
    await user.click(within(dialog).getByRole('button', { name: 'Cancel booking' }))

    expect(await screen.findByText('VRMS-20261018-0007 cancelled. The refund has been started.')).toBeInTheDocument()
    expect(sent).toEqual({ expected_refund: '9248.00', password: 'Demo@1234' })
  })
})
