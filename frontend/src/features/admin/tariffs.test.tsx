import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { CATEGORIES, TARIFFS } from './fixtures'

const ADD_ONS = [{ id: 3, name: 'Child seat', daily_rate: '150.00', vehicle_type: 'Car', is_active: true }]
const CODES = [
  {
    id: 4,
    code: 'WELCOME10',
    discount_type: 'Percent',
    value: '10.00',
    valid_from: '2026-01-01T00:00:00Z',
    valid_to: '2026-12-31T18:29:00Z',
    is_active: true,
    usage_limit: null,
    times_used: 2,
  },
]

function servePricing() {
  signedInAs('ADMINISTRATOR')
  server.use(
    http.get(`${API}/pricing/admin/tariffs/`, () => HttpResponse.json(TARIFFS)),
    http.get(`${API}/pricing/admin/add-ons/`, () => HttpResponse.json(ADD_ONS)),
    http.get(`${API}/pricing/admin/discount-codes/`, () => HttpResponse.json(CODES)),
    http.get(`${API}/fleet/categories/`, () => HttpResponse.json(CATEGORIES)),
  )
}

describe('tariffs (Fleet.Tariff, BR-13, UC 11 step 2)', () => {
  it('shows the history with which tariff is in force and how many bookings keep each', async () => {
    servePricing()
    renderApp({ route: '/app/tariffs' })
    const table = await screen.findByRole('table', { name: 'Tariff history' })
    const rows = within(table).getAllByRole('row')
    expect(rows[1]).toHaveTextContent('Scheduled')
    expect(rows[2]).toHaveTextContent('In force')
    expect(rows[2]).toHaveTextContent('3 bookings priced at it')
    expect(within(rows[1]).getByRole('button', { name: 'Withdraw the Hatchback tariff' })).toBeInTheDocument()
    expect(within(rows[2]).queryByRole('button')).not.toBeInTheDocument() // history is never withdrawn
    const nav = screen.getAllByRole('link', { name: /Tariffs/ })[0]
    expect(nav).not.toHaveTextContent('Soon')
  })

  it('defines a tariff that starts now when no date is given', async () => {
    servePricing()
    let sent: unknown
    server.use(
      http.post(`${API}/pricing/admin/tariffs/`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({ ...TARIFFS[1], id: 9, daily_rate: '2100.00' }, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/tariffs' })
    await user.click(await screen.findByRole('button', { name: 'Define tariff' }))
    expect(await screen.findByText('Choose the category.')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Vehicle category'), '1')
    await user.type(screen.getByLabelText('Hourly rate (₹)'), '175')
    await user.type(screen.getByLabelText('Daily rate (₹)'), '2100')
    await user.type(screen.getByLabelText('Weekly rate (₹)'), '12500')
    await user.type(screen.getByLabelText('Free kilometres per day'), '250')
    await user.type(screen.getByLabelText('Excess-kilometre rate (₹ per km)'), '11.50')
    await user.click(screen.getByRole('button', { name: 'Define tariff' }))

    expect(await screen.findByText(/Hatchback tariff in force now\. Confirmed bookings keep the tariff/)).toBeInTheDocument()
    expect(sent).toEqual({
      vehicle_category: 1,
      hourly_rate: '175',
      daily_rate: '2100',
      weekly_rate: '12500',
      free_km_allowance: 250,
      excess_km_rate: '11.50',
      effective_from: null,
    })
  })

  it('shows the server’s refusal of a past effective date next to the field', async () => {
    servePricing()
    server.use(
      http.post(`${API}/pricing/admin/tariffs/`, () =>
        HttpResponse.json(
          { effective_from: ['The effective date cannot be in the past; leave it empty to start now.'] },
          { status: 400 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/tariffs' })
    await screen.findByRole('option', { name: 'Hatchback (Car)' })
    await user.selectOptions(screen.getByLabelText('Vehicle category'), '1')
    for (const label of ['Hourly rate (₹)', 'Daily rate (₹)', 'Weekly rate (₹)', 'Free kilometres per day', 'Excess-kilometre rate (₹ per km)']) {
      await user.type(screen.getByLabelText(label), '1')
    }
    await user.type(screen.getByLabelText('Effective from'), '2026-01-01T10:00')
    await user.click(screen.getByRole('button', { name: 'Define tariff' }))
    expect(
      await screen.findByText('The effective date cannot be in the past; leave it empty to start now.'),
    ).toBeInTheDocument()
  })

  it('stops offering an add-on and switches a discount code off', async () => {
    servePricing()
    const patched: Array<{ url: string; body: unknown }> = []
    server.use(
      http.patch(`${API}/pricing/admin/:kind/:id/`, async ({ request }) => {
        patched.push({ url: new URL(request.url).pathname, body: await request.json() })
        return HttpResponse.json({})
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/tariffs' })
    await user.click(await screen.findByRole('button', { name: 'Stop offering Child seat' }))
    expect(await screen.findByText('Child seat withdrawn.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Switch off WELCOME10' }))
    expect(await screen.findByText('WELCOME10 switched off.')).toBeInTheDocument()
    expect(patched).toEqual([
      { url: '/api/v1/pricing/admin/add-ons/3/', body: { is_active: false } },
      { url: '/api/v1/pricing/admin/discount-codes/4/', body: { is_active: false } },
    ])
  })
})
