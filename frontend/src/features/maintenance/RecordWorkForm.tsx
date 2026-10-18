import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'

import { attachInvoice, type MaintenanceJob, recordWork } from '@/api/maintenance'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { todayISO } from '@/lib/dates'
import { applyServerErrors, describedBy } from '@/lib/form'
import { FORM, FORM_INDENT } from '@/lib/layout'
import { cn } from '@/lib/utils'

import { type RecordValues, recordSchema } from './schemas'

const FIELDS = [
  'service_date',
  'odometer_at_service',
  'work_description',
  'labour_cost',
  'downtime_hours',
] as const

/** Drop trailing zeros the server adds ("1.00" -> "1"), for friendlier editing. */
const plain = (value: string) => value.replace(/\.00$/, '')

function defaults(job: MaintenanceJob): RecordValues {
  const recorded = job.service_date !== null
  return {
    service_date: job.service_date ?? todayISO(),
    // Empty until recorded: the hint gives the last reading, so typing never appends to it.
    odometer_at_service: job.odometer_at_service === null ? '' : String(job.odometer_at_service),
    work_description: job.work_description,
    labour_cost: recorded ? plain(job.labour_cost) : '',
    downtime_hours: job.downtime_hours ? plain(job.downtime_hours) : '',
    parts: job.parts.map((part) => ({
      part_name: part.part_name,
      quantity: plain(part.quantity),
      unit_cost: plain(part.unit_cost),
    })),
  }
}

/** Maint.Record: the work, each part with quantity and cost, labour and downtime. */
export function RecordWorkForm({
  job,
  onSaved,
}: {
  job: MaintenanceJob
  onSaved: (job: MaintenanceJob) => void
}) {
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<RecordValues>({ resolver: zodResolver(recordSchema), defaultValues: defaults(job) })
  const parts = useFieldArray({ control, name: 'parts' })

  const save = useMutation({
    mutationFn: (values: RecordValues) =>
      recordWork(job.job_id, { ...values, odometer_at_service: Number(values.odometer_at_service) }),
    onSuccess: onSaved,
    onError: (error) => setFormError(applyServerErrors(error, setError, FIELDS)),
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(null)
    save.mutate(values)
  })

  const invalid = (name: keyof typeof errors, id: string) => ({
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': describedBy(id, { error: Boolean(errors[name]) }),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Record the work</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className={FORM}>
          <FormAlert message={formError} />
          <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
            <Field id="record-date" label="Service date" error={errors.service_date?.message}>
              <Input id="record-date" type="date" max={todayISO()} {...invalid('service_date', 'record-date')} {...register('service_date')} />
            </Field>
            <Field
              id="record-odometer"
              label="Odometer at service (km)"
              hint={`The vehicle last read ${job.vehicle.odometer} km; the reading cannot be lower.`}
              error={errors.odometer_at_service?.message}
            >
              <Input
                id="record-odometer"
                inputMode="numeric"
                aria-invalid={errors.odometer_at_service ? true : undefined}
                aria-describedby={describedBy('record-odometer', { hint: true, error: Boolean(errors.odometer_at_service) })}
                {...register('odometer_at_service')}
              />
            </Field>
          </div>
          <Field id="record-work" label="Work performed" error={errors.work_description?.message}>
            <Textarea id="record-work" rows={4} {...invalid('work_description', 'record-work')} {...register('work_description')} />
          </Field>
          <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
            <Field id="record-labour" label="Labour cost (₹)" error={errors.labour_cost?.message}>
              <Input id="record-labour" inputMode="decimal" {...invalid('labour_cost', 'record-labour')} {...register('labour_cost')} />
            </Field>
            <Field id="record-downtime" label="Downtime (hours)" error={errors.downtime_hours?.message}>
              <Input id="record-downtime" inputMode="decimal" {...invalid('downtime_hours', 'record-downtime')} {...register('downtime_hours')} />
            </Field>
          </div>

          <fieldset className={cn('grid gap-3', FORM_INDENT)}>
            <legend className="mb-1 text-sm font-medium">Parts used</legend>
            {parts.fields.length === 0 ? (
              <p className="text-sm text-muted-foreground">No parts added. Add each part replaced, if any.</p>
            ) : null}
            {parts.fields.map((field, index) => {
              const partErrors = errors.parts?.[index]
              return (
                <div key={field.id} className="@container/form grid gap-3 border-t pt-4 @lg/form:grid-cols-[minmax(0,1fr)_6rem_8rem_auto] @lg/form:items-end">
                  <Field id={`part-${index}-name`} label={`Part ${index + 1}`} error={partErrors?.part_name?.message}>
                    <Input id={`part-${index}-name`} aria-invalid={partErrors?.part_name ? true : undefined} {...register(`parts.${index}.part_name`)} />
                  </Field>
                  <Field id={`part-${index}-qty`} label="Quantity" error={partErrors?.quantity?.message}>
                    <Input id={`part-${index}-qty`} inputMode="decimal" aria-invalid={partErrors?.quantity ? true : undefined} {...register(`parts.${index}.quantity`)} />
                  </Field>
                  <Field id={`part-${index}-cost`} label="Unit cost (₹)" error={partErrors?.unit_cost?.message}>
                    <Input id={`part-${index}-cost`} inputMode="decimal" aria-invalid={partErrors?.unit_cost ? true : undefined} {...register(`parts.${index}.unit_cost`)} />
                  </Field>
                  <Button type="button" variant="outline" onClick={() => parts.remove(index)}>
                    <Trash2 aria-hidden="true" />
                    <span className="sr-only sm:not-sr-only">Remove</span>
                    <span className="sr-only"> part {index + 1}</span>
                  </Button>
                </div>
              )
            })}
            <div>
              <Button
                type="button"
                variant="outline"
               
               
                onClick={() => parts.append({ part_name: '', quantity: '1', unit_cost: '' })}
              >
                <Plus aria-hidden="true" />
                Add a part
              </Button>
            </div>
          </fieldset>

          <p className={cn('text-sm text-muted-foreground', FORM_INDENT)}>
            The total cost (labour plus parts) is worked out when you save.
          </p>
          <div className={FORM_INDENT}>
            <SubmitButton busy={save.isPending} busyLabel="Saving…">
              Save work record
            </SubmitButton>
          </div>
        </form>
        <InvoiceUpload job={job} onSaved={onSaved} />
      </CardContent>
    </Card>
  )
}

/** Maint.Record "permit the workshop invoice to be attached" (UC 9 step 3). */
function InvoiceUpload({ job, onSaved }: { job: MaintenanceJob; onSaved: (job: MaintenanceJob) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const upload = useMutation({
    mutationFn: (chosen: File) => attachInvoice(job.job_id, chosen),
    onSuccess: (next) => {
      setFile(null)
      setError(null)
      onSaved(next)
    },
    onError: (failure) => setError(failure instanceof Error ? failure.message : 'Something went wrong.'),
  })
  return (
    <form
      noValidate
      className={cn(FORM, 'mt-8 border-t pt-6')}
      onSubmit={(event) => {
        event.preventDefault()
        if (!file) setError('Choose the invoice file.')
        else upload.mutate(file)
      }}
    >
      <Field
        id="record-invoice"
        label="Workshop invoice"
        hint="A PDF, JPG or PNG of at most 5 MB. A new file replaces the one attached."
        error={error ?? undefined}
      >
        <Input
          id="record-invoice"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy('record-invoice', { hint: true, error: Boolean(error) })}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </Field>
      {job.workshop_invoice_url ? (
        <div className={FORM_INDENT}>
          <StatusMessage
            message={
              <>
                An invoice is attached.{' '}
                <a href={job.workshop_invoice_url} target="_blank" rel="noreferrer" className="font-medium text-primary underline">
                  Open the invoice
                </a>
              </>
            }
          />
        </div>
      ) : null}
      <div className={FORM_INDENT}>
        <SubmitButton busy={upload.isPending} busyLabel="Attaching…">
          Attach invoice
        </SubmitButton>
      </div>
    </form>
  )
}
