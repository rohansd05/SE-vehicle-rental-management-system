import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { ApiError } from '@/api/client'
import {
  listTechnicians,
  type MaintenanceJob,
  type ScheduleConflict,
  scheduleJob,
} from '@/api/maintenance'
import { Field, FormAlert, SubmitButton } from '@/components/form'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { formatDateTime } from '@/lib/dates'
import { applyServerErrors, describedBy } from '@/lib/form'

import { NativeSelect } from './JobList'
import { TECHNICIANS_KEY } from './keys'
import { localToISO, type ScheduleValues, scheduleSchema } from './schemas'

const FIELDS = ['technician', 'scheduled_from', 'scheduled_to'] as const

/** Maint.Schedule and Maint.Conflict: assign a technician and a period. */
export function ScheduleCard({
  job,
  onScheduled,
}: {
  job: MaintenanceJob
  onScheduled: (job: MaintenanceJob) => void
}) {
  const technicians = useQuery({ queryKey: TECHNICIANS_KEY, queryFn: listTechnicians })
  const [formError, setFormError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<ScheduleConflict | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    getValues,
    formState: { errors },
  } = useForm<ScheduleValues>({
    resolver: zodResolver(scheduleSchema),
    defaultValues: { technician: '', scheduled_from: '', scheduled_to: '' },
  })

  const schedule = useMutation({
    mutationFn: ({ values, confirm }: { values: ScheduleValues; confirm: boolean }) =>
      scheduleJob(job.job_id, {
        technician: Number(values.technician),
        scheduled_from: localToISO(values.scheduled_from),
        scheduled_to: localToISO(values.scheduled_to),
        confirm_conflicts: confirm,
      }),
    onSuccess: (scheduled) => {
      setConflict(null)
      onScheduled(scheduled)
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'schedule_conflict') {
        setConflict(error.body as ScheduleConflict)
        return
      }
      setFormError(applyServerErrors(error, setError, FIELDS))
    },
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(null)
    setConflict(null)
    schedule.mutate({ values, confirm: false })
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Assign and schedule</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {technicians.isPending ? (
          <LoadingState label="Loading technicians…" />
        ) : technicians.isError ? (
          <ErrorState title="We couldn’t load the technicians" error={technicians.error} onRetry={() => void technicians.refetch()} />
        ) : (
          <form onSubmit={onSubmit} noValidate className="grid gap-4">
            <FormAlert message={formError} />
            <Field id="schedule-technician" label="Technician" error={errors.technician?.message}>
              <NativeSelect
                id="schedule-technician"
                aria-invalid={errors.technician ? true : undefined}
                aria-describedby={describedBy('schedule-technician', { error: Boolean(errors.technician) })}
                {...register('technician')}
              >
                <option value="">Choose a technician</option>
                {technicians.data.map((technician) => (
                  <option key={technician.technician_id} value={technician.technician_id}>
                    {technician.name} ({technician.workshop})
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="schedule-from" label="Starts" error={errors.scheduled_from?.message}>
                <Input
                  id="schedule-from"
                  type="datetime-local"
                  aria-invalid={errors.scheduled_from ? true : undefined}
                  aria-describedby={describedBy('schedule-from', { error: Boolean(errors.scheduled_from) })}
                  {...register('scheduled_from')}
                />
              </Field>
              <Field id="schedule-to" label="Ends" error={errors.scheduled_to?.message}>
                <Input
                  id="schedule-to"
                  type="datetime-local"
                  aria-invalid={errors.scheduled_to ? true : undefined}
                  aria-describedby={describedBy('schedule-to', { error: Boolean(errors.scheduled_to) })}
                  {...register('scheduled_to')}
                />
              </Field>
            </div>
            {conflict ? (
              <div role="alert" className="grid gap-3 rounded-md border-l-2 border-l-status-maintenance bg-status-maintenance-tint p-3 text-sm">
                <p className="font-medium">{conflict.detail}</p>
                <ul className="grid gap-1">
                  {conflict.bookings.map((booking) => (
                    <li key={booking.booking_reference}>
                      {booking.booking_reference}: {formatDateTime(booking.pickup_datetime)} to{' '}
                      {formatDateTime(booking.return_datetime)}
                    </li>
                  ))}
                </ul>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Button
                    type="button"
                    size="lg"
                    className="h-10"
                    disabled={schedule.isPending}
                    onClick={() => schedule.mutate({ values: getValues(), confirm: true })}
                  >
                    Schedule anyway
                  </Button>
                  <Button type="button" variant="outline" size="lg" className="h-10" onClick={() => setConflict(null)}>
                    Choose another period
                  </Button>
                </div>
              </div>
            ) : null}
            <div>
              <SubmitButton busy={schedule.isPending} busyLabel="Scheduling…">
                Schedule job
              </SubmitButton>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
