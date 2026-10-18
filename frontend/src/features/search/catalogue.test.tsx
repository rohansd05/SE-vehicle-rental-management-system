// Module R4: the guest catalogue (Search.Browse), Search.Filter, the sort,
// Search.Detail's rating and SA-2 state, and UC 2 extension 3a's alternatives,
// through the screens against the API mocked by MSW.

import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { CAR as CAR_DETAIL, PICKUP, QUOTE, RETURN } from '@/features/booking/fixtures'
import { renderAppAt } from '@/features/booking/test-render'
import { API, makeAccessToken, server, signedInAs, USERS } from '@/test/server'

import type { AvailableVehicle, Branch, SearchAlternative, SearchResults, VehicleCategory } from './api'

const BRANCHES: Branch[] = [
  { branch_id: 1, branch_name: 'Andheri', address: 'Andheri (E), Mumbai' },
  { branch_id: 2, branch_name: 'Bandra', address: 'Bandra (W), Mumbai' },
]
const CATEGORIES: VehicleCategory[] = [{ id: 3, name: 'Hatchback', vehicle_type: 'Car' }]

const RESULT: AvailableVehicle = {
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
  rating_count: 3,
  last_service_date: '2026-09-20',
  estimate: { billing_unit: 'day', billing_count: 2, total_payable: '4248.00', security_deposit: '5000.00' },
}

const page = (results: AvailableVehicle[]): SearchResults => ({ count: results.length, next: null, previous: null, results })
const QUERY = new URLSearchParams({ branch: '1', pickup_datetime: PICKUP, return_datetime: RETURN })

/** The catalogue API; returns the query of every search and alternatives request. */
function serveCatalogue(results: AvailableVehicle[] = [RESULT], alternatives: SearchAlternative[] = []) {
  const searches: URLSearchParams[] = []
  const asked: URLSearchParams[] = []
  server.use(
    http.get(`${API}/fleet/branches/`, () => HttpResponse.json(BRANCHES)),
    http.get(`${API}/fleet/categories/`, () => HttpResponse.json(CATEGORIES)),
    http.get(`${API}/fleet/search/`, ({ request }) => {
      searches.push(new URL(request.url).searchParams)
      return HttpResponse.json(page(results))
    }),
    http.get(`${API}/fleet/search/alternatives/`, ({ request }) => {
      asked.push(new URL(request.url).searchParams)
      return HttpResponse.json(alternatives)
    }),
  )
  return { searches, asked }
}

describe('guest catalogue (Search.Browse)', () => {
  it('lets a signed-out visitor search and see the rating with its count', async () => {
    serveCatalogue()
    renderAppAt(`/search?${QUERY}`)
    const results = await screen.findByRole('list', { name: 'Available vehicles' })
    expect(within(results).getByText('(3 ratings)')).toBeInTheDocument()
    expect(within(results).getByRole('link', { name: 'View and book the Maruti Suzuki Swift' })).toHaveAttribute(
      'href',
      `/vehicles/11?${new URLSearchParams({ pickup_datetime: PICKUP, return_datetime: RETURN })}`,
    )
  })

  it('offers sign-in or registration instead of booking, keeping the vehicle and dates', async () => {
    server.use(http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json(CAR_DETAIL)))
    renderAppAt(`/vehicles/11?${new URLSearchParams({ pickup_datetime: PICKUP, return_datetime: RETURN })}`)
    expect(await screen.findByRole('heading', { name: 'Maruti Suzuki Swift (2023)' })).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Book this vehicle' })).not.toBeInTheDocument()
    expect(screen.getByText('(2 ratings)')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Register to book' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in to book' })).toBeInTheDocument()
  })

  it('returns to the same vehicle and dates after signing in, ready to book', async () => {
    const user = userEvent.setup()
    server.use(
      http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json(CAR_DETAIL)),
      http.get(`${API}/pricing/add-ons/`, () => HttpResponse.json([])),
      http.post(`${API}/pricing/quote/`, () => HttpResponse.json(QUOTE)),
      http.post(`${API}/auth/login/`, () => HttpResponse.json({ access: makeAccessToken(), user: USERS.CUSTOMER })),
    )
    renderAppAt(`/vehicles/11?${new URLSearchParams({ pickup_datetime: PICKUP, return_datetime: RETURN })}`)
    await user.click(await screen.findByRole('link', { name: 'Sign in to book' }))
    await user.type(await screen.findByLabelText('E-mail'), 'customer@vrms.test')
    await user.type(screen.getByLabelText('Password'), 'Demo@1234')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    // Back on the vehicle inside the app, with R1's booking form for the same period.
    expect(await screen.findByRole('form', { name: 'Book this vehicle' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Hold this vehicle and pay' })).toBeInTheDocument()
  })

  it('carries the vehicle through registration and the code check to sign-in', { timeout: 20_000 }, async () => {
    const user = userEvent.setup()
    server.use(
      http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json(CAR_DETAIL)),
      http.get(`${API}/pricing/add-ons/`, () => HttpResponse.json([])),
      http.post(`${API}/pricing/quote/`, () => HttpResponse.json(QUOTE)),
      http.post(`${API}/auth/register/`, () =>
        HttpResponse.json({ email: 'asha@example.com', detail: 'Code sent.' }, { status: 201 }),
      ),
      http.post(`${API}/auth/verify-otp/`, () => HttpResponse.json({ detail: 'Your account is verified.' })),
      http.post(`${API}/auth/login/`, () => HttpResponse.json({ access: makeAccessToken(), user: USERS.CUSTOMER })),
    )
    renderAppAt(`/vehicles/11?${new URLSearchParams({ pickup_datetime: PICKUP, return_datetime: RETURN })}`)
    await user.click(await screen.findByRole('link', { name: 'Register to book' }))
    await user.type(await screen.findByLabelText('Full name'), 'Asha Rao')
    await user.type(screen.getByLabelText('E-mail'), 'asha@example.com')
    const [mobile, emergencyMobile] = screen.getAllByLabelText('Mobile number')
    await user.type(mobile, '+919812345678')
    await user.type(screen.getByLabelText('Address'), '14 Hill Road, Mumbai')
    await user.type(screen.getByLabelText('Date of birth'), '1996-04-12')
    await user.type(screen.getByLabelText('Name'), 'Ravi Rao')
    await user.type(emergencyMobile, '+919812300000')
    await user.type(screen.getByLabelText('Password'), 'Str0ng!Passw0rd')
    await user.type(screen.getByLabelText('Confirm password'), 'Str0ng!Passw0rd')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    await user.type(await screen.findByLabelText('Verification code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    await user.type(await screen.findByLabelText('Password'), 'Str0ng!Passw0rd')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('form', { name: 'Book this vehicle' })).toBeInTheDocument()
  })

  it('a customer on the public page goes to the app to book', async () => {
    signedInAs('CUSTOMER')
    server.use(http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json(CAR_DETAIL)))
    renderAppAt(`/vehicles/11?${new URLSearchParams({ pickup_datetime: PICKUP, return_datetime: RETURN })}`)
    expect(await screen.findByRole('link', { name: 'Book this vehicle' })).toHaveAttribute(
      'href',
      `/app/vehicles/11?${new URLSearchParams({ pickup_datetime: PICKUP, return_datetime: RETURN })}`,
    )
  })
})

describe('Search.Filter and the sort', () => {
  it('sends every filter and the sort to the server', async () => {
    const user = userEvent.setup()
    const { searches } = serveCatalogue()
    renderAppAt(`/search?${QUERY}`)
    await screen.findByRole('list', { name: 'Available vehicles' })
    await user.selectOptions(screen.getByLabelText('Vehicle type'), 'Car')
    await user.type(screen.getByLabelText('Brand'), 'Maruti')
    await user.type(screen.getByLabelText('Model'), 'Swift')
    await user.selectOptions(screen.getByLabelText('Fuel'), 'Petrol')
    await user.selectOptions(screen.getByLabelText('Transmission'), 'Manual')
    await user.type(screen.getByLabelText('Seats, at least'), '5')
    await user.type(screen.getByLabelText('Estimated price from'), '1000')
    await user.type(screen.getByLabelText('Estimated price up to'), '5000')
    await user.selectOptions(screen.getByLabelText('Rating, at least'), '4')
    await user.selectOptions(screen.getByLabelText('Sort by'), 'price')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(searches).toHaveLength(2))
    const last = searches.at(-1)!
    expect(Object.fromEntries(last)).toMatchObject({
      vehicle_type: 'Car',
      brand: 'Maruti',
      model: 'Swift',
      fuel_type: 'Petrol',
      transmission: 'Manual',
      min_seats: '5',
      min_price: '1000',
      max_price: '5000',
      min_rating: '4',
      sort: 'price',
    })
  })

  it('shows a highest price below the lowest next to its field', async () => {
    const user = userEvent.setup()
    serveCatalogue()
    renderAppAt(`/search?${QUERY}`)
    await screen.findByRole('list', { name: 'Available vehicles' })
    await user.type(screen.getByLabelText('Estimated price from'), '5000')
    await user.type(screen.getByLabelText('Estimated price up to'), '1000')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('The highest price must not be below the lowest.')).toBeInTheDocument()
    expect(screen.getByLabelText('Estimated price up to')).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('UC 2 extension 3a: nearest alternatives', () => {
  it('offers other branches and nearby dates when nothing matches', async () => {
    const user = userEvent.setup()
    const later = '2027-01-12T04:30:00Z'
    const { asked, searches } = serveCatalogue(
      [],
      [
        { branch: 2, branch_name: 'Bandra', pickup_datetime: PICKUP, return_datetime: RETURN, vehicles: 2 },
        { branch: 1, branch_name: 'Andheri', pickup_datetime: later, return_datetime: '2027-01-14T04:30:00Z', vehicles: 1 },
      ],
    )
    renderAppAt(`/search?${QUERY}&brand=Maruti`)
    expect(await screen.findByText('No vehicles are free for these dates')).toBeInTheDocument()
    const list = await screen.findByRole('heading', { name: 'Nearest alternatives' })
    const links = within(list.parentElement!).getAllByRole('link')
    expect(links[0]).toHaveTextContent('Bandra, same dates')
    expect(links[0]).toHaveTextContent('2 vehicles free')
    expect(links[1]).toHaveTextContent('1 vehicle free')
    expect(asked[0].get('brand')).toBe('Maruti') // the same filters
    await user.click(links[0])
    await screen.findByText('No vehicles are free for these dates')
    expect(searches.at(-1)!.get('branch')).toBe('2')
  })
})

describe('Search.Detail and SA-2', () => {
  it('marks a vehicle overdue for its service as not bookable', async () => {
    signedInAs('CUSTOMER')
    server.use(
      http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json({ ...CAR_DETAIL, service_overdue: true })),
    )
    renderAppAt(`/app/vehicles/11?${new URLSearchParams({ pickup_datetime: PICKUP, return_datetime: RETURN })}`)
    expect(await screen.findByText('Not bookable: service overdue')).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Book this vehicle' })).not.toBeInTheDocument()
  })

  it('shows the free distance and the excess-km rate', async () => {
    server.use(http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json(CAR_DETAIL)))
    renderAppAt('/vehicles/11')
    expect(await screen.findByText('250 km per day, then ₹12.00 per km')).toBeInTheDocument()
  })
})
