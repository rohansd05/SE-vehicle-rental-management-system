import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { type AuditEntry, auditFilterOptions, type AuditFilters, listAudit } from '@/api/admin'
import { ROLE_LABELS } from '@/api/types'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { useSignedInUser } from '@/features/auth/auth-context'
import { formatDateTime } from '@/lib/dates'
import { stagger } from '@/lib/motion'

import { AUDIT_KEY } from './keys'

const FILTERS = ['actor', 'action', 'entity_type', 'entity_id', 'date_from', 'date_to'] as const

function values(value: unknown): string {
  return value === null || value === undefined ? '—' : JSON.stringify(value, null, 2)
}

function Entry({ entry, index }: { entry: AuditEntry; index: number }) {
  return (
    <li className="enter grid min-w-0 gap-x-8 gap-y-2 border-b py-4 @xl:grid-cols-[13rem_minmax(0,1fr)_minmax(0,1.2fr)]" style={stagger(index)}>
      <span className="num text-sm whitespace-nowrap text-muted-foreground">{formatDateTime(entry.timestamp)}</span>
      <span className="grid min-w-0 gap-1">
        <span className="font-medium">{entry.action}</span>
        <span className="text-sm text-muted-foreground">
          {entry.entity_type} <span className="num">#{entry.entity_id}</span>
        </span>
      </span>
      <span className="grid min-w-0 gap-1 text-sm">
        <span>
          {entry.actor ? (
            <>
              {entry.actor.name} <span className="text-muted-foreground">({ROLE_LABELS[entry.actor.role]}, {entry.actor.email})</span>
            </>
          ) : (
            <span className="text-muted-foreground">The system</span>
          )}
        </span>
        <details>
          <summary className="cursor-pointer text-primary">Previous and new values</summary>
          <div className="mt-2 grid gap-2 @lg:grid-cols-2">
            <div>
              <p className="text-label text-muted-foreground">Before</p>
              <pre className="num max-h-64 overflow-auto rounded-md bg-canvas-sunken p-2 text-xs whitespace-pre-wrap">{values(entry.before)}</pre>
            </div>
            <div>
              <p className="text-label text-muted-foreground">After</p>
              <pre className="num max-h-64 overflow-auto rounded-md bg-canvas-sunken p-2 text-xs whitespace-pre-wrap">{values(entry.after)}</pre>
            </div>
          </div>
        </details>
      </span>
    </li>
  )
}

/**
 * Fleet.Audit, SE-10: the audit log, read-only, with filters by actor, action, entity
 * and date. An Administrator reads every entry; a Branch Manager their own branch's.
 */
export function AuditPage() {
  const user = useSignedInUser()
  const [params, setParams] = useSearchParams()
  const filters: AuditFilters = Object.fromEntries(
    [...FILTERS, 'page'].map((name) => [name, params.get(name) ?? '']),
  )
  const [draft, setDraft] = useState<AuditFilters>(filters)
  const options = useQuery({ queryKey: [...AUDIT_KEY, 'filters'], queryFn: auditFilterOptions })
  const entries = useQuery({
    queryKey: [...AUDIT_KEY, filters],
    queryFn: () => listAudit(filters),
    placeholderData: keepPreviousData,
  })

  const apply = (next: AuditFilters) => {
    const search = new URLSearchParams()
    for (const [name, value] of Object.entries(next)) if (value) search.set(name, value)
    setParams(search)
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    apply({ ...draft, page: '' })
  }
  const set = (name: keyof AuditFilters) => (event: { target: { value: string } }) =>
    setDraft((current) => ({ ...current, [name]: event.target.value }))
  const page = Number(filters.page || '1')

  return (
    <section>
      <PageHeader
        title="Audit log"
        photo="band-quiet-2"
        variant="compact"
        description={
          user.role === 'BRANCH_MANAGER'
            ? 'Every change to your branch’s bookings, vehicles, jobs and payments, and what your staff did. Nothing here can be edited.'
            : 'Every change to fleet, tariff, branch and user data.'
        }
      />
      <form noValidate onSubmit={submit} className="mb-6 grid gap-4 border-y py-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 xl:items-end">
        <div className="grid gap-1.5">
          <Label htmlFor="audit-actor">Actor</Label>
          <Input id="audit-actor" value={draft.actor ?? ''} placeholder="Name, e-mail or system" onChange={set('actor')} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="audit-action">Action</Label>
          <NativeSelect id="audit-action" value={draft.action ?? ''} onChange={set('action')}>
            <option value="">All actions</option>
            {(options.data?.actions ?? []).map((action) => (
              <option key={action}>{action}</option>
            ))}
          </NativeSelect>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="audit-entity">Entity</Label>
          <NativeSelect id="audit-entity" value={draft.entity_type ?? ''} onChange={set('entity_type')}>
            <option value="">All entities</option>
            {(options.data?.entity_types ?? []).map((type) => (
              <option key={type}>{type}</option>
            ))}
          </NativeSelect>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="audit-from">From</Label>
          <Input id="audit-from" type="date" value={draft.date_from ?? ''} onChange={set('date_from')} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="audit-to">To</Label>
          <Input id="audit-to" type="date" value={draft.date_to ?? ''} onChange={set('date_to')} />
        </div>
        <div className="flex flex-wrap gap-3">
          <Button type="submit">Apply filters</Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setDraft({})
              apply({})
            }}
          >
            Clear
          </Button>
        </div>
      </form>
      {filters.entity_id ? (
        <p className="mb-3 text-sm text-muted-foreground">
          Showing the history of {filters.entity_type || 'record'} <span className="num">#{filters.entity_id}</span>.
        </p>
      ) : null}
      {entries.isPending ? (
        <LoadingState label="Loading the audit log…" rows={4} />
      ) : entries.isError ? (
        <ErrorState title="We couldn’t load the audit log" error={entries.error} onRetry={() => void entries.refetch()} />
      ) : entries.data.results.length === 0 ? (
        <EmptyState title="No entries" description="Nothing matches these filters. Change or clear them." />
      ) : (
        <>
          <p className="mb-3 text-sm text-muted-foreground" aria-live="polite">
            {entries.data.count} {entries.data.count === 1 ? 'entry' : 'entries'}, newest first.
          </p>
          <ul aria-label="Audit entries" className="@container border-t">
            {entries.data.results.map((entry, index) => (
              <Entry key={entry.id} entry={entry} index={index} />
            ))}
          </ul>
          <div className="mt-4 flex justify-end gap-3">
            <Button variant="outline" disabled={!entries.data.previous} onClick={() => apply({ ...filters, page: String(page - 1) })}>
              Previous page
            </Button>
            <Button variant="outline" disabled={!entries.data.next} onClick={() => apply({ ...filters, page: String(page + 1) })}>
              Next page
            </Button>
          </div>
        </>
      )}
    </section>
  )
}
