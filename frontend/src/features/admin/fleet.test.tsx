import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { BRANCHES, CATEGORIES, page, VEHICLE, VEHICLE_DETAIL } from './fixtures'

const jpg = (name: string) => new File(['jpeg'], name, { type: 'image/jpeg' })

describe('fleet (Fleet.Status, UC 11)', () => {
  it('lists every vehicle with its status and document alerts, and filters by status', async () => {
    signedInAs('ADMINISTRATOR')
    const seen = vi.fn()
    server.use(
      http.get(`${API}/fleet/admin/vehicles/`, ({ request }) => {
        seen(new URL(request.url).searchParams.get('status'))
        return HttpResponse.json(page([VEHICLE]))
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/fleet' })

    const row = await screen.findByRole('link', { name: /MH02DM1001 · Maruti Suzuki Swift/ })
    expect(within(row).getByText('Available')).toBeInTheDocument()
    expect(within(row).getByText('Road Tax not on record')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Status'), 'Unsafe')
    expect(seen).toHaveBeenLastCalledWith('Unsafe')
    const nav = screen.getAllByRole('link', { name: /Fleet/ })[0]
    expect(nav).not.toHaveTextContent('Soon')
  })

  it('adds a vehicle with its photos and the expiry of each statutory document', async () => {
    signedInAs('ADMINISTRATOR')
    let received: FormData | undefined
    server.use(
      http.get(`${API}/fleet/categories/`, () => HttpResponse.json(CATEGORIES)),
      http.get(`${API}/fleet/admin/branches/`, () => HttpResponse.json(BRANCHES)),
      http.post(`${API}/fleet/admin/vehicles/`, async ({ request }) => {
        received = await request.formData()
        return HttpResponse.json(VEHICLE_DETAIL, { status: 201 })
      }),
      http.get(`${API}/fleet/admin/vehicles/12/`, () => HttpResponse.json(VEHICLE_DETAIL)),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/fleet/new' })

    await user.click(await screen.findByRole('button', { name: 'Add vehicle' }))
    expect(await screen.findByText('Enter the registration number.')).toBeInTheDocument()
    expect(screen.getByText('Enter the insurance expiry date.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Registration number'), 'MH02ZZ9001')
    await user.type(screen.getByLabelText('Chassis number'), 'CHASSIS99')
    await user.selectOptions(screen.getByLabelText('Category'), '1')
    await user.type(screen.getByLabelText('Brand'), 'Tata')
    await user.type(screen.getByLabelText('Model'), 'Altroz')
    await user.type(screen.getByLabelText('Year'), '2025')
    await user.type(screen.getByLabelText('Colour'), 'Gold')
    await user.selectOptions(screen.getByLabelText('Fuel type'), 'Electric')
    await user.type(screen.getByLabelText('Battery capacity (kWh)'), '30')
    await user.selectOptions(screen.getByLabelText('Home branch'), '1')
    await user.type(screen.getByLabelText('Odometer (km)'), '120')
    for (const type of ['Insurance', 'Pollution Certificate', 'Fitness Certificate', 'Road Tax']) {
      await user.type(screen.getByLabelText(`${type} expires on`), '2027-12-31')
    }
    await user.upload(screen.getByLabelText('Photographs'), [jpg('a.jpg'), jpg('b.jpg'), jpg('c.jpg')])
    await user.click(screen.getByRole('button', { name: 'Add vehicle' }))
    expect(await screen.findByText('Add at least 4 photographs.')).toBeInTheDocument()

    await user.upload(screen.getByLabelText('Photographs'), [jpg('a.jpg'), jpg('b.jpg'), jpg('c.jpg'), jpg('d.jpg')])
    await user.click(screen.getByRole('button', { name: 'Add vehicle' }))

    expect(await screen.findByText('MH02DM1001 added to the fleet.')).toBeInTheDocument()
    expect(received?.get('registration_no')).toBe('MH02ZZ9001')
    expect(received?.get('fuel_capacity')).toBe('30')
    expect(received?.getAll('photos')).toHaveLength(4)
    expect(received?.get('engine_cc')).toBeNull() // a car sends its transmission and seats
    expect(received?.get('transmission')).toBe('Manual')
    expect(JSON.parse(String(received?.get('documents')))).toEqual([
      { document_type: 'Insurance', expiry_date: '2027-12-31' },
      { document_type: 'Pollution Certificate', expiry_date: '2027-12-31' },
      { document_type: 'Fitness Certificate', expiry_date: '2027-12-31' },
      { document_type: 'Road Tax', expiry_date: '2027-12-31' },
    ])
  })

  it('shows the server’s refusal of a registration already on record next to the field', async () => {
    signedInAs('ADMINISTRATOR')
    server.use(
      http.get(`${API}/fleet/categories/`, () => HttpResponse.json(CATEGORIES)),
      http.get(`${API}/fleet/admin/branches/`, () => HttpResponse.json(BRANCHES)),
      http.post(`${API}/fleet/admin/vehicles/`, () =>
        HttpResponse.json({ registration_no: ['A vehicle with this registration number already exists.'] }, { status: 400 }),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/fleet/new' })
    await user.type(await screen.findByLabelText('Registration number'), 'MH02DM1001')
    await user.type(screen.getByLabelText('Chassis number'), 'X1')
    await user.selectOptions(screen.getByLabelText('Category'), '2')
    expect(screen.getByLabelText('Engine capacity (cc)')).toBeInTheDocument() // a two-wheeler
    await user.type(screen.getByLabelText('Engine capacity (cc)'), '110')
    for (const [label, value] of [['Brand', 'Honda'], ['Model', 'Activa'], ['Year', '2025'], ['Colour', 'Grey'], ['Odometer (km)', '10']]) {
      await user.type(screen.getByLabelText(label), value)
    }
    await user.selectOptions(screen.getByLabelText('Fuel type'), 'Petrol')
    await user.type(screen.getByLabelText('Tank capacity (litres)'), '5.3')
    await user.selectOptions(screen.getByLabelText('Home branch'), '1')
    for (const type of ['Insurance', 'Pollution Certificate', 'Fitness Certificate', 'Road Tax']) {
      await user.type(screen.getByLabelText(`${type} expires on`), '2027-12-31')
    }
    await user.upload(screen.getByLabelText('Photographs'), [1, 2, 3, 4].map((n) => jpg(`${n}.jpg`)))
    await user.click(screen.getByRole('button', { name: 'Add vehicle' }))
    expect(await screen.findByText('A vehicle with this registration number already exists.')).toBeInTheDocument()
  })
})

describe('one vehicle (UC 11: edit, documents, photos, Fleet.Retire)', () => {
  function serveVehicle() {
    signedInAs('ADMINISTRATOR')
    server.use(
      http.get(`${API}/fleet/admin/vehicles/12/`, () => HttpResponse.json(VEHICLE_DETAIL)),
      http.get(`${API}/fleet/admin/branches/`, () => HttpResponse.json(BRANCHES)),
    )
  }

  it('sends only the fields that changed', async () => {
    serveVehicle()
    let sent: unknown
    server.use(
      http.patch(`${API}/fleet/admin/vehicles/12/`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({ ...VEHICLE_DETAIL, colour: 'Blue' })
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/fleet/12' })
    const colour = await screen.findByLabelText('Colour')
    await user.clear(colour)
    await user.type(colour, 'Blue')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Vehicle details saved.')).toBeInTheDocument()
    expect(sent).toEqual({ colour: 'Blue' })
  })

  it('states why a vehicle with a future booking cannot be retired', async () => {
    serveVehicle()
    let reason: unknown
    server.use(
      http.post(`${API}/fleet/admin/vehicles/12/retire/`, async ({ request }) => {
        reason = await request.json()
        return HttpResponse.json(
          { detail: 'This vehicle has bookings that are not over; cancel or reassign them first.' },
          { status: 409 },
        )
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/fleet/12' })
    await user.click(await screen.findByRole('button', { name: 'Retire vehicle' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Retire vehicle' }))
    expect(await within(dialog).findByText('Give the reason.')).toBeInTheDocument()
    await user.type(within(dialog).getByLabelText('Reason'), 'Old')
    await user.click(within(dialog).getByRole('button', { name: 'Retire vehicle' }))
    expect(await within(dialog).findByText(/bookings that are not over/)).toBeInTheDocument()
    expect(reason).toEqual({ reason: 'Old' })
  })

  it('records a document renewal and refuses to drop below four photographs', async () => {
    serveVehicle()
    let documentForm: FormData | undefined
    server.use(
      http.post(`${API}/fleet/admin/vehicles/12/documents/`, async ({ request }) => {
        documentForm = await request.formData()
        return HttpResponse.json({}, { status: 201 })
      }),
      http.delete(`${API}/fleet/admin/vehicles/12/photos/1/`, () =>
        HttpResponse.json({ detail: ['A vehicle keeps at least 4 photographs; add another before removing this one.'] }, { status: 400 }),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/fleet/12' })
    expect(await screen.findByText('Handover is refused until these are valid (SA-3)')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Document'), 'Road Tax')
    await user.type(screen.getByLabelText('Expires on'), '2027-03-31')
    await user.click(screen.getByRole('button', { name: 'Record document' }))
    expect(await screen.findByText('Road Tax recorded.')).toBeInTheDocument()
    expect(documentForm?.get('document_type')).toBe('Road Tax')
    expect(documentForm?.get('expiry_date')).toBe('2027-03-31')

    await user.click(screen.getByRole("button", { name: "Remove photograph 1" }))
    expect(await screen.findByText(/keeps at least 4 photographs/)).toBeInTheDocument()
  })
})

describe('branches and serviceable areas', () => {
  it('adds a serviceable area to a branch', async () => {
    signedInAs('ADMINISTRATOR')
    let area: unknown
    server.use(
      http.get(`${API}/fleet/admin/branches/`, () => HttpResponse.json(BRANCHES)),
      http.post(`${API}/fleet/admin/branches/1/areas/`, async ({ request }) => {
        area = await request.json()
        return HttpResponse.json({ id: 6, pincode: '400058', locality: 'Andheri West' }, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/fleet/branches' })
    expect(await screen.findByRole('heading', { name: 'Andheri' })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Serviceable areas of Andheri' })).toHaveTextContent('400053')
    await user.type(screen.getByLabelText('Pincode'), '400058')
    await user.type(screen.getByLabelText('Locality'), 'Andheri West')
    await user.click(screen.getByRole('button', { name: 'Add area' }))
    expect(await screen.findByText('Area 400058 added to Andheri.')).toBeInTheDocument()
    expect(area).toEqual({ pincode: '400058', locality: 'Andheri West' })
  })
})
