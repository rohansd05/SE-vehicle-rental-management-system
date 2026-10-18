import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { todayISO } from '@/lib/dates'
import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { toCsv } from './csv'
import { makeCustomers, makeDashboard, makeMaintenance, makeRevenue, makeUtilisation } from './fixtures'

const REPORTS = { utilisation: makeUtilisation(), revenue: makeRevenue(), maintenance: makeMaintenance(), customers: makeCustomers() }

/** Serve the reports, recording each request's type and period. */
function serveReports(overrides: Partial<Record<keyof typeof REPORTS, () => Response>> = {}) {
  const requests: { type: string; from: string | null; to: string | null }[] = []
  server.use(
    http.get(`${API}/reports/:type/`, ({ params, request }) => {
      const type = String(params.type) as keyof typeof REPORTS
      const search = new URL(request.url).searchParams
      requests.push({ type, from: search.get('date_from'), to: search.get('date_to') })
      return overrides[type]?.() ?? HttpResponse.json(REPORTS[type])
    }),
  )
  return requests
}

/** Open /app/reports and ask for `report` over `from` to `to` with the form (UC 14 step 1). */
async function showReport(report: string, from = '2026-10-01', to = '2026-10-15') {
  const user = userEvent.setup()
  renderApp({ route: '/app/reports' })
  await screen.findByRole('button', { name: 'Show report' })
  await user.selectOptions(screen.getByLabelText('Report'), report)
  await user.clear(screen.getByLabelText('From'))
  await user.type(screen.getByLabelText('From'), from)
  await user.clear(screen.getByLabelText('To'))
  await user.type(screen.getByLabelText('To'), to)
  await user.click(screen.getByRole('button', { name: 'Show report' }))
  return user
}

function table(name: string) {
  return screen.getByRole('table', { name })
}

afterEach(() => vi.restoreAllMocks())

describe('reports (UC 14 View Reports)', () => {
  it('is in the menu of Administrators and Branch Managers, no longer marked Soon', async () => {
    signedInAs('ADMINISTRATOR')
    serveReports()
    renderApp({ route: '/app/reports' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Reports' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Reports/ })[0]).not.toHaveTextContent('Soon')
  })

  it('opens on utilisation for this month: figures, charts and the least utilised vehicles', async () => {
    signedInAs('ADMINISTRATOR')
    const requests = serveReports()
    renderApp({ route: '/app/reports' })
    expect(await screen.findByRole('table', { name: 'Least utilised vehicles' })).toBeInTheDocument()
    const today = todayISO()
    expect(requests[0]).toEqual({ type: 'utilisation', from: `${today.slice(0, 8)}01`, to: today })
    expect(screen.getByText(/All branches\./)).toBeInTheDocument()
    expect(screen.getByText('Utilisation by vehicle category')).toBeInTheDocument()
    const row = within(table('By vehicle')).getByText('MH02DB2001').closest('tr') as HTMLElement
    expect(row).toHaveTextContent('Hatchback')
    expect(row).toHaveTextContent('46.0')
    expect(row).toHaveTextContent('1.0') // days under maintenance
    expect(row).toHaveTextContent('13.7%')
  })

  it('shows the revenue lines apart; refunds awaiting approval are not counted', async () => {
    signedInAs('ADMINISTRATOR')
    const requests = serveReports()
    await showReport('revenue')

    const lines = await screen.findByRole('table', { name: 'Revenue' })
    expect(requests.at(-1)).toEqual({ type: 'revenue', from: '2026-10-01', to: '2026-10-15' })
    const line = (name: RegExp) => within(lines).getByText(name).closest('tr') as HTMLElement
    expect(line(/^Rental income$/)).toHaveTextContent('₹3,000.00')
    expect(line(/^Add-on income$/)).toHaveTextContent('₹200.00')
    expect(line(/^Discounts$/)).toHaveTextContent('-₹100.00')
    expect(line(/^Debit notes/)).toHaveTextContent('₹236.00')
    expect(line(/^Credit notes/)).toHaveTextContent('₹118.00')
    expect(line(/^Net revenue$/)).toHaveTextContent('₹3,776.00Yes')
    expect(line(/^Refunds awaiting approval$/)).toHaveTextContent('₹500.00No')
    expect(within(table('By payment method')).getByText('Card').closest('tr')).toHaveTextContent('₹1,416.00')
    expect(screen.getByText('Net revenue by branch')).toBeInTheDocument()
  })

  it('shows maintenance cost per job type, including jobs the system raised', async () => {
    signedInAs('ADMINISTRATOR')
    serveReports()
    await showReport('maintenance')
    const byType = await screen.findByRole('table', { name: 'By job type' })
    expect(within(byType).getByText('Preventive').closest('tr')).toHaveTextContent('11₹500.00₹300.00₹800.00')
    expect(within(byType).getByText('Inspection').closest('tr')).toHaveTextContent('₹0.00')
    expect(within(table('By vehicle')).getByText('MH02DB2001').closest('tr')).toHaveTextContent('₹2,500.00')
    expect(screen.getByText('Cost by job type')).toBeInTheDocument()
  })

  it('shows new, active and top customers, no-shows and dues', async () => {
    signedInAs('ADMINISTRATOR')
    serveReports()
    await showReport('customers')
    const top = await screen.findByRole('table', { name: 'Top customers' })
    expect(within(top).getByText('Asha Rao').closest('tr')).toHaveTextContent('21₹2,360.00')
    expect(within(table('Customers with dues')).getByText('=Ravi Kumar').closest('tr')).toHaveTextContent('₹850.00')
    expect(screen.getByText('No-shows', { selector: 'dt' }).nextElementSibling).toHaveTextContent('1')
  })

  it('a Branch Manager’s report is limited to their branch (UC 14 extension 1a)', async () => {
    signedInAs('BRANCH_MANAGER')
    serveReports({ utilisation: () => HttpResponse.json(makeUtilisation({ scope: 'Andheri' })) })
    renderApp({ route: '/app/reports' })
    expect(await screen.findByText(/Andheri branch only\./)).toBeInTheDocument()
    expect(screen.getByText(/for your branch, for any period/)).toBeInTheDocument()
  })

  it('shows the server’s refusal of a period on the To field', async () => {
    signedInAs('ADMINISTRATOR')
    serveReports({
      utilisation: () =>
        HttpResponse.json({ date_to: ['The end of the period cannot be before its start.'] }, { status: 400 }),
    })
    await showReport('utilisation', '2026-10-15', '2026-10-01')
    expect(await screen.findByText('The end of the period cannot be before its start.')).toBeInTheDocument()
    expect(screen.getByLabelText('To')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('says so when a report cannot be computed, and tries again', async () => {
    signedInAs('ADMINISTRATOR')
    let fail = true
    serveReports({
      utilisation: () => (fail ? HttpResponse.json({ detail: 'Server error.' }, { status: 500 }) : HttpResponse.json(REPORTS.utilisation)),
    })
    const user = userEvent.setup()
    renderApp({ route: '/app/reports' })
    expect(await screen.findByText('We couldn’t compute the report')).toBeInTheDocument()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('table', { name: 'By vehicle' })).toBeInTheDocument()
  })

  it('exports the report to a CSV file with the exact amounts (UC 14 step 3)', async () => {
    signedInAs('ADMINISTRATOR')
    serveReports()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const created = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:report')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const user = await showReport('revenue')
    await screen.findByRole('table', { name: 'Revenue' })
    await user.click(screen.getByRole('button', { name: 'Export CSV' }))

    expect(click).toHaveBeenCalledOnce()
    const link = click.mock.contexts[0] as HTMLAnchorElement
    expect(link.download).toBe('revenue-2026-10-01-to-2026-10-15.csv')
    const blob = created.mock.calls[0][0] as Blob
    const csv = await blob.text()
    expect(csv).toContain('Revenue\r\nLine,Amount,In net revenue\r\nRental income,3000.00,Yes')
    expect(csv).toContain('Net revenue,3776.00,Yes')
    expect(csv).toContain('By payment method\r\nMethod,Charges,Refunds,Net\r\nCard,1534.00,118.00,1416.00')
  })
})

describe('the CSV file', () => {
  it('quotes commas and quotes, keeps negative amounts, and defuses formulas in text', () => {
    const csv = toCsv([
      {
        title: 'Customers',
        columns: [
          { label: 'Name', value: (row: { name: string; due: string }) => row.name },
          { label: 'Due', value: (row: { name: string; due: string }) => row.due, kind: 'money' },
        ],
        rows: [
          { name: 'Rao, "Asha"', due: '-100.00' },
          { name: '=HYPERLINK("x")', due: '850.00' },
        ],
      },
    ])
    expect(csv).toBe('Customers\r\nName,Due\r\n"Rao, ""Asha""",-100.00\r\n"\'=HYPERLINK(""x"")",850.00')
  })
})

describe('the home page summary (Report.Dashboard)', () => {
  it('shows an Administrator today’s figures, bookings and revenue, and the fleet by status', async () => {
    signedInAs('ADMINISTRATOR')
    server.use(
      http.get(`${API}/reports/summary/`, () =>
        HttpResponse.json(
          makeDashboard({
            collections_today: 3,
            returns_today: 2,
            overdue_returns: 1,
            open_maintenance_jobs: 4,
            vehicles_by_status: [{ status: 'Available', count: 12 }, { status: 'On Rent', count: 5 }],
            periods: [
              { period: 'today', bookings: 2, revenue: '4248.00' },
              { period: 'week', bookings: 6, revenue: '12744.00' },
              { period: 'month', bookings: 20, revenue: '50000.00' },
            ],
          }),
        ),
      ),
    )
    renderApp({ route: '/app' })
    expect(await screen.findByRole('heading', { name: 'Today at a glance' })).toBeInTheDocument()
    expect(screen.getByText('Collections due today', { selector: 'dt' }).nextElementSibling).toHaveTextContent('3')
    expect(screen.getByText('Overdue returns', { selector: 'dt' }).nextElementSibling).toHaveTextContent('1')
    expect(screen.getByText('Open maintenance jobs', { selector: 'dt' }).nextElementSibling).toHaveTextContent('4')
    const figures = table('Bookings and revenue')
    expect(within(figures).getByText('This week').closest('tr')).toHaveTextContent('6₹12,744.00')
    expect(screen.getByText('On Rent').closest('li')).toHaveTextContent('5')
    expect(screen.getByRole('link', { name: 'Open reports' })).toHaveAttribute('href', '/app/reports')
  })

  it('a Branch Manager’s summary names their branch', async () => {
    signedInAs('BRANCH_MANAGER')
    server.use(http.get(`${API}/reports/summary/`, () => HttpResponse.json(makeDashboard({ scope: 'Andheri' }))))
    renderApp({ route: '/app' })
    expect(await screen.findByText('Andheri branch only.')).toBeInTheDocument()
  })

  it.each(['CUSTOMER', 'BRANCH_STAFF', 'MAINTENANCE_TECHNICIAN'] as const)('is not shown to %s', async (role) => {
    signedInAs(role)
    const asked = vi.fn()
    server.use(
      http.get(`${API}/reports/summary/`, () => {
        asked()
        return HttpResponse.json(makeDashboard())
      }),
    )
    renderApp({ route: '/app' })
    await screen.findByRole('heading', { name: /Welcome/ })
    expect(screen.queryByText('Today at a glance')).not.toBeInTheDocument()
    expect(asked).not.toHaveBeenCalled()
  })
})
