import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ShieldAlert } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import {
  approveClearance,
  cancelJob,
  completeJob,
  getJob,
  type MaintenanceJob,
  startJob,
} from '@/api/maintenance'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { useSignedInUser } from '@/features/auth/auth-context'
import { formatINR } from '@/lib/currency'
import { formatDate, formatDateTime } from '@/lib/dates'
import { describedBy } from '@/lib/form'

import { JobStatusBadge, SeverityBadge } from './badges'
import { formatKm } from './format'
import { CLEARANCES_KEY, jobKey, JOBS_KEY, VEHICLES_KEY } from './keys'
import { RecordWorkForm } from './RecordWorkForm'
import { ScheduleCard } from './ScheduleCard'
import { type CancelValues, cancelSchema } from './schemas'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium break-words">{children}</dd>
    </>
  )
}

function DetailsCard({ job }: { job: MaintenanceJob }) {
  const vehicle = job.vehicle
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Job and vehicle</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-2 text-sm sm:grid-cols-[11rem_1fr]">
          <Row label="Vehicle">
            {vehicle.registration_no} · {vehicle.brand} {vehicle.model} ({vehicle.category})
          </Row>
          <Row label="Vehicle status">
            <VehicleStatusBadge status={vehicle.status} />
          </Row>
          <Row label="Branch">{vehicle.home_branch}</Row>
          <Row label="Odometer">{formatKm(vehicle.odometer)}</Row>
          <Row label="Job type">{job.job_type}</Row>
          <Row label="Severity">
            <SeverityBadge severity={job.severity} />
          </Row>
          <Row label="Problem">{job.reported_problem}</Row>
          <Row label="Reported">
            {job.reported_by}, {formatDateTime(job.created_at)}
          </Row>
          <Row label="Technician">
            {job.technician ? `${job.technician.name} (${job.technician.workshop})` : 'Not assigned'}
          </Row>
          <Row label="Scheduled">
            {job.scheduled_from
              ? `${formatDateTime(job.scheduled_from)} to ${formatDateTime(job.scheduled_to)}`
              : 'Not scheduled'}
          </Row>
          {job.started_at ? <Row label="Started">{formatDateTime(job.started_at)}</Row> : null}
          {job.closed_at ? (
            <Row label={job.status === 'Completed' ? 'Closed by' : 'Closed'}>
              {job.closed_by ?? '—'}, {formatDateTime(job.closed_at)}
            </Row>
          ) : null}
          <Row label="Last service">
            {formatDate(vehicle.last_service_date)} at {formatKm(vehicle.last_service_odometer)}
          </Row>
          <Row label="Next service due (BR-15)">
            {vehicle.next_service_due.date || vehicle.next_service_due.odometer !== null
              ? `${formatDate(vehicle.next_service_due.date)} or ${formatKm(vehicle.next_service_due.odometer)}, whichever comes first`
              : 'Not known until a service is recorded'}
          </Row>
        </dl>
      </CardContent>
    </Card>
  )
}

/** The recorded work (Maint.Record), as the Administrator reviews it. */
function WorkRecordCard({ job }: { job: MaintenanceJob }) {
  if (job.service_date === null) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Work recorded</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        <dl className="grid gap-2 text-sm sm:grid-cols-[11rem_1fr]">
          <Row label="Service date">{formatDate(job.service_date)}</Row>
          <Row label="Odometer at service">{formatKm(job.odometer_at_service)}</Row>
          <Row label="Work performed">{job.work_description}</Row>
          <Row label="Downtime">{job.downtime_hours ? `${job.downtime_hours} hours` : '—'}</Row>
          <Row label="Labour">{formatINR(job.labour_cost)}</Row>
        </dl>
        {job.parts.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Parts used</caption>
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th scope="col" className="py-2 pr-2 font-normal">Part</th>
                  <th scope="col" className="py-2 pr-2 text-right font-normal">Qty</th>
                  <th scope="col" className="py-2 pr-2 text-right font-normal">Unit cost</th>
                  <th scope="col" className="py-2 text-right font-normal">Amount</th>
                </tr>
              </thead>
              <tbody>
                {job.parts.map((part) => (
                  <tr key={part.id} className="border-b">
                    <td className="py-2 pr-2">{part.part_name}</td>
                    <td className="py-2 pr-2 text-right">{part.quantity}</td>
                    <td className="py-2 pr-2 text-right">{formatINR(part.unit_cost)}</td>
                    <td className="py-2 text-right">{formatINR(part.total_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No parts were replaced.</p>
        )}
        <p className="flex justify-between border-t pt-3 font-medium">
          <span>Total cost</span>
          <span>{formatINR(job.total_cost)}</span>
        </p>
      </CardContent>
    </Card>
  )
}

function CancelDialog({ job, onCancelled }: { job: MaintenanceJob; onCancelled: (job: MaintenanceJob) => void }) {
  const [open, setOpen] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CancelValues>({ resolver: zodResolver(cancelSchema) })

  const onSubmit = handleSubmit(async ({ reason }) => {
    setFormError(null)
    try {
      onCancelled(await cancelJob(job.job_id, reason))
      setOpen(false)
      reset()
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Something went wrong.')
    }
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="lg" className="h-10">
          Cancel job
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancel job {job.job_id}?</DialogTitle>
          <DialogDescription>
            A cancelled job cannot be reopened. An Unsafe flag stays until an Administrator clears it.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} noValidate className="grid gap-4">
          <FormAlert message={formError} />
          <Field id="cancel-reason" label="Reason" error={errors.reason?.message}>
            <Textarea
              id="cancel-reason"
              rows={3}
              aria-invalid={errors.reason ? true : undefined}
              aria-describedby={describedBy('cancel-reason', { error: Boolean(errors.reason) })}
              {...register('reason')}
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" size="lg" className="h-10" onClick={() => setOpen(false)}>
              Keep the job
            </Button>
            <SubmitButton busy={isSubmitting} busyLabel="Cancelling…">
              Cancel job
            </SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ApproveDialog({ job, onApprove, busy }: { job: MaintenanceJob; onApprove: () => void; busy: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="lg" className="h-10">
          Clear Unsafe flag and complete
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Clear the Unsafe flag on {job.vehicle.registration_no}?</DialogTitle>
          <DialogDescription>
            The vehicle becomes Available for rental again, job {job.job_id} is completed, and you
            are recorded as the approver (BR-16).
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" size="lg" className="h-10" onClick={() => setOpen(false)}>
            Not yet
          </Button>
          <Button
            size="lg"
            className="h-10"
            disabled={busy}
            aria-busy={busy}
            onClick={() => {
              setOpen(false)
              onApprove()
            }}
          >
            Approve clearance
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** One job, with the actions the signed-in role may take at its current status. */
export function JobDetailPage() {
  const user = useSignedInUser()
  const { id } = useParams()
  const jobId = Number(id)
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string | null>(
    (location.state as { flash?: string } | null)?.flash ?? null,
  )
  const [actionError, setActionError] = useState<string | null>(null)
  const job = useQuery({ queryKey: jobKey(jobId), queryFn: () => getJob(jobId) })

  const isTechnician = user.role === 'MAINTENANCE_TECHNICIAN'
  const isAdmin = user.role === 'ADMINISTRATOR'
  const isManager = ['BRANCH_STAFF', 'BRANCH_MANAGER', 'ADMINISTRATOR'].includes(user.role)

  const update = (next: MaintenanceJob, note: string | null) => {
    queryClient.setQueryData(jobKey(jobId), next)
    void queryClient.invalidateQueries({ queryKey: JOBS_KEY })
    void queryClient.invalidateQueries({ queryKey: CLEARANCES_KEY })
    void queryClient.invalidateQueries({ queryKey: VEHICLES_KEY })
    setActionError(null)
    setMessage(note)
  }
  const fail = (error: unknown) => {
    setMessage(null)
    setActionError(error instanceof Error ? error.message : 'Something went wrong.')
  }

  const start = useMutation({
    mutationFn: () => startJob(jobId),
    onSuccess: (next) => update(next, 'Job started. Record the work when it is done.'),
    onError: fail,
  })
  const complete = useMutation({
    mutationFn: () => completeJob(jobId),
    onSuccess: (next) =>
      update(
        next,
        next.awaiting_clearance
          ? 'Work complete. The vehicle is flagged Unsafe, so an Administrator must clear it before the job closes.'
          : `Job completed. ${next.vehicle.registration_no} is ${next.vehicle.status}.`,
      ),
    onError: fail,
  })
  const approve = useMutation({
    mutationFn: () => approveClearance(jobId),
    onSuccess: (next) => {
      update(next, null)
      navigate('/app/clearances', {
        state: {
          flash: `Unsafe flag cleared. Job ${next.job_id} is completed and ${next.vehicle.registration_no} is ${next.vehicle.status}.`,
        },
      })
    },
    onError: fail,
  })

  const backTo = isTechnician ? '/app/jobs' : '/app/maintenance'
  const back = (
    <Button asChild variant="ghost" size="lg" className="mb-2 -ml-2 h-10">
      <Link to={backTo}>
        <ArrowLeft aria-hidden="true" />
        {isTechnician ? 'Back to my jobs' : 'Back to maintenance'}
      </Link>
    </Button>
  )

  if (job.isPending || job.isError) {
    return (
      <section>
        {back}
        <PageHeader title={`Job ${id}`} />
        {job.isPending ? (
          <LoadingState label="Loading the job…" />
        ) : (
          <ErrorState title="We couldn’t load this job" error={job.error} onRetry={() => void job.refetch()} />
        )}
      </section>
    )
  }

  const data = job.data
  const inProgress = data.status === 'In Progress' && !data.awaiting_clearance

  return (
    <section>
      {back}
      <PageHeader
        title={`Job ${data.job_id} · ${data.vehicle.registration_no}`}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <JobStatusBadge job={data} />
            <VehicleStatusBadge status={data.vehicle.status} />
          </span>
        }
      />
      <div className="grid gap-6">
        <StatusMessage message={message} tone="success" />
        <FormAlert message={actionError} />

        {data.awaiting_clearance ? (
          <div role="status" className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4">
            <ShieldAlert className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">Awaiting administrator clearance</p>
              <p className="mt-1 text-sm text-muted-foreground">
                The work is recorded and complete. {data.vehicle.registration_no} is flagged Unsafe, so
                an Administrator must review the work and clear the flag before the job closes and the
                vehicle can be rented (BR-16). Requested {formatDateTime(data.clearance_requested_at)}.
              </p>
            </div>
          </div>
        ) : null}

        {isTechnician && data.status === 'Scheduled' ? (
          <div>
            <Button size="lg" className="h-10" onClick={() => start.mutate()} disabled={start.isPending} aria-busy={start.isPending}>
              {start.isPending ? 'Starting…' : 'Start job'}
            </Button>
          </div>
        ) : null}

        {isManager && data.status === 'Reported' ? (
          <ScheduleCard job={data} onScheduled={(next) => update(next, `Job scheduled and assigned to ${next.technician?.name}. They have been e-mailed.`)} />
        ) : null}

        <DetailsCard job={data} />

        {isTechnician && inProgress ? (
          <RecordWorkForm
            key={`${data.job_id}-${data.service_date ?? 'new'}`}
            job={data}
            onSaved={(next) => update(next, `Work recorded. Total cost ${formatINR(next.total_cost)}.`)}
          />
        ) : null}

        <WorkRecordCard job={data} />

        {isTechnician && inProgress ? (
          <Card>
            <CardHeader>
              <CardTitle>
                <h2>Complete the job</h2>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              {data.missing_work.length ? (
                <p className="text-sm text-muted-foreground">
                  Still to record: {data.missing_work.join(', ')}.
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  The work record is complete. Completing releases the vehicle, or asks an
                  Administrator to clear it if it is flagged Unsafe.
                </p>
              )}
              <div>
                <Button size="lg" className="h-10" onClick={() => complete.mutate()} disabled={complete.isPending} aria-busy={complete.isPending}>
                  {complete.isPending ? 'Completing…' : 'Complete job'}
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {isAdmin && data.awaiting_clearance ? (
          <div className="flex flex-col gap-2 sm:flex-row">
            <ApproveDialog job={data} busy={approve.isPending} onApprove={() => approve.mutate()} />
          </div>
        ) : null}

        {isManager && (data.status === 'Reported' || data.status === 'Scheduled') ? (
          <div>
            <CancelDialog job={data} onCancelled={(next) => update(next, `Job ${next.job_id} cancelled.`)} />
          </div>
        ) : null}
      </div>
    </section>
  )
}
