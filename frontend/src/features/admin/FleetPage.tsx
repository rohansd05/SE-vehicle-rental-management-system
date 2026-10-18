import { useQuery } from '@tanstack/react-query'
import { Building2, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { listVehicles } from '@/api/admin'
import type { VehicleStatus } from '@/api/maintenance'
import { StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { RowLink, RowList } from '@/components/row-list'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { formatKm } from '@/features/maintenance/format'
import { stagger } from '@/lib/motion'

import { documentAlertText } from './format'
import { VEHICLES_KEY } from './keys'

const STATUSES: readonly VehicleStatus[] = ['Available', 'On Rent', 'Under Maintenance', 'Unsafe', 'Retired']

/** Fleet.Status (UC 11): every vehicle with its current status; add one, or manage branches. */
export function FleetPage() {
  const location = useLocation()
  const flash = (location.state as { flash?: string } | null)?.flash ?? null
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const vehicles = useQuery({
    queryKey: [...VEHICLES_KEY, { status, q }],
    queryFn: () => listVehicles({ status, q: q.trim() }),
  })

  return (
    <section>
      <PageHeader
        title="Fleet"
        photo="step-search-1"
        variant="compact"
        description="Vehicles, branches and statutory documents."
        actions={
          <>
            <Button asChild>
              <Link to="/app/fleet/new">
                <Plus aria-hidden="true" />
                Add a vehicle
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/app/fleet/branches">
                <Building2 aria-hidden="true" />
                Branches
              </Link>
            </Button>
          </>
        }
      />
      <StatusMessage message={flash} tone="success" />
      <div className="mt-4 mb-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex items-center gap-3">
            <Label htmlFor="fleet-status">Status</Label>
            <NativeSelect id="fleet-status" className="w-56" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </NativeSelect>
          </div>
          <div className="flex items-center gap-3">
            <Label htmlFor="fleet-search">Find</Label>
            <Input
              id="fleet-search"
              className="w-64"
              type="search"
              value={q}
              placeholder="Registration, brand or model"
              onChange={(event) => setQ(event.target.value)}
            />
          </div>
        </div>
        {vehicles.data && vehicles.data.results.length > 0 ? (
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {vehicles.data.count} {vehicles.data.count === 1 ? 'vehicle' : 'vehicles'}
            {vehicles.data.next ? `, showing the first ${vehicles.data.results.length}` : ''}.
          </p>
        ) : null}
      </div>
      {vehicles.isPending ? (
        <LoadingState label="Loading the fleet…" rows={4} />
      ) : vehicles.isError ? (
        <ErrorState title="We couldn’t load the fleet" error={vehicles.error} onRetry={() => void vehicles.refetch()} />
      ) : vehicles.data.results.length === 0 ? (
        <EmptyState
          title="No vehicles found"
          description={status || q ? 'Change the status or the search to see more vehicles.' : 'Add the first vehicle of the fleet.'}
        />
      ) : (
        <RowList>
          {vehicles.data.results.map((vehicle, index) => (
            <RowLink
              key={vehicle.id}
              to={`/app/fleet/${vehicle.id}`}
              srLabel="Open vehicle"
              columns="@xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1.3fr)_minmax(0,1fr)]"
              style={stagger(index)}
            >
              <span className="grid min-w-0 gap-1.5">
                <span className="font-medium">
                  <span className="num whitespace-nowrap">{vehicle.registration_no}</span> · {vehicle.brand} {vehicle.model}
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  <VehicleStatusBadge status={vehicle.status} />
                </span>
              </span>
              <span className="grid min-w-0 gap-1 text-sm text-muted-foreground">
                <span>
                  {vehicle.category_name} · {vehicle.fuel_type} · {vehicle.home_branch_name}
                </span>
                {vehicle.document_alerts.length ? (
                  <span className="text-status-unsafe">{vehicle.document_alerts.map(documentAlertText).join('; ')}</span>
                ) : (
                  <span>Documents valid</span>
                )}
              </span>
              <span className="flex min-w-0 flex-wrap gap-x-4 gap-y-1 text-small text-muted-foreground @xl:flex-col @xl:items-end @xl:text-right">
                <span>Odometer {formatKm(vehicle.odometer)}</span>
                <span>{vehicle.photo_count} photos</span>
              </span>
            </RowLink>
          ))}
        </RowList>
      )}
    </section>
  )
}
