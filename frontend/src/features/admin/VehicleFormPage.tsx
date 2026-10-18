import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { type Path, useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'

import { createVehicle, DOCUMENT_TYPES, FUEL_TYPES, listBranches, listCategories } from '@/api/admin'
import { Field, FormAlert, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { todayISO } from '@/lib/dates'
import { applyServerErrors, describedBy } from '@/lib/form'
import { FORM, FORM_INDENT } from '@/lib/layout'
import { cn } from '@/lib/utils'

import { capacityLabel } from './format'
import { BRANCHES_KEY, CATEGORIES_KEY, VEHICLES_KEY } from './keys'
import { DOCUMENT_FIELDS, type VehicleValues, vehicleSchema } from './schemas'

/** At least four photographs (Fleet.Add). */
const MIN_PHOTOS = 4

const SERVER_FIELDS = [
  'registration_no',
  'category',
  'brand',
  'model',
  'year',
  'colour',
  'fuel_type',
  'transmission',
  'seating_capacity',
  'engine_cc',
  'chassis_number',
  'home_branch',
  'odometer',
  'fuel_capacity',
  'available_from',
] as const

/** Fleet.Add (UC 11 step 1, extension 1a): an Administrator adds a vehicle. */
export function VehicleFormPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const categories = useQuery({ queryKey: CATEGORIES_KEY, queryFn: listCategories })
  const branches = useQuery({ queryKey: BRANCHES_KEY, queryFn: listBranches })
  const [photos, setPhotos] = useState<File[]>([])
  const [photoError, setPhotoError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors },
  } = useForm<VehicleValues>({
    resolver: zodResolver(vehicleSchema),
    defaultValues: {
      category: '',
      home_branch: '',
      transmission: 'Manual',
      seating_capacity: '5',
      engine_cc: '',
      odometer: '',
      available_from: todayISO(),
    },
  })
  const categoryId = useWatch({ control, name: 'category' })
  const fuel = useWatch({ control, name: 'fuel_type' }) ?? ''
  const isCar = categories.data?.find((c) => String(c.id) === categoryId)?.vehicle_type !== 'Two-Wheeler'

  const save = useMutation({
    mutationFn: (values: VehicleValues) => {
      const form = new FormData()
      for (const name of SERVER_FIELDS) {
        const value = values[name]
        if (isCar ? name !== 'engine_cc' : name !== 'transmission' && name !== 'seating_capacity') {
          if (value !== '') form.append(name, value)
        }
      }
      for (const photo of photos) form.append('photos', photo)
      form.append(
        'documents',
        JSON.stringify(DOCUMENT_TYPES.map((type) => ({ document_type: type, expiry_date: values[DOCUMENT_FIELDS[type]] }))),
      )
      return createVehicle(form)
    },
    onSuccess: async (vehicle) => {
      await queryClient.invalidateQueries({ queryKey: VEHICLES_KEY })
      navigate(`/app/fleet/${vehicle.id}`, { state: { flash: `${vehicle.registration_no} added to the fleet.` } })
    },
    onError: (error) => setFormError(applyServerErrors(error, setError, SERVER_FIELDS)),
  })

  const onSubmit = handleSubmit((values) => {
    setFormError(null)
    if (photos.length < MIN_PHOTOS) {
      setPhotoError(`Add at least ${MIN_PHOTOS} photographs.`)
      return
    }
    setPhotoError(null)
    save.mutate(values)
  })

  const field = (name: Path<VehicleValues>, id: string, label: ReactNode, input: ReactNode, hint?: ReactNode) => (
    <Field id={id} label={label} hint={hint} error={errors[name]?.message}>
      {input}
    </Field>
  )
  const inputProps = (name: Path<VehicleValues>, id: string, hint = false) => ({
    id,
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': describedBy(id, { hint, error: Boolean(errors[name]) }),
    ...register(name),
  })

  return (
    <section>
      <Button asChild variant="ghost" className="mb-2 -ml-2 h-10">
        <Link to="/app/fleet">
          <ArrowLeft aria-hidden="true" />
          Back to the fleet
        </Link>
      </Button>
      <PageHeader
        title="Add a vehicle"
        photo="step-search-1"
        variant="compact"
        description="The vehicle is bookable from its availability date. A registration or chassis number already on record is refused."
      />
      {categories.isPending || branches.isPending ? (
        <LoadingState label="Loading categories and branches…" />
      ) : categories.isError || branches.isError ? (
        <ErrorState
          title="We couldn’t load the form"
          error={categories.error ?? branches.error}
          onRetry={() => {
            void categories.refetch()
            void branches.refetch()
          }}
        />
      ) : (
        <form onSubmit={onSubmit} noValidate className={cn(FORM, 'max-w-4xl')}>
          <FormAlert message={formError} />
          {field('registration_no', 'vehicle-registration', 'Registration number', <Input {...inputProps('registration_no', 'vehicle-registration')} />)}
          {field('chassis_number', 'vehicle-chassis', 'Chassis number', <Input {...inputProps('chassis_number', 'vehicle-chassis')} />)}
          {field(
            'category',
            'vehicle-category',
            'Category',
            <NativeSelect {...inputProps('category', 'vehicle-category')}>
              <option value="">Choose a category</option>
              {categories.data.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name} ({category.vehicle_type})
                </option>
              ))}
            </NativeSelect>,
          )}
          <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
            {field('brand', 'vehicle-brand', 'Brand', <Input {...inputProps('brand', 'vehicle-brand')} />)}
            {field('model', 'vehicle-model', 'Model', <Input {...inputProps('model', 'vehicle-model')} />)}
            {field('year', 'vehicle-year', 'Year', <Input inputMode="numeric" {...inputProps('year', 'vehicle-year')} />)}
            {field('colour', 'vehicle-colour', 'Colour', <Input {...inputProps('colour', 'vehicle-colour')} />)}
          </div>
          {field(
            'fuel_type',
            'vehicle-fuel',
            'Fuel type',
            <NativeSelect defaultValue="" {...inputProps('fuel_type', 'vehicle-fuel')}>
              <option value="" disabled>
                Choose a fuel type
              </option>
              {FUEL_TYPES.map((type) => (
                <option key={type}>{type}</option>
              ))}
            </NativeSelect>,
          )}
          {field(
            'fuel_capacity',
            'vehicle-capacity',
            capacityLabel(fuel),
            <Input inputMode="decimal" {...inputProps('fuel_capacity', 'vehicle-capacity', true)} />,
            'Needed to charge a fuel or charge shortfall at return (BR-12).',
          )}
          {isCar ? (
            <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
              {field(
                'transmission',
                'vehicle-transmission',
                'Transmission',
                <NativeSelect {...inputProps('transmission', 'vehicle-transmission')}>
                  <option>Manual</option>
                  <option>Automatic</option>
                </NativeSelect>,
              )}
              {field(
                'seating_capacity',
                'vehicle-seats',
                'Seating capacity',
                <Input inputMode="numeric" {...inputProps('seating_capacity', 'vehicle-seats')} />,
              )}
            </div>
          ) : (
            field('engine_cc', 'vehicle-engine', 'Engine capacity (cc)', <Input inputMode="numeric" {...inputProps('engine_cc', 'vehicle-engine')} />)
          )}
          {field(
            'home_branch',
            'vehicle-branch',
            'Home branch',
            <NativeSelect {...inputProps('home_branch', 'vehicle-branch')}>
              <option value="">Choose a branch</option>
              {branches.data.map((branch) => (
                <option key={branch.branch_id} value={branch.branch_id}>
                  {branch.branch_name}
                </option>
              ))}
            </NativeSelect>,
          )}
          <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
            {field('odometer', 'vehicle-odometer', 'Odometer (km)', <Input inputMode="numeric" {...inputProps('odometer', 'vehicle-odometer')} />)}
            {field('available_from', 'vehicle-available', 'Available from', <Input type="date" {...inputProps('available_from', 'vehicle-available')} />)}
          </div>

          <fieldset className={cn('grid gap-4 border-t pt-5', FORM_INDENT)}>
            <legend className="mb-1 text-sm font-medium">Statutory documents (SA-3)</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              {DOCUMENT_TYPES.map((type) => {
                const name = DOCUMENT_FIELDS[type]
                const id = `vehicle-${name}`
                return (
                  <div key={type} className="grid gap-1.5">
                    <label htmlFor={id} className="text-sm font-medium">
                      {type} expires on
                    </label>
                    <Input id={id} type="date" aria-invalid={errors[name] ? true : undefined} {...register(name)} />
                    {errors[name] ? <p className="text-small font-medium text-destructive">{errors[name]?.message}</p> : null}
                  </div>
                )
              })}
            </div>
          </fieldset>

          <Field
            id="vehicle-photos"
            label="Photographs"
            hint={`At least ${MIN_PHOTOS}, JPG or PNG, at most 5 MB each. ${photos.length} chosen.`}
            error={photoError ?? errors.root?.message}
          >
            <Input
              id="vehicle-photos"
              type="file"
              multiple
              accept=".jpg,.jpeg,.png"
              aria-invalid={photoError ? true : undefined}
              aria-describedby={describedBy('vehicle-photos', { hint: true, error: Boolean(photoError) })}
              onChange={(event) => setPhotos(Array.from(event.target.files ?? []))}
            />
          </Field>
          <div className={FORM_INDENT}>
            <SubmitButton busy={save.isPending} busyLabel="Adding…">
              Add vehicle
            </SubmitButton>
          </div>
        </form>
      )}
    </section>
  )
}
