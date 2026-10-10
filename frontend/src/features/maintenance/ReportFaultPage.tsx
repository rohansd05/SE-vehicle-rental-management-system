import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'

import { JOB_TYPES, listMaintenanceVehicles, reportJob, SEVERITIES } from '@/api/maintenance'
import { Field, FormAlert, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { applyServerErrors, describedBy } from '@/lib/form'

import { formatKm } from './format'
import { NativeSelect } from './JobList'
import { JOBS_KEY, VEHICLES_KEY } from './keys'
import { type ReportValues, reportSchema } from './schemas'

const FIELDS = ['vehicle', 'job_type', 'severity', 'reported_problem', 'flag_unsafe'] as const

/** Maint.Create: Branch Staff, Branch Managers and Administrators report a fault. */
export function ReportFaultPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [formError, setFormError] = useState<string | null>(null)
  const vehicles = useQuery({ queryKey: VEHICLES_KEY, queryFn: listMaintenanceVehicles })
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors },
  } = useForm<ReportValues>({
    resolver: zodResolver(reportSchema),
    defaultValues: { vehicle: '', reported_problem: '', flag_unsafe: false },
  })

  const report = useMutation({
    mutationFn: (values: ReportValues) => reportJob({ ...values, vehicle: Number(values.vehicle) }),
    onSuccess: async (job) => {
      await queryClient.invalidateQueries({ queryKey: JOBS_KEY })
      await queryClient.invalidateQueries({ queryKey: VEHICLES_KEY })
      navigate(`/app/maintenance/${job.job_id}`, {
        state: { flash: `Job ${job.job_id} reported. Assign a technician and a date to schedule it.` },
      })
    },
    onError: (error) => setFormError(applyServerErrors(error, setError, FIELDS)),
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(null)
    report.mutate(values)
  })

  const vehicleId = useWatch({ control, name: 'vehicle' })
  const choosable = vehicles.data?.filter((vehicle) => vehicle.status !== 'Retired') ?? []
  const selected = choosable.find((vehicle) => String(vehicle.id) === vehicleId)

  return (
    <section className="max-w-2xl">
      <Button asChild variant="ghost" size="lg" className="mb-2 -ml-2 h-10">
        <Link to="/app/maintenance">
          <ArrowLeft aria-hidden="true" />
          Back to maintenance
        </Link>
      </Button>
      <PageHeader
        title="Report a fault"
        description="The job starts as Reported. The vehicle goes Under Maintenance when the job is scheduled, or at once if you flag it Unsafe."
      />
      {vehicles.isPending ? (
        <LoadingState label="Loading your branch’s vehicles…" />
      ) : vehicles.isError ? (
        <ErrorState title="We couldn’t load the vehicles" error={vehicles.error} onRetry={() => void vehicles.refetch()} />
      ) : choosable.length === 0 ? (
        <EmptyState title="No vehicles" description="Your branch has no vehicles that can be sent for maintenance." />
      ) : (
        <Card>
          <CardContent>
            <form onSubmit={onSubmit} noValidate className="grid gap-5">
              <FormAlert message={formError} />
              <Field id="report-vehicle" label="Vehicle" error={errors.vehicle?.message}>
                <NativeSelect
                  id="report-vehicle"
                  aria-invalid={errors.vehicle ? true : undefined}
                  aria-describedby={describedBy('report-vehicle', { error: Boolean(errors.vehicle) })}
                  {...register('vehicle')}
                >
                  <option value="">Choose a vehicle</option>
                  {choosable.map((vehicle) => (
                    <option key={vehicle.id} value={vehicle.id}>
                      {vehicle.registration_no} · {vehicle.brand} {vehicle.model} ({vehicle.status})
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              {selected ? (
                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <VehicleStatusBadge status={selected.status} />
                  <span>{selected.home_branch}</span>
                  <span>Odometer {formatKm(selected.odometer)}</span>
                </div>
              ) : null}
              <div className="grid gap-5 sm:grid-cols-2">
                <Field id="report-type" label="Job type" error={errors.job_type?.message}>
                  <NativeSelect
                    id="report-type"
                    defaultValue=""
                    aria-invalid={errors.job_type ? true : undefined}
                    aria-describedby={describedBy('report-type', { error: Boolean(errors.job_type) })}
                    {...register('job_type')}
                  >
                    <option value="" disabled>
                      Choose a type
                    </option>
                    {JOB_TYPES.map((type) => (
                      <option key={type}>{type}</option>
                    ))}
                  </NativeSelect>
                </Field>
                <Field id="report-severity" label="Severity" error={errors.severity?.message}>
                  <NativeSelect
                    id="report-severity"
                    defaultValue=""
                    aria-invalid={errors.severity ? true : undefined}
                    aria-describedby={describedBy('report-severity', { error: Boolean(errors.severity) })}
                    {...register('severity')}
                  >
                    <option value="" disabled>
                      Choose a severity
                    </option>
                    {SEVERITIES.map((severity) => (
                      <option key={severity}>{severity}</option>
                    ))}
                  </NativeSelect>
                </Field>
              </div>
              <Field id="report-problem" label="Problem" error={errors.reported_problem?.message}>
                <Textarea
                  id="report-problem"
                  rows={4}
                  placeholder="For example: brake pedal feels soft; car pulls to the left when braking."
                  aria-invalid={errors.reported_problem ? true : undefined}
                  aria-describedby={describedBy('report-problem', { error: Boolean(errors.reported_problem) })}
                  {...register('reported_problem')}
                />
              </Field>
              <div className="flex items-start gap-3 rounded-md border p-3">
                <input
                  id="report-unsafe"
                  type="checkbox"
                  className="mt-1 size-4 accent-destructive"
                  aria-describedby="report-unsafe-hint"
                  {...register('flag_unsafe')}
                />
                <div>
                  <label htmlFor="report-unsafe" className="text-sm font-medium">
                    Flag the vehicle as Unsafe
                  </label>
                  <p id="report-unsafe-hint" className="text-xs text-muted-foreground">
                    It leaves search, booking and handover at once. Only an Administrator can clear
                    the flag (BR-16).
                  </p>
                </div>
              </div>
              <div>
                <SubmitButton busy={report.isPending} busyLabel="Reporting…">
                  Report fault
                </SubmitButton>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
    </section>
  )
}
