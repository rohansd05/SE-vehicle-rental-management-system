import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { makeJob, page, VEHICLE } from './fixtures'

describe('vehicle status badge', () => {
  it.each(['Available', 'On Rent', 'Under Maintenance', 'Unsafe', 'Retired'] as const)(
    'names the %s status in text, not colour alone',
    (status) => {
      render(<VehicleStatusBadge status={status} />)
      expect(screen.getByText(status)).toBeInTheDocument()
    },
  )
})

describe('technician: my jobs', () => {
  it('lists assigned jobs and filters by status', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    const seen = vi.fn()
    server.use(
      http.get(`${API}/maintenance/jobs/`, ({ request }) => {
        const status = new URL(request.url).searchParams.get('status')
        seen(status)
        const jobs = status === 'Completed' ? [] : [makeJob()]
        return HttpResponse.json(page(jobs))
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/jobs' })

    const link = await screen.findByRole('link', { name: /Job 7 · MH01AB1234/ })
    expect(within(link).getByText('Scheduled')).toBeInTheDocument()
    expect(within(link).getByText('Under Maintenance')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Status'), 'Completed')
    expect(await screen.findByText('No completed jobs')).toBeInTheDocument()
    expect(seen).toHaveBeenLastCalledWith('Completed')
  })

  it('shows an error state with a retry', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    server.use(
      http.get(`${API}/maintenance/jobs/`, () =>
        HttpResponse.json({ detail: 'Server unavailable.' }, { status: 500 }),
      ),
    )
    renderApp({ route: '/app/jobs' })
    expect(await screen.findByRole('alert')).toHaveTextContent('Server unavailable.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows the awaiting-clearance state and no Complete button', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    const job = makeJob({
      status: 'In Progress',
      awaiting_clearance: true,
      clearance_requested_at: '2026-10-14T13:00:00Z',
      vehicle: { ...VEHICLE, status: 'Unsafe' },
    })
    server.use(http.get(`${API}/maintenance/jobs/7/`, () => HttpResponse.json(job)))
    renderApp({ route: '/app/jobs/7' })

    expect(await screen.findByText('Awaiting administrator clearance')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Complete job' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Record the work' })).not.toBeInTheDocument()
  })

  it('is the technician’s menu entry, no longer marked Soon', async () => {
    signedInAs('MAINTENANCE_TECHNICIAN')
    server.use(http.get(`${API}/maintenance/jobs/`, () => HttpResponse.json(page([]))))
    renderApp({ route: '/app/jobs' })
    expect(await screen.findByText('No maintenance jobs are assigned to you.')).toBeInTheDocument()
    const nav = screen.getAllByRole('link', { name: /Maintenance jobs/ })[0]
    expect(nav).not.toHaveTextContent('Soon')
  })
})

describe('branch staff: report and schedule', () => {
  function staffWithVehicles() {
    signedInAs('BRANCH_STAFF')
    server.use(
      http.get(`${API}/maintenance/vehicles/`, () =>
        HttpResponse.json([{ ...VEHICLE, status: 'Available' }]),
      ),
    )
  }

  it('validates the report form, then sends it and opens the new job', async () => {
    staffWithVehicles()
    let sent: unknown
    server.use(
      http.post(`${API}/maintenance/jobs/`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json(makeJob({ status: 'Reported', technician: null }), { status: 201 })
      }),
      http.get(`${API}/maintenance/jobs/7/`, () =>
        HttpResponse.json(makeJob({ status: 'Reported', technician: null })),
      ),
      http.get(`${API}/maintenance/technicians/`, () =>
        HttpResponse.json([{ technician_id: 3, name: 'Tara Tech', workshop: 'Agency workshop' }]),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/maintenance/report' })

    await user.click(await screen.findByRole('button', { name: 'Report fault' }))
    expect(await screen.findByText('Choose the vehicle.')).toBeInTheDocument()
    expect(screen.getByText('Describe the problem.')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Vehicle'), '12')
    await user.selectOptions(screen.getByLabelText('Job type'), 'Corrective')
    await user.selectOptions(screen.getByLabelText('Severity'), 'Critical')
    await user.type(screen.getByLabelText('Problem'), 'Brakes failed on test drive.')
    await user.click(screen.getByLabelText('Flag the vehicle as Unsafe'))
    await user.click(screen.getByRole('button', { name: 'Report fault' }))

    expect(await screen.findByText(/Job 7 reported/)).toBeInTheDocument()
    expect(sent).toEqual({
      vehicle: 12,
      job_type: 'Corrective',
      severity: 'Critical',
      reported_problem: 'Brakes failed on test drive.',
      flag_unsafe: true,
    })
    expect(screen.getByRole('heading', { name: 'Assign and schedule' })).toBeInTheDocument()
  })

  it('lists conflicting bookings and schedules anyway on confirmation', async () => {
    signedInAs('BRANCH_STAFF')
    const bodies: Array<{ confirm_conflicts: boolean }> = []
    server.use(
      http.get(`${API}/maintenance/jobs/7/`, () =>
        HttpResponse.json(makeJob({ status: 'Reported', technician: null })),
      ),
      http.get(`${API}/maintenance/technicians/`, () =>
        HttpResponse.json([{ technician_id: 3, name: 'Tara Tech', workshop: 'Agency workshop' }]),
      ),
      http.post(`${API}/maintenance/jobs/7/schedule/`, async ({ request }) => {
        const body = (await request.json()) as { confirm_conflicts: boolean }
        bodies.push(body)
        if (!body.confirm_conflicts) {
          return HttpResponse.json(
            {
              detail: 'The maintenance period overlaps Confirmed bookings. Confirm to schedule it anyway.',
              code: 'schedule_conflict',
              bookings: [
                {
                  booking_reference: 'VRMS-20261014-0001',
                  pickup_datetime: '2026-10-14T05:30:00Z',
                  return_datetime: '2026-10-15T05:30:00Z',
                },
              ],
            },
            { status: 409 },
          )
        }
        return HttpResponse.json(makeJob())
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/maintenance/7' })

    await user.selectOptions(await screen.findByLabelText('Technician'), '3')
    await user.type(screen.getByLabelText('Starts'), '2026-10-14T10:00')
    await user.type(screen.getByLabelText('Ends'), '2026-10-14T18:00')
    await user.click(screen.getByRole('button', { name: 'Schedule job' }))

    expect(await screen.findByText(/VRMS-20261014-0001/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Schedule anyway' }))
    expect(await screen.findByText(/Job scheduled and assigned to Tara Tech/)).toBeInTheDocument()
    expect(bodies.map((body) => body.confirm_conflicts)).toEqual([false, true])
  })

  it('keeps customers out of the maintenance screens', async () => {
    signedInAs('CUSTOMER')
    renderApp({ route: '/app/maintenance' })
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
  })
})

describe('administrator: clearance queue', () => {
  it('shows an empty state when nothing waits', async () => {
    signedInAs('ADMINISTRATOR')
    server.use(http.get(`${API}/maintenance/clearances/`, () => HttpResponse.json(page([]))))
    renderApp({ route: '/app/clearances' })
    expect(await screen.findByText('Nothing to clear')).toBeInTheDocument()
  })
})
