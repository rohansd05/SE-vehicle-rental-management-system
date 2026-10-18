import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import type { AvailableVehicle, Branch, SearchResults, VehicleCategory } from './api'

const BRANCHES: Branch[] = [
  { branch_id: 1, branch_name: 'Andheri', address: 'Andheri (E), Mumbai' },
  { branch_id: 2, branch_name: 'Bandra', address: 'Bandra (W), Mumbai' },
]

const CATEGORIES: VehicleCategory[] = [
  { id: 3, name: 'Hatchback', vehicle_type: 'Car' },
  { id: 4, name: 'Scooter', vehicle_type: 'Two-Wheeler' },
]

const CAR: AvailableVehicle = {
  id: 11,
  brand: 'Maruti Suzuki',
  model: 'Swift',
  year: 2023,
  colour: 'White',
  fuel_type: 'Petrol',
  vehicle_type: 'Car',
  category: 'Hatchback',
  category_id: 3,
  home_branch: 'Andheri',
  home_branch_id: 1,
  transmission: 'Manual',
  seating_capacity: 5,
  engine_cc: null,
  average_rating: '4.50',
  rating_count: 2,
  last_service_date: '2026-09-20',
  estimate: { billing_unit: 'day', billing_count: 2, total_payable: '4248.00', security_deposit: '5000.00' },
}

const SCOOTER: AvailableVehicle = {
  ...CAR,
  id: 12,
  brand: 'Honda',
  model: 'Activa 6G',
  colour: 'Grey',
  vehicle_type: 'Two-Wheeler',
  category: 'Scooter',
  category_id: 4,
  transmission: null,
  seating_capacity: null,
  engine_cc: 110,
  average_rating: null,
  last_service_date: null,
  estimate: null,
}

// Local wall-clock times, as typed into datetime-local inputs.
const PICKUP = '2027-01-10T10:00'
const RETURN = '2027-01-12T10:00'

const page = (results: AvailableVehicle[], extra: Partial<SearchResults> = {}): SearchResults => ({
  count: results.length,
  next: null,
  previous: null,
  results,
  ...extra,
})

/** A signed-in customer on the search page; returns every search request's query. */
function customerOnSearch(respond: (url: URL) => Response | Promise<Response> = () => HttpResponse.json(page([CAR, SCOOTER]))) {
  const requests: URLSearchParams[] = []
  signedInAs('CUSTOMER')
  server.use(
    http.get(`${API}/fleet/branches/`, () => HttpResponse.json(BRANCHES)),
    http.get(`${API}/fleet/categories/`, () => HttpResponse.json(CATEGORIES)),
    http.get(`${API}/fleet/search/`, ({ request }) => {
      const url = new URL(request.url)
      requests.push(url.searchParams)
      return respond(url)
    }),
  )
  renderApp({ route: '/app/search' })
  return requests
}

async function fillAndSearch(
  user: ReturnType<typeof userEvent.setup>,
  { branch = 'Andheri', pickup = PICKUP, ret = RETURN }: { branch?: string; pickup?: string; ret?: string } = {},
) {
  if (branch) await user.selectOptions(await screen.findByLabelText('Pickup branch'), branch)
  const pickupInput = await screen.findByLabelText('Pickup')
  await user.clear(pickupInput)
  if (pickup) await user.type(pickupInput, pickup)
  const returnInput = screen.getByLabelText('Return')
  await user.clear(returnInput)
  if (ret) await user.type(returnInput, ret)
  await user.click(screen.getByRole('button', { name: 'Search' }))
}

describe('vehicle search (Search.Available)', () => {
  it('lists the branches and categories to search by', async () => {
    customerOnSearch()
    const branch = await screen.findByLabelText('Pickup branch')
    expect(within(branch).getAllByRole('option').map((option) => option.textContent)).toEqual([
      'Choose a branch',
      'Andheri',
      'Bandra',
    ])
    expect(
      within(screen.getByLabelText('Vehicle category'))
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Any category', 'Hatchback (Car)', 'Scooter (Two-Wheeler)'])
  })

  it('sends the branch and the period in UTC, then lists the free vehicles', async () => {
    const requests = customerOnSearch()
    const user = userEvent.setup()
    await fillAndSearch(user)

    const list = await screen.findByRole('list', { name: 'Available vehicles' })
    expect(requests).toHaveLength(1)
    expect(requests[0].get('branch')).toBe('1')
    expect(requests[0].get('pickup_datetime')).toBe(new Date(PICKUP).toISOString())
    expect(requests[0].get('return_datetime')).toBe(new Date(RETURN).toISOString())
    expect(requests[0].has('category')).toBe(false)

    expect(screen.getByText(/2 vehicles are free at Andheri from/)).toBeInTheDocument()
    const [car, scooter] = within(list).getAllByRole('listitem')
    expect(within(car).getByRole('heading', { name: 'Maruti Suzuki Swift (2023)' })).toBeInTheDocument()
    expect(within(car).getByText('Petrol · White · Manual · 5 seats')).toBeInTheDocument()
    expect(within(car).getByText('4.5 out of 5')).toBeInTheDocument()
    expect(within(car).getByText('Hatchback')).toBeInTheDocument()
    expect(within(scooter).getByText('Petrol · Grey · 110 cc')).toBeInTheDocument()
    expect(within(scooter).getByText('No ratings yet')).toBeInTheDocument()
    expect(within(scooter).getByText('Not recorded')).toBeInTheDocument()
  })

  it('marks each price as an estimate and shows the deposit apart (Search.Price)', async () => {
    customerOnSearch()
    const user = userEvent.setup()
    await fillAndSearch(user)
    const [car, scooter] = within(await screen.findByRole('list', { name: 'Available vehicles' })).getAllByRole(
      'listitem',
    )
    expect(within(car).getByText('Estimated price').closest('p')).toHaveTextContent(
      'Estimated price ₹4,248.00 for 2 days',
    )
    expect(within(car).getByText(/usage-based charges are not included/)).toBeInTheDocument()
    expect(within(car).getByText(/Refundable security deposit ₹5,000.00/)).toBeInTheDocument()
    expect(within(scooter).getByText('No price is published for this category yet.')).toBeInTheDocument()
  })

  it('sends the category when one is chosen', async () => {
    const requests = customerOnSearch(() => HttpResponse.json(page([SCOOTER])))
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText('Vehicle category'), 'Scooter (Two-Wheeler)')
    await fillAndSearch(user)
    expect(await screen.findByText(/1 vehicle is free/)).toBeInTheDocument()
    expect(requests[0].get('category')).toBe('4')
  })

  it.each([
    ['the return is before the pickup', '2027-01-10T09:00', 'The return must be after the pickup.'],
    ['the rental is under 4 hours', '2027-01-10T13:59', 'A rental lasts at least 4 hours (BR-5).'],
    ['the rental is over 30 days', '2027-02-09T10:01', 'A rental lasts at most 30 days (BR-5).'],
  ])('refuses to search when %s (BR-5)', async (_case, ret, message) => {
    const requests = customerOnSearch()
    const user = userEvent.setup()
    await fillAndSearch(user, { ret })
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.getByLabelText('Return')).toHaveAttribute('aria-invalid', 'true')
    expect(requests).toHaveLength(0)
  })

  it('requires a branch and a pickup in the future', async () => {
    const requests = customerOnSearch()
    const user = userEvent.setup()
    await fillAndSearch(user, { branch: '', pickup: '2020-01-10T10:00', ret: '2020-01-12T10:00' })
    expect(await screen.findByText('Choose a pickup branch.')).toBeInTheDocument()
    expect(await screen.findByText('Choose a pickup time in the future.')).toBeInTheDocument()
    expect(requests).toHaveLength(0)
  })

  it('says so when no vehicle is free', async () => {
    customerOnSearch(() => HttpResponse.json(page([])))
    const user = userEvent.setup()
    await fillAndSearch(user)
    expect(await screen.findByText('No vehicles are free for these dates')).toBeInTheDocument()
    expect(screen.getByText(/0 vehicles are free at Andheri/)).toBeInTheDocument()
  })

  it('shows progress, then an error with a retry that works', async () => {
    let calls = 0
    customerOnSearch(async () => {
      calls += 1
      await delay(50)
      return calls === 1
        ? HttpResponse.json({ detail: 'Server error.' }, { status: 500 })
        : HttpResponse.json(page([CAR]))
    })
    const user = userEvent.setup()
    await fillAndSearch(user)
    expect(await screen.findByText('Finding available vehicles…')).toBeInTheDocument()
    expect(await screen.findByText('We couldn’t search right now')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'Maruti Suzuki Swift (2023)' })).toBeInTheDocument()
  })

  it('puts the server’s rule message next to its field', async () => {
    customerOnSearch(() =>
      HttpResponse.json({ pickup_datetime: ['Choose a pickup time in the future.'] }, { status: 400 }),
    )
    const user = userEvent.setup()
    await fillAndSearch(user)
    expect(await screen.findByText('Choose a pickup time in the future.')).toBeInTheDocument()
    expect(screen.getByLabelText('Pickup')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByRole('list', { name: 'Available vehicles' })).not.toBeInTheDocument()
  })

  it('shows a refusal that names no field above the form', async () => {
    customerOnSearch(() => HttpResponse.json({ detail: 'Search is unavailable.' }, { status: 400 }))
    const user = userEvent.setup()
    await fillAndSearch(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('Search is unavailable.')
  })

  it('pages through a long result list', async () => {
    const requests = customerOnSearch((url) =>
      url.searchParams.get('page') === '2'
        ? HttpResponse.json(page([SCOOTER], { count: 21, previous: 'p1' }))
        : HttpResponse.json(page([CAR], { count: 21, next: 'p2' })),
    )
    const user = userEvent.setup()
    await fillAndSearch(user)
    expect(await screen.findByRole('heading', { name: 'Maruti Suzuki Swift (2023)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    expect(await screen.findByRole('heading', { name: 'Honda Activa 6G (2023)' })).toBeInTheDocument()
    expect(requests.at(-1)?.get('page')).toBe('2')
    expect(requests.at(-1)?.get('branch')).toBe('1')
  })

  it('explains when the form cannot load', async () => {
    signedInAs('CUSTOMER')
    const branches = vi.fn(() => HttpResponse.json({ detail: 'Down.' }, { status: 503 }))
    server.use(
      http.get(`${API}/fleet/branches/`, branches),
      http.get(`${API}/fleet/categories/`, () => HttpResponse.json(CATEGORIES)),
    )
    renderApp({ route: '/app/search' })
    expect(await screen.findByText('We couldn’t load the search form')).toBeInTheDocument()
    expect(branches).toHaveBeenCalled()
  })

  it('is the customer’s menu entry, no longer marked Soon', async () => {
    customerOnSearch()
    expect(await screen.findByLabelText('Pickup branch')).toBeInTheDocument()
    const link = screen.getAllByRole('link', { name: /Find a vehicle/ })[0]
    expect(link).not.toHaveTextContent('Soon')
  })
})
