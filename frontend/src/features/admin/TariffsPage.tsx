import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useForm } from 'react-hook-form'

import {
  type AdminAddOn,
  type AdminDiscountCode,
  type AdminTariff,
  defineTariff,
  type DiscountType,
  listAddOns,
  listCategories,
  listDiscountCodes,
  listTariffs,
  saveAddOn,
  saveDiscountCode,
  withdrawTariff,
} from '@/api/admin'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { localToISO } from '@/features/maintenance/schemas'
import { formatINR } from '@/lib/currency'
import { formatDateTime } from '@/lib/dates'
import { applyServerErrors, describedBy } from '@/lib/form'
import { FORM, FORM_INDENT } from '@/lib/layout'
import { cn } from '@/lib/utils'

import { ADD_ONS_KEY, CATEGORIES_KEY, DISCOUNTS_KEY, TARIFFS_KEY } from './keys'
import { type TariffValues, tariffSchema } from './schemas'

const message = (error: unknown) => (error instanceof Error ? error.message : 'Something went wrong.')
const TARIFF_FIELDS = [
  'vehicle_category',
  'hourly_rate',
  'daily_rate',
  'weekly_rate',
  'free_km_allowance',
  'excess_km_rate',
  'effective_from',
] as const

const STATE_TONE: Record<string, string> = {
  'In force': 'font-medium text-status-available',
  Scheduled: 'font-medium text-status-booked',
  Superseded: 'text-muted-foreground',
}

/** Fleet.Tariff (BR-13): a new tariff from an effective date; the previous one stays. */
function DefineTariff({ onSaved }: { onSaved: (note: string) => void }) {
  const categories = useQuery({ queryKey: CATEGORIES_KEY, queryFn: listCategories })
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<TariffValues>({
    resolver: zodResolver(tariffSchema),
    defaultValues: { vehicle_category: '', effective_from: '' },
  })
  const save = useMutation({
    mutationFn: (values: TariffValues) =>
      defineTariff({
        ...values,
        vehicle_category: Number(values.vehicle_category),
        free_km_allowance: Number(values.free_km_allowance),
        effective_from: values.effective_from ? localToISO(values.effective_from) : null,
      }),
    onSuccess: (tariff) => {
      reset({ vehicle_category: '', effective_from: '' })
      onSaved(
        tariff.state === 'Scheduled'
          ? `${tariff.category_name} tariff scheduled from ${formatDateTime(tariff.effective_from)}.`
          : `${tariff.category_name} tariff in force now. Confirmed bookings keep the tariff they were priced at.`,
      )
    },
    onError: (error) => setFormError(applyServerErrors(error, setError, TARIFF_FIELDS)),
  })
  const money = (name: (typeof TARIFF_FIELDS)[number], label: string, hint?: string) => (
    <Field id={`tariff-${name}`} label={label} hint={hint} error={errors[name]?.message}>
      <Input
        id={`tariff-${name}`}
        inputMode="decimal"
        aria-invalid={errors[name] ? true : undefined}
        aria-describedby={describedBy(`tariff-${name}`, { hint: Boolean(hint), error: Boolean(errors[name]) })}
        {...register(name)}
      />
    </Field>
  )
  return (
    <form
      noValidate
      className={FORM}
      onSubmit={handleSubmit((values) => {
        setFormError(null)
        save.mutate(values)
      })}
    >
      <FormAlert message={formError} />
      <Field id="tariff-vehicle_category" label="Vehicle category" error={errors.vehicle_category?.message}>
        <NativeSelect id="tariff-vehicle_category" aria-invalid={errors.vehicle_category ? true : undefined} {...register('vehicle_category')}>
          <option value="">Choose a category</option>
          {(categories.data ?? []).map((category) => (
            <option key={category.id} value={category.id}>
              {category.name} ({category.vehicle_type})
            </option>
          ))}
        </NativeSelect>
      </Field>
      <div className="grid gap-5 @lg/form:grid-cols-3 @3xl/form:grid-cols-1">
        {money('hourly_rate', 'Hourly rate (₹)')}
        {money('daily_rate', 'Daily rate (₹)')}
        {money('weekly_rate', 'Weekly rate (₹)')}
      </div>
      <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
        {money('free_km_allowance', 'Free kilometres per day')}
        {money('excess_km_rate', 'Excess-kilometre rate (₹ per km)')}
      </div>
      <Field
        id="tariff-effective_from"
        label="Effective from"
        hint="Leave empty to start now. It cannot be in the past (BR-13)."
        error={errors.effective_from?.message}
      >
        <Input
          id="tariff-effective_from"
          type="datetime-local"
          aria-describedby={describedBy('tariff-effective_from', { hint: true, error: Boolean(errors.effective_from) })}
          {...register('effective_from')}
        />
      </Field>
      <p className={cn('text-sm text-muted-foreground', FORM_INDENT)}>
        The security deposit is the one BR-3 fixes for the category's vehicle type. Confirmed bookings and issued invoices keep the tariff they were priced at.
      </p>
      <div className={FORM_INDENT}>
        <SubmitButton busy={save.isPending} busyLabel="Saving…">
          Define tariff
        </SubmitButton>
      </div>
    </form>
  )
}

function TariffHistory({ tariffs, onChanged }: { tariffs: AdminTariff[]; onChanged: (note: string) => void }) {
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="grid gap-3">
      <FormAlert message={error} />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Tariff history</caption>
          <thead>
            <tr className="border-b text-left text-label text-muted-foreground">
              <th scope="col" className="py-2.5 pr-3 font-normal">Category</th>
              <th scope="col" className="py-2.5 pr-3 font-normal">From</th>
              <th scope="col" className="py-2.5 pr-3 text-right font-normal">Hour</th>
              <th scope="col" className="py-2.5 pr-3 text-right font-normal">Day</th>
              <th scope="col" className="py-2.5 pr-3 text-right font-normal">Week</th>
              <th scope="col" className="py-2.5 pr-3 text-right font-normal">Free km/day</th>
              <th scope="col" className="py-2.5 pr-3 text-right font-normal">Excess km</th>
              <th scope="col" className="py-2.5 pr-3 text-right font-normal">Deposit</th>
              <th scope="col" className="py-2.5 pr-3 font-normal">State</th>
              <th scope="col" className="py-2.5 font-normal">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {tariffs.map((tariff) => (
              <tr key={tariff.id} className="border-b">
                <td className="py-2.5 pr-3">{tariff.category_name}</td>
                <td className="num py-2.5 pr-3 whitespace-nowrap">{formatDateTime(tariff.effective_from)}</td>
                <td className="num py-2.5 pr-3 text-right whitespace-nowrap">{formatINR(tariff.hourly_rate)}</td>
                <td className="num py-2.5 pr-3 text-right whitespace-nowrap">{formatINR(tariff.daily_rate)}</td>
                <td className="num py-2.5 pr-3 text-right whitespace-nowrap">{formatINR(tariff.weekly_rate)}</td>
                <td className="num py-2.5 pr-3 text-right">{tariff.free_km_allowance}</td>
                <td className="num py-2.5 pr-3 text-right whitespace-nowrap">{formatINR(tariff.excess_km_rate)}</td>
                <td className="num py-2.5 pr-3 text-right whitespace-nowrap">{formatINR(tariff.security_deposit)}</td>
                <td className={cn('py-2.5 pr-3 whitespace-nowrap', STATE_TONE[tariff.state])}>
                  {tariff.state}
                  <span className="block text-xs font-normal text-muted-foreground">
                    {tariff.booking_count} {tariff.booking_count === 1 ? 'booking' : 'bookings'} priced at it
                  </span>
                </td>
                <td className="py-2.5 text-right">
                  {tariff.state === 'Scheduled' ? (
                    <Button
                      variant="outline"
                      size="sm"
                      aria-label={`Withdraw the ${tariff.category_name} tariff`}
                      onClick={() =>
                        void withdrawTariff(tariff.id)
                          .then(() => onChanged(`The scheduled ${tariff.category_name} tariff was withdrawn.`))
                          .catch((failure: unknown) => setError(message(failure)))
                      }
                    >
                      Withdraw
                    </Button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** Book.Addons, BR-7: name, daily rate and availability. A booking keeps its own rate. */
function AddOns({ addOns, onChanged }: { addOns: AdminAddOn[]; onChanged: (note: string) => void }) {
  const [name, setName] = useState('')
  const [rate, setRate] = useState('')
  const [type, setType] = useState('')
  const [error, setError] = useState<string | null>(null)
  const act = (work: Promise<unknown>, note: string) =>
    void work.then(() => onChanged(note)).catch((failure: unknown) => setError(message(failure)))
  const add = (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    act(
      saveAddOn({ name: name.trim(), daily_rate: rate.trim(), vehicle_type: type }).then(() => {
        setName('')
        setRate('')
      }),
      `${name.trim()} added.`,
    )
  }
  return (
    <div className="grid gap-4">
      <FormAlert message={error} />
      <ul aria-label="Add-ons" className="border-t">
        {addOns.map((addOn) => (
          <li key={addOn.id} className="flex flex-wrap items-center justify-between gap-3 border-b py-3">
            <span className={cn(!addOn.is_active && 'text-muted-foreground')}>
              <span className="font-medium">{addOn.name}</span> ·{' '}
              <span className="num">{formatINR(addOn.daily_rate)}</span> a day · {addOn.vehicle_type || 'any vehicle'}
              {addOn.is_active ? '' : ' · not offered'}
            </span>
            <Button
              variant="outline"
              size="sm"
              aria-label={`${addOn.is_active ? 'Stop offering' : 'Offer again'} ${addOn.name}`}
              onClick={() =>
                act(saveAddOn({ is_active: !addOn.is_active }, addOn.id), `${addOn.name} ${addOn.is_active ? 'withdrawn' : 'offered again'}.`)
              }
            >
              {addOn.is_active ? 'Stop offering' : 'Offer again'}
            </Button>
          </li>
        ))}
      </ul>
      <form noValidate onSubmit={add} className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <label htmlFor="addon-name" className="text-sm font-medium">Add-on</label>
          <Input id="addon-name" className="w-56" value={name} onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="addon-rate" className="text-sm font-medium">Add-on rate a day (₹)</label>
          <Input id="addon-rate" className="w-32" inputMode="decimal" value={rate} onChange={(event) => setRate(event.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="addon-type" className="text-sm font-medium">For</label>
          <NativeSelect id="addon-type" className="w-44" value={type} onChange={(event) => setType(event.target.value)}>
            <option value="">Any vehicle</option>
            <option>Car</option>
            <option>Two-Wheeler</option>
          </NativeSelect>
        </div>
        <Button type="submit" variant="outline">
          Add add-on
        </Button>
      </form>
    </div>
  )
}

/** D17: admin-managed discount codes. */
function DiscountCodes({ codes, onChanged }: { codes: AdminDiscountCode[]; onChanged: (note: string) => void }) {
  const [code, setCode] = useState('')
  const [kind, setKind] = useState<DiscountType>('Percent')
  const [value, setValue] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [error, setError] = useState<string | null>(null)
  const act = (work: Promise<unknown>, note: string) =>
    void work.then(() => onChanged(note)).catch((failure: unknown) => setError(message(failure)))
  const add = (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (!code.trim() || !value.trim() || !from || !to) {
      setError('Enter the code, its value and when it starts and ends.')
      return
    }
    act(
      saveDiscountCode({
        code: code.trim(),
        discount_type: kind,
        value: value.trim(),
        valid_from: localToISO(from),
        valid_to: localToISO(to),
      }).then(() => setCode('')),
      `${code.trim().toUpperCase()} created.`,
    )
  }
  return (
    <div className="grid gap-4">
      <FormAlert message={error} />
      <ul aria-label="Discount codes" className="border-t">
        {codes.map((discount) => (
          <li key={discount.id} className="flex flex-wrap items-center justify-between gap-3 border-b py-3">
            <span className={cn(!discount.is_active && 'text-muted-foreground')}>
              <span className="num font-medium">{discount.code}</span> ·{' '}
              {discount.discount_type === 'Percent' ? `${discount.value}%` : formatINR(discount.value)} ·{' '}
              <span className="num">{formatDateTime(discount.valid_from)}</span> to{' '}
              <span className="num">{formatDateTime(discount.valid_to)}</span> · used {discount.times_used}
              {discount.usage_limit ? ` of ${discount.usage_limit}` : ''} times
              {discount.is_active ? '' : ' · switched off'}
            </span>
            <Button
              variant="outline"
              size="sm"
              aria-label={`${discount.is_active ? 'Switch off' : 'Switch on'} ${discount.code}`}
              onClick={() =>
                act(
                  saveDiscountCode({ is_active: !discount.is_active }, discount.id),
                  `${discount.code} ${discount.is_active ? 'switched off' : 'switched on'}.`,
                )
              }
            >
              {discount.is_active ? 'Switch off' : 'Switch on'}
            </Button>
          </li>
        ))}
      </ul>
      <form noValidate onSubmit={add} className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <label htmlFor="discount-code" className="text-sm font-medium">Code</label>
          <Input id="discount-code" className="w-40" value={code} onChange={(event) => setCode(event.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="discount-type" className="text-sm font-medium">Type</label>
          <NativeSelect id="discount-type" className="w-36" value={kind} onChange={(event) => setKind(event.target.value as DiscountType)}>
            <option>Percent</option>
            <option>Fixed</option>
          </NativeSelect>
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="discount-value" className="text-sm font-medium">Value</label>
          <Input id="discount-value" className="w-28" inputMode="decimal" value={value} onChange={(event) => setValue(event.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="discount-from" className="text-sm font-medium">Valid from</label>
          <Input id="discount-from" type="datetime-local" value={from} onChange={(event) => setFrom(event.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="discount-to" className="text-sm font-medium">Valid to</label>
          <Input id="discount-to" type="datetime-local" value={to} onChange={(event) => setTo(event.target.value)} />
        </div>
        <Button type="submit" variant="outline">
          Create code
        </Button>
      </form>
    </div>
  )
}

/** UC 11 step 2 (BR-13, Exp 3 Administrator.define_tariff()), add-ons and discount codes. */
export function TariffsPage() {
  const queryClient = useQueryClient()
  const [note, setNote] = useState<string | null>(null)
  const tariffs = useQuery({ queryKey: TARIFFS_KEY, queryFn: listTariffs })
  const addOns = useQuery({ queryKey: ADD_ONS_KEY, queryFn: listAddOns })
  const codes = useQuery({ queryKey: DISCOUNTS_KEY, queryFn: listDiscountCodes })
  const changed = (text: string) => {
    for (const key of [TARIFFS_KEY, ADD_ONS_KEY, DISCOUNTS_KEY]) void queryClient.invalidateQueries({ queryKey: key })
    setNote(text)
  }

  return (
    <section>
      <PageHeader
        title="Tariffs"
        photo="band-payment-1"
        variant="compact"
        description="Tariffs, add-ons and discount codes."
      />
      <div className="mb-6">
        <StatusMessage message={note} tone="success" />
      </div>
      <div className="grid gap-12">
        <section aria-labelledby="tariffs-define" className="grid gap-5">
          <h2 id="tariffs-define">Define a tariff</h2>
          <div className="max-w-4xl">
            <DefineTariff onSaved={changed} />
          </div>
        </section>
        <section aria-labelledby="tariffs-history" className="grid gap-5">
          <h2 id="tariffs-history">Tariff history</h2>
          {tariffs.isPending ? (
            <LoadingState label="Loading the tariffs…" rows={3} />
          ) : tariffs.isError ? (
            <ErrorState title="We couldn’t load the tariffs" error={tariffs.error} onRetry={() => void tariffs.refetch()} />
          ) : (
            <TariffHistory tariffs={tariffs.data} onChanged={changed} />
          )}
        </section>
        <section aria-labelledby="tariffs-add-ons" className="grid gap-5">
          <h2 id="tariffs-add-ons">Add-ons</h2>
          {addOns.isPending ? (
            <LoadingState label="Loading the add-ons…" />
          ) : addOns.isError ? (
            <ErrorState title="We couldn’t load the add-ons" error={addOns.error} onRetry={() => void addOns.refetch()} />
          ) : (
            <AddOns addOns={addOns.data} onChanged={changed} />
          )}
        </section>
        <section aria-labelledby="tariffs-discounts" className="grid gap-5">
          <h2 id="tariffs-discounts">Discount codes</h2>
          {codes.isPending ? (
            <LoadingState label="Loading the discount codes…" />
          ) : codes.isError ? (
            <ErrorState title="We couldn’t load the discount codes" error={codes.error} onRetry={() => void codes.refetch()} />
          ) : (
            <DiscountCodes codes={codes.data} onChanged={changed} />
          )}
        </section>
      </div>
    </section>
  )
}
