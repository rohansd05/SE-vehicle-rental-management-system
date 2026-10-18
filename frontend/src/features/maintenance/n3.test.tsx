// Module N3 on the maintenance screens: the odometer field, the workshop invoice
// (Maint.Record), BR-16's authorised technician, Maint.History, the cancellation
// record, BR-15's automatic Preventive job and the overdue warning (SA-2).

import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { MaintenanceJob } from '@/api/maintenance'
import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { makeJob, page, RECORDED, VEHICLE } from './fixtures'

const JOB = `${API}/maintenance/jobs/7`

function serve(initial: MaintenanceJob) {
  const state = { job: initial }
  server.use(http.get(`${JOB}/`, () => HttpResponse.json(state.job)))
  return state
}

describe('record the work (Maint.Record)', () => {
  it('starts the odometer empty, so typing never appends to the last reading', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    serve(makeJob({ status: 'In Progress', started_at: '2026-10-14T05:00:00Z' }))
    const user = userEvent.setup()
    renderApp({ route: '/app/jobs/7' })
    const odometer = await screen.findByLabelText('Odometer at service (km)')
    expect(odometer).toHaveValue('')
    expect(screen.getByText('The vehicle last read 15000 km; the reading cannot be lower.')).toBeInTheDocument()
    await user.type(odometer, '15230')
    expect(odometer).toHaveValue('15230')
  })

  it('attaches the workshop invoice and links to it', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    const state = serve(makeJob({ ...RECORDED }))
    let received: FormData | undefined
    server.use(
      http.put(`${JOB}/invoice/`, async ({ request }) => {
        received = await request.formData()
        state.job = makeJob({ ...RECORDED, workshop_invoice_url: '/api/v1/files/invoice-token/' })
        return HttpResponse.json(state.job)
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/jobs/7' })
    await user.click(await screen.findByRole('button', { name: 'Attach invoice' }))
    expect(await screen.findByText('Choose the invoice file.')).toBeInTheDocument()
    await user.upload(screen.getByLabelText('Workshop invoice'), new File(['%PDF-1.4'], 'bill.pdf', { type: 'application/pdf' }))
    await user.click(screen.getByRole('button', { name: 'Attach invoice' }))

    expect(await screen.findByText('An invoice is attached.')).toBeInTheDocument()
    expect(received?.get('workshop_invoice')).toMatchObject({ type: 'application/pdf', size: 8 }) // the file was sent
    const links = screen.getAllByRole('link', { name: 'Open the invoice' })
    expect(links[0]).toHaveAttribute('href', '/api/v1/files/invoice-token/')
  })
})

describe('BR-16: an authorised technician clears Unsafe while closing the job', () => {
  it('offers the clearance only to an authorised technician, and sends it', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    const unsafe = { ...VEHICLE, status: 'Unsafe' as const }
    const state = serve(makeJob({ ...RECORDED, vehicle: unsafe, can_clear_unsafe: true }))
    let sent: unknown
    server.use(
      http.post(`${JOB}/complete/`, async ({ request }) => {
        sent = await request.json()
        state.job = makeJob({
          ...RECORDED,
          status: 'Completed',
          closed_by: 'Tara Tech',
          closed_at: '2026-10-14T14:00:00Z',
          vehicle: { ...VEHICLE, status: 'Available' },
        })
        return HttpResponse.json(state.job)
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/jobs/7' })
    await user.click(await screen.findByLabelText('Clear the Unsafe flag as I close the job'))
    await user.click(screen.getByRole('button', { name: 'Complete job' }))

    expect(await screen.findByText(/Unsafe flag cleared and job completed\. MH01AB1234 is Available; you are recorded \(BR-16\)\./)).toBeInTheDocument()
    expect(sent).toEqual({ clear_unsafe: true })
  })

  it('an unauthorised technician sees no such option and asks an Administrator', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    serve(makeJob({ ...RECORDED, vehicle: { ...VEHICLE, status: 'Unsafe' } }))
    let sent: unknown
    server.use(
      http.post(`${JOB}/complete/`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json(makeJob({ ...RECORDED, awaiting_clearance: true, vehicle: { ...VEHICLE, status: 'Unsafe' } }))
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/jobs/7' })
    await user.click(await screen.findByRole('button', { name: 'Complete job' }))
    expect(await screen.findByText(/an Administrator must clear it before the job closes/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Clear the Unsafe flag as I close the job')).not.toBeInTheDocument()
    expect(sent).toEqual({ clear_unsafe: false })
  })
})

describe('the job page (N3 details)', () => {
  it('shows a Preventive job the system raised with its BR-15 due point and the overdue warning', async () => {
    signedInAs('BRANCH_STAFF')
    serve(
      makeJob({
        status: 'Reported',
        technician: null,
        job_type: 'Preventive',
        reported_by: null,
        due_odometer: 25100,
        due_date: '2027-04-01',
        reported_problem: 'Preventive service due (BR-15) at 25,100 km or 01 Apr 2027, whichever comes first.',
        vehicle: { ...VEHICLE, status: 'Available', service_overdue: true },
      }),
    )
    server.use(http.get(`${API}/maintenance/technicians/`, () => HttpResponse.json([])))
    renderApp({ route: '/app/maintenance/7' })
    expect(await screen.findByText('Preventive service overdue')).toBeInTheDocument()
    expect(screen.getByText(/Raised by the system \(BR-15\)/)).toBeInTheDocument()
    expect(screen.getByText('Service due (BR-15)').nextElementSibling).toHaveTextContent('25,100 km, whichever comes first')
  })

  it('shows who cancelled a job, when and why', async () => {
    signedInAs('BRANCH_STAFF')
    serve(
      makeJob({
        status: 'Cancelled',
        cancelled_by: 'Ravi Staff',
        cancelled_at: '2026-10-13T06:00:00Z',
        cancel_reason: 'Duplicate of job 41.',
      }),
    )
    renderApp({ route: '/app/maintenance/7' })
    expect(await screen.findByText('Cancelled by')).toBeInTheDocument()
    expect(screen.getByText('Cancelled by').nextElementSibling).toHaveTextContent('Ravi Staff')
    expect(screen.getByText('Reason for cancelling').nextElementSibling).toHaveTextContent('Duplicate of job 41.')
  })
})

describe('Maint.History', () => {
  it('lists every job on the vehicle with its date, type, odometer, work, parts, cost and downtime', async () => {
    signedInAs('BRANCH_STAFF')
    serve(makeJob({ status: 'Scheduled' }))
    server.use(
      http.get(`${API}/maintenance/vehicles/12/history/`, () =>
        HttpResponse.json(
          page([
            makeJob({ ...RECORDED, status: 'Completed', job_id: 9 }),
            makeJob({ job_id: 4, job_type: 'Inspection', status: 'Cancelled' }),
          ]),
        ),
      ),
      http.get(`${API}/maintenance/technicians/`, () => HttpResponse.json([])),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/maintenance/7' })
    await user.click(await screen.findByRole('link', { name: 'Maintenance history of MH01AB1234' }))

    expect(await screen.findByRole('heading', { name: 'Maintenance history · MH01AB1234' })).toBeInTheDocument()
    const recorded = screen.getByRole('link', { name: /Job 9 · Corrective/ })
    expect(recorded).toHaveTextContent('Replaced front brake pads.')
    expect(recorded).toHaveTextContent('Parts: Brake pads × 1')
    expect(recorded).toHaveTextContent('₹2,250.00')
    expect(recorded).toHaveTextContent('Downtime 6.50 hours')
    expect(recorded).toHaveTextContent('15,100 km')
    expect(within(screen.getByRole('link', { name: /Job 4 · Inspection/ })).getByText('Cancelled')).toBeInTheDocument()
  })
})
