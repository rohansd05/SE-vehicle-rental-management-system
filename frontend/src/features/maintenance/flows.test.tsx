// Exp 4 sequence diagram 3 through the screens, against the API mocked by MSW:
// a technician completes a job, "record work first" is shown, and an
// Administrator approves an Unsafe clearance (BR-16).

import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { MaintenanceJob, RecordWorkRequest } from '@/api/maintenance'
import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { makeJob, page, RECORDED, VEHICLE } from './fixtures'

const JOB = `${API}/maintenance/jobs/7`

/** The job as the server holds it; handlers read and update it. */
function serve(initial: MaintenanceJob) {
  const state = { job: initial }
  server.use(http.get(`${JOB}/`, () => HttpResponse.json(state.job)))
  return state
}

describe('technician completes a job', () => {
  // Many keystrokes; under the full parallel suite this needs more than the 5 s default.
  it('records the work and parts, then completes; the vehicle is Available', { timeout: 15_000 }, async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    const state = serve(
      makeJob({
        status: 'In Progress',
        started_at: '2026-10-14T05:00:00Z',
        missing_work: ['service date', 'odometer reading', 'work performed', 'downtime'],
      }),
    )
    let recorded: RecordWorkRequest | undefined
    server.use(
      http.put(`${JOB}/record/`, async ({ request }) => {
        recorded = (await request.json()) as RecordWorkRequest
        state.job = makeJob({ ...RECORDED, missing_work: [] })
        return HttpResponse.json(state.job)
      }),
      http.post(`${JOB}/complete/`, () => {
        state.job = makeJob({
          ...RECORDED,
          status: 'Completed',
          closed_by: 'Tara Tech',
          closed_at: '2026-10-14T13:00:00Z',
          vehicle: {
            ...VEHICLE,
            status: 'Available',
            odometer: 15100,
            last_service_date: '2026-10-14',
            last_service_odometer: 15100,
            next_service_due: { odometer: 20100, date: '2027-04-14' },
          },
        })
        return HttpResponse.json(state.job)
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/jobs/7' })

    const odometer = await screen.findByLabelText('Odometer at service (km)')
    await user.clear(odometer)
    await user.type(odometer, '15100')
    await user.type(screen.getByLabelText('Work performed'), 'Replaced front brake pads.')
    await user.type(screen.getByLabelText('Labour cost (₹)'), '800')
    await user.type(screen.getByLabelText('Downtime (hours)'), '6.5')
    await user.click(screen.getByRole('button', { name: 'Add a part' }))
    await user.type(screen.getByLabelText('Part 1'), 'Brake pads')
    await user.type(screen.getByLabelText('Unit cost (₹)'), '1450')
    await user.click(screen.getByRole('button', { name: 'Save work record' }))

    expect(await screen.findByText('Work recorded. Total cost ₹2,250.00.')).toBeInTheDocument()
    expect(recorded).toMatchObject({
      odometer_at_service: 15100,
      labour_cost: '800',
      downtime_hours: '6.5',
      parts: [{ part_name: 'Brake pads', quantity: '1', unit_cost: '1450' }],
    })

    await user.click(screen.getByRole('button', { name: 'Complete job' }))
    expect(await screen.findByText('Job completed. MH01AB1234 is Available.')).toBeInTheDocument()
    expect(screen.getAllByText('Completed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Available').length).toBeGreaterThan(0)
    expect(screen.getByText(/20,100 km, whichever comes first/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Complete job' })).not.toBeInTheDocument()
  })

  it('shows "record work first" when the server refuses to close the job', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    serve(makeJob({ status: 'In Progress', missing_work: ['work performed', 'downtime'] }))
    server.use(
      http.post(`${JOB}/complete/`, () =>
        HttpResponse.json(
          {
            detail:
              'This job cannot be closed: record work first (missing: work performed, downtime).',
            code: 'work_incomplete',
            missing: ['work performed', 'downtime'],
          },
          { status: 400 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/jobs/7' })

    await user.click(await screen.findByRole('button', { name: 'Complete job' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('record work first (missing: work performed, downtime)')
    expect(screen.getByText('Still to record: work performed, downtime.')).toBeInTheDocument()
  })
})

describe('administrator approves an Unsafe clearance', () => {
  it('reviews the job, vehicle and work, approves, and the queue empties', async () => {
    signedInAs('ADMINISTRATOR')
    const waiting = makeJob({
      ...RECORDED,
      awaiting_clearance: true,
      clearance_requested_at: '2026-10-14T13:00:00Z',
      vehicle: { ...VEHICLE, status: 'Unsafe' },
    })
    const state = serve(waiting)
    const queue = { jobs: [waiting] }
    server.use(
      http.get(`${API}/maintenance/clearances/`, () => HttpResponse.json(page(queue.jobs))),
      http.post(`${JOB}/approve-clearance/`, () => {
        state.job = makeJob({
          ...RECORDED,
          status: 'Completed',
          closed_by: 'Anil Admin',
          closed_at: '2026-10-14T14:00:00Z',
          vehicle: { ...VEHICLE, status: 'Available' },
        })
        queue.jobs = []
        return HttpResponse.json(state.job)
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/clearances' })

    await user.click(await screen.findByRole('link', { name: /Job 7 · MH01AB1234/ }))
    expect(await screen.findByText('Awaiting administrator clearance')).toBeInTheDocument()
    const work = screen.getByRole('heading', { name: 'Work recorded' }).closest('[data-slot="card"]')!
    expect(within(work as HTMLElement).getByText('Replaced front brake pads.')).toBeInTheDocument()
    expect(within(work as HTMLElement).getByText('₹2,250.00')).toBeInTheDocument()
    expect(screen.getAllByText('Unsafe').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Clear Unsafe flag and complete' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/you are recorded as the approver/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Approve clearance' }))

    expect(await screen.findByText(/Unsafe flag cleared. Job 7 is completed and MH01AB1234 is Available./)).toBeInTheDocument()
    expect(await screen.findByText('Nothing to clear')).toBeInTheDocument()
  })
})
