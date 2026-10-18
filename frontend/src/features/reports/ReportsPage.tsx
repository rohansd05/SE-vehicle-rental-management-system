import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { Field } from '@/components/form'
import { PageHeader } from '@/components/page'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { useSignedInUser } from '@/features/auth/auth-context'
import { useAgency } from '@/hooks/page'
import { formatDate, todayISO } from '@/lib/dates'

import { getReport, type ReportPeriod, type Reports, REPORTS_KEY, type ReportType } from './api'
import { downloadCsv, toCsv } from './csv'
import { Figures, ReportTable } from './parts'
import { REPORT_VIEWS, type ReportView } from './views'

const TYPES = Object.keys(REPORT_VIEWS) as ReportType[]

/** The report, its scope and its export (UC 14 steps 2 and 3, extension 1a). */
function ReportBody<T extends ReportType>({
  type,
  data,
  period,
}: {
  type: T
  data: Reports[T]
  period: ReportPeriod
}) {
  const { currency } = useAgency()
  const view: ReportView<Reports[T]> = REPORT_VIEWS[type]
  const sections = view.sections(data)
  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {view.label}, <span className="num whitespace-nowrap">{formatDate(period.date_from)}</span> to{' '}
          <span className="num whitespace-nowrap">{formatDate(period.date_to)}</span>, local time.{' '}
          {data.scope === 'All branches' ? 'All branches.' : `${data.scope} branch only.`}
        </p>
        <Button
          variant="outline"
          onClick={() =>
            downloadCsv(`${type}-${period.date_from}-to-${period.date_to}.csv`, toCsv(sections))
          }
        >
          <Download aria-hidden="true" />
          Export CSV
        </Button>
      </div>
      <Figures items={view.figures(data, currency)} />
      <div className="grid gap-10 xl:grid-cols-2">{view.charts(data, currency)}</div>
      {sections.map((section) => (
        <ReportTable key={section.title} section={section} currency={currency} />
      ))}
    </div>
  )
}

/** Exp 2 UC 14 View Reports; Exp 3 BranchManager.view_branch_reports(). */
export function ReportsPage() {
  const user = useSignedInUser()
  const [params, setParams] = useSearchParams()
  const today = todayISO()
  const type = TYPES.find((name) => name === params.get('report')) ?? 'utilisation'
  const period: ReportPeriod = {
    date_from: params.get('date_from') || `${today.slice(0, 8)}01`,
    date_to: params.get('date_to') || today,
  }
  const [draft, setDraft] = useState({ report: type, ...period })
  const report = useQuery({
    queryKey: [...REPORTS_KEY, type, period],
    queryFn: () => getReport(type, period),
  })
  const fieldErrors = report.error instanceof ApiError ? report.error.fieldErrors : {}
  const set = (name: keyof typeof draft) => (event: { target: { value: string } }) =>
    setDraft((current) => ({ ...current, [name]: event.target.value }))
  const submit = (event: FormEvent) => {
    event.preventDefault()
    setParams(new URLSearchParams(draft))
  }

  return (
    <section>
      <PageHeader
        title="Reports"
        photo="band-dashboard-1"
        variant="compact"
        description={
          user.role === 'BRANCH_MANAGER'
            ? 'Utilisation, revenue, maintenance cost and customers for your branch, for any period.'
            : 'Utilisation, revenue, maintenance cost and customers across every branch, for any period.'
        }
      />
      <form
        noValidate
        onSubmit={submit}
        className="mb-8 grid gap-4 border-y py-4 sm:grid-cols-2 xl:grid-cols-4 xl:items-start"
      >
        <Field id="report-type" label="Report">
          <NativeSelect id="report-type" value={draft.report} onChange={set('report')}>
            {TYPES.map((name) => (
              <option key={name} value={name}>
                {REPORT_VIEWS[name].label}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field id="report-from" label="From" error={fieldErrors.date_from?.[0]}>
          <Input
            id="report-from"
            type="date"
            value={draft.date_from}
            max={today}
            aria-invalid={Boolean(fieldErrors.date_from)}
            aria-describedby={fieldErrors.date_from ? 'report-from-error' : undefined}
            onChange={set('date_from')}
          />
        </Field>
        <Field id="report-to" label="To" error={fieldErrors.date_to?.[0]}>
          <Input
            id="report-to"
            type="date"
            value={draft.date_to}
            aria-invalid={Boolean(fieldErrors.date_to)}
            aria-describedby={fieldErrors.date_to ? 'report-to-error' : undefined}
            onChange={set('date_to')}
          />
        </Field>
        <div className="grid gap-1.5 xl:pt-8">
          <Button type="submit" disabled={report.isFetching}>
            {report.isFetching ? 'Computing the report…' : 'Show report'}
          </Button>
        </div>
      </form>
      {report.isPending ? (
        report.isFetching ? (
          <LoadingState label="Computing the report…" rows={3} />
        ) : null
      ) : report.isError ? (
        Object.keys(fieldErrors).length ? null : (
          <ErrorState title="We couldn’t compute the report" error={report.error} onRetry={() => void report.refetch()} />
        )
      ) : (
        <ReportBody type={type} data={report.data} period={period} />
      )}
    </section>
  )
}
