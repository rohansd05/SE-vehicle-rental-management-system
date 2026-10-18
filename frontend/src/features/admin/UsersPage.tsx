import { useQuery } from '@tanstack/react-query'
import { Plus, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { listCustomers, listStaff, STAFF_ROLES } from '@/api/admin'
import { ROLE_LABELS } from '@/api/types'
import { StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { RowLink, RowList } from '@/components/row-list'
import { TONE_PILL } from '@/components/status-tone'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { stagger } from '@/lib/motion'

import { CUSTOMERS_KEY, STAFF_KEY } from './keys'

export function ActiveBadge({ active }: { active: boolean }) {
  return (
    <Badge variant="secondary" className={active ? TONE_PILL.available : TONE_PILL.inactive}>
      {active ? 'Active' : 'Disabled'}
    </Badge>
  )
}

export function BlacklistBadge() {
  return (
    <Badge variant="secondary" className={TONE_PILL.unsafe}>
      Blacklisted
    </Badge>
  )
}

function StaffAccounts() {
  const [role, setRole] = useState('')
  const [q, setQ] = useState('')
  const staff = useQuery({ queryKey: [...STAFF_KEY, { role, q }], queryFn: () => listStaff({ role, q: q.trim() }) })
  return (
    <section aria-labelledby="users-staff" className="grid gap-4">
      <h2 id="users-staff">Staff accounts</h2>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="flex items-center gap-3">
          <Label htmlFor="staff-role">Role</Label>
          <NativeSelect id="staff-role" className="w-64" value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="">All staff roles</option>
            {STAFF_ROLES.map((value) => (
              <option key={value} value={value}>
                {ROLE_LABELS[value]}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex items-center gap-3">
          <Label htmlFor="staff-search">Find</Label>
          <Input id="staff-search" type="search" className="w-64" value={q} placeholder="Name, e-mail or mobile" onChange={(event) => setQ(event.target.value)} />
        </div>
      </div>
      {staff.isPending ? (
        <LoadingState label="Loading the staff accounts…" rows={3} />
      ) : staff.isError ? (
        <ErrorState title="We couldn’t load the staff accounts" error={staff.error} onRetry={() => void staff.refetch()} />
      ) : staff.data.results.length === 0 ? (
        <EmptyState title="No staff accounts found" description="Change the role or the search, or add an account." />
      ) : (
        <RowList>
          {staff.data.results.map((account, index) => (
            <RowLink
              key={account.id}
              to={`/app/users/${account.id}`}
              srLabel="Open account"
              columns="@xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]"
              style={stagger(index)}
            >
              <span className="grid min-w-0 gap-1.5">
                <span className="font-medium">{account.name}</span>
                <span className="flex flex-wrap items-center gap-2">
                  <ActiveBadge active={account.is_active} />
                  {account.authorised_to_clear_unsafe ? (
                    <span className="inline-flex items-center gap-1 text-xs font-medium">
                      <ShieldCheck className="size-3.5" aria-hidden="true" />
                      May clear Unsafe (BR-16)
                    </span>
                  ) : null}
                </span>
              </span>
              <span className="grid min-w-0 gap-1 text-sm text-muted-foreground">
                <span>{ROLE_LABELS[account.role]}</span>
                <span>{account.branch_name ?? account.workshop}</span>
              </span>
              <span className="grid min-w-0 gap-1 text-small text-muted-foreground @xl:text-right">
                <span className="truncate">{account.email}</span>
                <span className="num">{account.mobile_no}</span>
              </span>
            </RowLink>
          ))}
        </RowList>
      )}
    </section>
  )
}

function Customers() {
  const [q, setQ] = useState('')
  const [onlyBlacklisted, setOnlyBlacklisted] = useState(false)
  const blacklisted = onlyBlacklisted ? 'true' : ''
  const customers = useQuery({
    queryKey: [...CUSTOMERS_KEY, { q, blacklisted }],
    queryFn: () => listCustomers({ q: q.trim(), blacklisted }),
  })
  return (
    <section aria-labelledby="users-customers" className="grid gap-4">
      <h2 id="users-customers">Customers and the blacklist</h2>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="flex items-center gap-3">
          <Label htmlFor="customer-search">Find</Label>
          <Input id="customer-search" type="search" className="w-64" value={q} placeholder="Name, e-mail or mobile" onChange={(event) => setQ(event.target.value)} />
        </div>
        <div className="flex items-center gap-2">
          <input
            id="customer-blacklisted"
            type="checkbox"
            className="size-4"
            checked={onlyBlacklisted}
            onChange={(event) => setOnlyBlacklisted(event.target.checked)}
          />
          <label htmlFor="customer-blacklisted" className="text-sm">
            Blacklisted only
          </label>
        </div>
      </div>
      {customers.isPending ? (
        <LoadingState label="Loading the customers…" rows={3} />
      ) : customers.isError ? (
        <ErrorState title="We couldn’t load the customers" error={customers.error} onRetry={() => void customers.refetch()} />
      ) : customers.data.results.length === 0 ? (
        <EmptyState title="No customers found" description={onlyBlacklisted ? 'No customer is blacklisted.' : 'Change the search to find a customer.'} />
      ) : (
        <RowList>
          {customers.data.results.map((customer, index) => (
            <RowLink
              key={customer.customer_id}
              to={`/app/users/customers/${customer.customer_id}`}
              srLabel="Open customer"
              columns="@xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)]"
              style={stagger(index)}
            >
              <span className="grid min-w-0 gap-1.5">
                <span className="font-medium">{customer.name}</span>
                {customer.is_blacklisted ? (
                  <span>
                    <BlacklistBadge />
                  </span>
                ) : null}
              </span>
              <span className="min-w-0 text-sm text-muted-foreground">
                {customer.is_blacklisted ? `Reason: ${customer.blacklist_reason ?? '—'}` : 'May book (BR-4)'}
              </span>
              <span className="grid min-w-0 gap-1 text-small text-muted-foreground @xl:text-right">
                <span className="truncate">{customer.email}</span>
                <span className="num">{customer.mobile_no}</span>
              </span>
            </RowLink>
          ))}
        </RowList>
      )}
    </section>
  )
}

/** Fleet.Users and BR-4 (UC 12): staff accounts, and customers to blacklist. */
export function UsersPage() {
  const location = useLocation()
  const flash = (location.state as { flash?: string } | null)?.flash ?? null
  return (
    <section>
      <PageHeader
        title="Users"
        photo="band-licence-checks-1"
        variant="compact"
        description="Staff accounts and the customer blacklist."
        actions={
          <Button asChild>
            <Link to="/app/users/new">
              <Plus aria-hidden="true" />
              Add a staff account
            </Link>
          </Button>
        }
      />
      <StatusMessage message={flash} tone="success" />
      <div className="mt-4 grid gap-12">
        <StaffAccounts />
        <Customers />
      </div>
    </section>
  )
}
