import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, History, Trash2 } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { type Path, useForm } from 'react-hook-form'
import { Link, useLocation, useParams } from 'react-router-dom'

import {
  addDocument,
  addPhoto,
  type AdminVehicleDetail,
  DOCUMENT_TYPES,
  FUEL_TYPES,
  getVehicle,
  listBranches,
  removeDocument,
  removePhoto,
  retireVehicle,
  updateVehicle,
  type VehicleUpdate,
} from '@/api/admin'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { StickyRail } from '@/components/sticky-rail'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { formatDate } from '@/lib/dates'
import { applyServerErrors } from '@/lib/form'
import { FORM, FORM_INDENT, RAIL_LAYOUT } from '@/lib/layout'
import { cn } from '@/lib/utils'

import { capacityLabel, documentAlertText } from './format'
import { BRANCHES_KEY, vehicleKey, VEHICLES_KEY } from './keys'
import { ReasonDialog } from './ReasonDialog'

type EditValues = Record<
  | 'registration_no'
  | 'chassis_number'
  | 'brand'
  | 'model'
  | 'year'
  | 'colour'
  | 'fuel_type'
  | 'fuel_capacity'
  | 'home_branch'
  | 'available_from'
  | 'odometer'
  | 'transmission'
  | 'seating_capacity'
  | 'engine_cc',
  string
>
const NUMBERS = new Set(['year', 'home_branch', 'odometer', 'seating_capacity', 'engine_cc'])

function editDefaults(vehicle: AdminVehicleDetail): EditValues {
  return {
    registration_no: vehicle.registration_no,
    chassis_number: vehicle.chassis_number,
    brand: vehicle.brand,
    model: vehicle.model,
    year: String(vehicle.year),
    colour: vehicle.colour,
    fuel_type: vehicle.fuel_type,
    fuel_capacity: vehicle.fuel_capacity ?? '',
    home_branch: String(vehicle.home_branch),
    available_from: vehicle.available_from,
    odometer: String(vehicle.odometer),
    transmission: vehicle.transmission ?? '',
    seating_capacity: vehicle.seating_capacity === null ? '' : String(vehicle.seating_capacity),
    engine_cc: vehicle.engine_cc === null ? '' : String(vehicle.engine_cc),
  }
}

/** UC 11 "edit": only the changed fields are sent; the status is never edited here. */
function EditCard({ vehicle, onSaved }: { vehicle: AdminVehicleDetail; onSaved: (message: string) => void }) {
  const queryClient = useQueryClient()
  const branches = useQuery({ queryKey: BRANCHES_KEY, queryFn: listBranches })
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, dirtyFields },
  } = useForm<EditValues>({ defaultValues: editDefaults(vehicle) })
  const isCar = vehicle.vehicle_type !== 'Two-Wheeler'
  const fields = Object.keys(editDefaults(vehicle)) as Array<keyof EditValues>

  const save = useMutation({
    mutationFn: (values: EditValues) => {
      const changed: Record<string, string | number> = {}
      for (const name of fields) {
        if (dirtyFields[name]) changed[name] = NUMBERS.has(name) ? Number(values[name]) : values[name].trim()
      }
      return updateVehicle(vehicle.id, changed as VehicleUpdate)
    },
    onSuccess: (next) => {
      queryClient.setQueryData(vehicleKey(vehicle.id), next)
      void queryClient.invalidateQueries({ queryKey: VEHICLES_KEY })
      reset(editDefaults(next))
      onSaved('Vehicle details saved.')
    },
    onError: (error) => setFormError(applyServerErrors(error, setError, fields)),
  })

  const text = (name: Path<EditValues>, label: string, extra: ReactNode = null, type = 'text') => (
    <Field id={`edit-${name}`} label={label} error={errors[name]?.message}>
      {extra ?? <Input id={`edit-${name}`} type={type} aria-invalid={errors[name] ? true : undefined} {...register(name)} />}
    </Field>
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Vehicle details</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form
          noValidate
          className={FORM}
          onSubmit={handleSubmit((values) => {
            setFormError(null)
            save.mutate(values)
          })}
        >
          <FormAlert message={formError} />
          {text('registration_no', 'Registration number')}
          {text('chassis_number', 'Chassis number')}
          <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
            {text('brand', 'Brand')}
            {text('model', 'Model')}
            {text('year', 'Year')}
            {text('colour', 'Colour')}
          </div>
          {text(
            'fuel_type',
            'Fuel type',
            <NativeSelect id="edit-fuel_type" {...register('fuel_type')}>
              {FUEL_TYPES.map((type) => (
                <option key={type}>{type}</option>
              ))}
            </NativeSelect>,
          )}
          {text('fuel_capacity', capacityLabel(vehicle.fuel_type))}
          {isCar ? (
            <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
              {text(
                'transmission',
                'Transmission',
                <NativeSelect id="edit-transmission" {...register('transmission')}>
                  <option>Manual</option>
                  <option>Automatic</option>
                </NativeSelect>,
              )}
              {text('seating_capacity', 'Seating capacity')}
            </div>
          ) : (
            text('engine_cc', 'Engine capacity (cc)')
          )}
          {text(
            'home_branch',
            'Home branch',
            <NativeSelect id="edit-home_branch" {...register('home_branch')}>
              {(branches.data ?? [{ branch_id: vehicle.home_branch, branch_name: vehicle.home_branch_name }]).map((branch) => (
                <option key={branch.branch_id} value={branch.branch_id}>
                  {branch.branch_name}
                </option>
              ))}
            </NativeSelect>,
          )}
          <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
            {text('odometer', 'Odometer (km)')}
            {text('available_from', 'Available from', null, 'date')}
          </div>
          <div className={FORM_INDENT}>
            <SubmitButton busy={save.isPending} busyLabel="Saving…">
              Save changes
            </SubmitButton>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

/** Fleet.Add, SA-3: each statutory document; a renewal is a new row and the latest counts. */
function DocumentsCard({ vehicle, onChanged }: { vehicle: AdminVehicleDetail; onChanged: (message: string) => void }) {
  const [type, setType] = useState<string>(DOCUMENT_TYPES[0])
  const [number, setNumber] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [expiry, setExpiry] = useState('')
  const [scan, setScan] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!expiry) {
      setError('Enter the expiry date.')
      return
    }
    const form = new FormData()
    form.append('document_type', type)
    form.append('document_number', number.trim())
    form.append('expiry_date', expiry)
    if (validFrom) form.append('valid_from', validFrom)
    if (scan) form.append('file', scan)
    setBusy(true)
    setError(null)
    try {
      await addDocument(vehicle.id, form)
      setNumber('')
      setValidFrom('')
      setExpiry('')
      setScan(null)
      onChanged(`${type} recorded.`)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Statutory documents</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6">
        {vehicle.documents.length ? (
          <table className="w-full text-sm">
            <caption className="sr-only">Statutory documents</caption>
            <thead>
              <tr className="border-b text-left text-label text-muted-foreground">
                <th scope="col" className="py-2.5 pr-3 font-normal">Document</th>
                <th scope="col" className="py-2.5 pr-3 font-normal">Number</th>
                <th scope="col" className="py-2.5 pr-3 font-normal">Expires</th>
                <th scope="col" className="py-2.5 pr-3 font-normal">State</th>
                <th scope="col" className="py-2.5 font-normal">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {vehicle.documents.map((document) => (
                <tr key={document.id} className={cn('border-b', !document.current && 'text-muted-foreground')}>
                  <td className="py-2.5 pr-3">
                    {document.document_type}
                    {document.current ? null : ' (history)'}
                    {document.file_url ? (
                      <>
                        {' · '}
                        <a href={document.file_url} target="_blank" rel="noreferrer" className="text-primary underline">
                          Scan
                        </a>
                      </>
                    ) : null}
                  </td>
                  <td className="num py-2.5 pr-3">{document.document_number || '—'}</td>
                  <td className="num py-2.5 pr-3 whitespace-nowrap">{formatDate(document.expiry_date)}</td>
                  <td className={cn('py-2.5 pr-3', document.current && document.state !== 'Valid' && 'font-medium text-status-unsafe')}>
                    {document.state}
                  </td>
                  <td className="py-2.5 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={async () => {
                        await removeDocument(vehicle.id, document.id)
                        onChanged(`${document.document_type} removed.`)
                      }}
                    >
                      <Trash2 aria-hidden="true" />
                      <span className="sr-only">Remove {document.document_type} {document.document_number}</span>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-muted-foreground">No documents are on record.</p>
        )}
        <form noValidate onSubmit={submit} className={cn(FORM, 'border-t pt-5')}>
          <FormAlert message={error} />
          <Field id="document-type" label="Document">
            <NativeSelect id="document-type" value={type} onChange={(event) => setType(event.target.value)}>
              {DOCUMENT_TYPES.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="document-number" label="Document number">
            <Input id="document-number" value={number} onChange={(event) => setNumber(event.target.value)} />
          </Field>
          <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
            <Field id="document-from" label="Valid from">
              <Input id="document-from" type="date" value={validFrom} onChange={(event) => setValidFrom(event.target.value)} />
            </Field>
            <Field id="document-expiry" label="Expires on">
              <Input id="document-expiry" type="date" value={expiry} onChange={(event) => setExpiry(event.target.value)} />
            </Field>
          </div>
          <Field id="document-scan" label="Scan" hint="Optional: a JPG or PNG of the document.">
            <Input id="document-scan" type="file" accept=".jpg,.jpeg,.png" onChange={(event) => setScan(event.target.files?.[0] ?? null)} />
          </Field>
          <div className={FORM_INDENT}>
            <SubmitButton busy={busy} busyLabel="Recording…">
              Record document
            </SubmitButton>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

/** Fleet.Add: at least four photographs stay. */
function PhotosCard({ vehicle, onChanged }: { vehicle: AdminVehicleDetail; onChanged: (message: string) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const act = async (work: () => Promise<unknown>, message: string) => {
    setError(null)
    try {
      await work()
      onChanged(message)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Something went wrong.')
    }
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Photographs</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-5">
        <FormAlert message={error} />
        <ul aria-label="Photographs" className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
          {vehicle.photos.map((photo, index) => (
            <li key={photo.id} className="grid gap-2">
              {photo.url ? (
                <img src={photo.url} alt={`Photograph ${index + 1} of ${vehicle.registration_no}`} className="aspect-[4/3] w-full rounded-md border object-cover" />
              ) : null}
              <Button
                variant="outline"
                size="sm"
                aria-label={`Remove photograph ${index + 1}`}
                onClick={() => void act(() => removePhoto(vehicle.id, photo.id), 'Photograph removed.')}
              >
                <Trash2 aria-hidden="true" />
                Remove
              </Button>
            </li>
          ))}
        </ul>
        <form
          noValidate
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (!file) setError('Choose a photograph.')
            else void act(() => addPhoto(vehicle.id, file), 'Photograph added.').then(() => setFile(null))
          }}
        >
          <Field id="photo-add" label="Add a photograph">
            <Input id="photo-add" type="file" accept=".jpg,.jpeg,.png" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </Field>
          <Button type="submit" variant="outline">
            Upload photograph
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

/** One vehicle (UC 11): edit, documents, photographs, and Fleet.Retire. */
export function VehiclePage() {
  const { id } = useParams()
  const vehicleId = Number(id)
  const location = useLocation()
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string | null>((location.state as { flash?: string } | null)?.flash ?? null)
  const vehicle = useQuery({ queryKey: vehicleKey(vehicleId), queryFn: () => getVehicle(vehicleId) })

  const changed = (note: string) => {
    void queryClient.invalidateQueries({ queryKey: vehicleKey(vehicleId) })
    void queryClient.invalidateQueries({ queryKey: VEHICLES_KEY })
    setMessage(note)
  }

  const back = (
    <Button asChild variant="ghost" className="mb-2 -ml-2 h-10">
      <Link to="/app/fleet">
        <ArrowLeft aria-hidden="true" />
        Back to the fleet
      </Link>
    </Button>
  )
  if (vehicle.isPending || vehicle.isError) {
    return (
      <section>
        {back}
        <PageHeader title="Vehicle" />
        {vehicle.isPending ? (
          <LoadingState label="Loading the vehicle…" />
        ) : (
          <ErrorState title="We couldn’t load this vehicle" error={vehicle.error} onRetry={() => void vehicle.refetch()} />
        )}
      </section>
    )
  }

  const data = vehicle.data
  return (
    <section>
      {back}
      <PageHeader
        title={`${data.registration_no} · ${data.brand} ${data.model}`}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <VehicleStatusBadge status={data.status} />
            {data.category_name}, {data.home_branch_name}
          </span>
        }
      />
      <div className="mb-6">
        <StatusMessage message={message} tone="success" />
      </div>
      <div className={RAIL_LAYOUT}>
        <div className="grid min-w-0 content-start gap-8">
          {data.document_alerts.length ? (
            <div role="status" className="rounded-md border-l-2 border-l-status-unsafe bg-status-unsafe-tint px-4 py-3 text-sm">
              <p className="font-medium">Handover is refused until these are valid (SA-3)</p>
              <p className="mt-1 text-muted-foreground">{data.document_alerts.map(documentAlertText).join('; ')}.</p>
            </div>
          ) : null}
          <EditCard key={data.id} vehicle={data} onSaved={setMessage} />
          <DocumentsCard vehicle={data} onChanged={changed} />
          <PhotosCard vehicle={data} onChanged={changed} />
        </div>
        <StickyRail>
          <div className="grid gap-4 lg:pt-1">
            <Button asChild variant="outline">
              <Link to={`/app/maintenance/vehicles/${data.id}/history`}>
                <History aria-hidden="true" />
                Maintenance history
              </Link>
            </Button>
            {data.status === 'Retired' ? (
              <p className="text-sm text-muted-foreground">
                Retired: it is never offered again, and its rental, payment and maintenance history is kept.
              </p>
            ) : (
              <ReasonDialog
                id="retire"
                trigger="Retire vehicle"
                variant="destructive"
                title={`Retire ${data.registration_no}?`}
                description="A retired vehicle is never offered or booked again; its history is kept. A vehicle with a booking that is not over cannot be retired (Fleet.Retire)."
                submitLabel="Retire vehicle"
                busyLabel="Retiring…"
                cancelLabel="Keep it"
                onConfirm={async (reason) => {
                  const next = await retireVehicle(data.id, reason)
                  queryClient.setQueryData(vehicleKey(data.id), next)
                  void queryClient.invalidateQueries({ queryKey: VEHICLES_KEY })
                  setMessage(`${data.registration_no} is retired.`)
                }}
              />
            )}
          </div>
        </StickyRail>
      </div>
    </section>
  )
}
