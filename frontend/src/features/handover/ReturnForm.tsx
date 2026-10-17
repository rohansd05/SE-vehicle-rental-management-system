import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Calculator, Plus, X } from 'lucide-react'
import { type FormEvent, useRef, useState } from 'react'

import { ApiError } from '@/api/client'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { useSignedInUser } from '@/features/auth/auth-context'
import { ImagePicker } from '@/features/licence/ImagePicker'
import { checkLicenceImage, LICENCE_IMAGE_ACCEPT } from '@/features/licence/rules'
import { isoToLocal, localToISO } from '@/features/search/schema'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { now } from '@/lib/dates'
import { FORM } from '@/lib/layout'

import {
  completeReturn,
  type DamageCharge,
  type DamageMark,
  quoteReturn,
  type Refusal,
  type ReturnDetail,
  type ReturnQuote,
  type ReturnReadings,
} from './api'
import { RETURNS_KEY, returnKey } from './keys'
import { HandoverPhoto } from './PhotoCompare'
import { SettlementSummary } from './SettlementSummary'
import { SignaturePad, type SignaturePadHandle } from './SignaturePad'
import { VehicleDiagram } from './VehicleDiagram'

type Errors = Record<string, string>

const sectionTitle = 'text-subsection font-semibold text-foreground'
const SEVERITIES = ['Low', 'Medium', 'High', 'Critical'] as const

/** What the browser can check before asking for the settlement (the server checks it all, CO-3). */
function check(odometer: string, fuel: string, returnedAt: string, costs: Record<string, string>, damage: DamageCharge[]) {
  const errors: Errors = {}
  if (!/^\d+$/.test(odometer.trim())) errors.odometer_reading = 'Enter the odometer reading in whole km.'
  const level = Number(fuel)
  if (fuel.trim() === '' || Number.isNaN(level) || level < 0 || level > 100) {
    errors.fuel_level = 'Enter the fuel or charge level, from 0 to 100%.'
  }
  if (!returnedAt) errors.returned_at = 'Enter the time the vehicle was returned.'
  if (Object.values(costs).some((cost) => !/^\d+(\.\d{1,2})?$/.test(cost.trim()))) {
    errors.missing_accessories = 'Enter the cost of each accessory not returned.'
  }
  if (damage.some((item) => !item.description.trim() || !/^\d+(\.\d{1,2})?$/.test(item.amount.trim()) || !item.justification.trim())) {
    errors.damage_charges = 'Give each damage charge a description, an amount and a justification.'
  }
  return errors
}

/**
 * Return.Checklist, Return.Charges, Return.Settle and Return.Flag (Exp 2 use
 * case 8; Exp 5: the customer acknowledges the itemised settlement before it
 * is settled). The server computes every charge, records the signed report,
 * settles the deposit, completes the booking and releases or flags the vehicle.
 */
export function ReturnForm({
  booking,
  onDone,
  onRefused,
}: {
  booking: ReturnDetail
  onDone: (next: ReturnDetail) => void
  onRefused: (refusals: Refusal[]) => void
}) {
  const queryClient = useQueryClient()
  const user = useSignedInUser()
  const { currency } = useAgency()
  const signature = useRef<SignaturePadHandle>(null)
  const handover = booking.handover_report
  const sides = booking.photo_sides
  const issued = handover?.accessories ?? []

  const [odometer, setOdometer] = useState(String(handover?.odometer_reading ?? booking.vehicle.odometer))
  const [fuel, setFuel] = useState('')
  const [returnedAt, setReturnedAt] = useState(() => isoToLocal(new Date(now()).toISOString()))
  const [missing, setMissing] = useState<Record<string, string>>({})
  const [damage, setDamage] = useState<DamageCharge[]>([])
  const [marks, setMarks] = useState<DamageMark[]>([])
  const [photos, setPhotos] = useState<Record<string, File | null>>({})
  const [extras, setExtras] = useState<File[]>([])
  const [flagged, setFlagged] = useState(false)
  const [flag, setFlag] = useState({ problem: '', severity: '', unfit: true })
  const [override, setOverride] = useState({ email: '', password: '', reason: '' })
  const [signed, setSigned] = useState(false)
  const [quote, setQuote] = useState<ReturnQuote | null>(null)
  const [quotes, setQuotes] = useState(0) // a new settlement needs a new signature
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  // Any change to what is charged makes the settlement the customer saw stale.
  const changed = <T,>(set: (value: T) => void) => (value: T) => {
    set(value)
    setQuote(null)
    setSigned(false)
  }

  const readings = (): ReturnReadings => ({
    odometer_reading: odometer.trim(),
    fuel_level: fuel.trim(),
    returned_at: returnedAt ? localToISO(returnedAt) : '',
    missing_accessories: issued
      .filter((item) => item.name in missing)
      .map((item) => ({ ...item, cost: missing[item.name]?.trim() ?? '' })),
    damage_charges: damage,
  })

  const serverErrors = (error: unknown) => {
    if (error instanceof ApiError && error.status === 409) {
      const body = error.body as { refusals?: Refusal[] } | undefined
      if (body?.refusals?.length) {
        void queryClient.invalidateQueries({ queryKey: returnKey(booking.id) })
        onRefused(body.refusals)
        return
      }
      if (error.code === 'settlement_changed') setQuote(null)
    }
    if (error instanceof ApiError && Object.keys(error.fieldErrors).length) {
      setErrors(Object.fromEntries(Object.entries(error.fieldErrors).map(([key, value]) => [key, value.join(' ')])))
    }
    setFormError(error instanceof Error ? error.message : 'The return could not be completed.')
  }

  const calculate = useMutation({
    mutationFn: () => quoteReturn(booking.id, readings()),
    onSuccess: (next) => {
      setQuote(next)
      setQuotes((count) => count + 1)
      setSigned(false)
      setFormError(null)
      setNotice('Show the settlement to the customer and ask them to sign to acknowledge it.')
    },
    onError: serverErrors,
  })

  const complete = useMutation({
    mutationFn: async () => {
      const blob = await signature.current?.toBlob()
      if (!blob || !quote) throw new ApiError(400, 'The customer must sign to acknowledge the settlement.')
      return completeReturn(booking.id, {
        ...readings(),
        damage_marks: marks,
        photos: Object.fromEntries(sides.map((side) => [side, photos[side] as File])),
        extra_photos: extras,
        signature: blob,
        expected_total: quote.total,
        flag: flagged ? flag : null,
        override: quote.override_required ? override : null,
      })
    },
    onSuccess: (next) => {
      queryClient.setQueryData(returnKey(booking.id), next)
      void queryClient.invalidateQueries({ queryKey: RETURNS_KEY })
      onDone(next)
    },
    onError: serverErrors,
  })

  const askForSettlement = () => {
    const found = check(odometer, fuel, returnedAt, missing, damage)
    setErrors(found)
    if (Object.keys(found).length) {
      setFormError('Complete the readings and charges before you calculate the settlement.')
      return
    }
    setFormError(null)
    calculate.mutate()
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found = check(odometer, fuel, returnedAt, missing, damage)
    for (const side of sides) {
      if (!photos[side]) found[`photo_${side.toLowerCase()}`] = `Add a photo of the ${side.toLowerCase()} of the vehicle.`
    }
    if (flagged && !flag.problem.trim()) found.flag_problem = 'Describe the problem.'
    if (flagged && !flag.severity) found.flag_severity = 'Choose the severity of the problem.'
    if (quote?.override_required && !(override.email.trim() && override.password && override.reason.trim())) {
      found.override_reason = 'A Branch Manager or an Administrator must approve the reading and give the reason.'
    }
    if (!quote) found.settlement = 'Calculate the settlement and show it to the customer first.'
    else if (!signed) found.signature = 'The customer must sign to acknowledge the settlement.'
    setErrors(found)
    if (Object.keys(found).length) {
      setFormError('Complete the checklist, the settlement and the signature before you finish the return.')
      return
    }
    setFormError(null)
    complete.mutate()
  }

  const money = (amount: string) => formatCurrency(amount, currency)
  const cash = booking.deposit_method === 'Cash'

  return (
    <form noValidate onSubmit={submit} aria-labelledby="return-form-title" className="grid gap-10">
      <h2 id="return-form-title">Return checklist</h2>
      <FormAlert message={formError} />

      <fieldset className={FORM}>
        <legend className={`${sectionTitle} mb-4`}>Readings</legend>
        <Field
          id="odometer_reading"
          label="Odometer (km)"
          hint={handover ? `${handover.odometer_reading} km at handover.` : undefined}
          error={errors.odometer_reading}
        >
          <Input
            id="odometer_reading"
            inputMode="numeric"
            className="num"
            value={odometer}
            aria-invalid={errors.odometer_reading ? true : undefined}
            aria-describedby={errors.odometer_reading ? 'odometer_reading-error' : 'odometer_reading-hint'}
            onChange={(event) => changed(setOdometer)(event.target.value)}
          />
        </Field>
        <Field
          id="fuel_level"
          label="Fuel or charge level (%)"
          hint={handover ? `${Number(handover.fuel_level)}% at handover.` : undefined}
          error={errors.fuel_level}
        >
          <Input
            id="fuel_level"
            inputMode="decimal"
            className="num"
            value={fuel}
            aria-invalid={errors.fuel_level ? true : undefined}
            aria-describedby={errors.fuel_level ? 'fuel_level-error' : 'fuel_level-hint'}
            onChange={(event) => changed(setFuel)(event.target.value)}
          />
        </Field>
        <Field id="returned_at" label="Returned at" error={errors.returned_at}>
          <Input
            id="returned_at"
            type="datetime-local"
            className="num"
            value={returnedAt}
            aria-invalid={errors.returned_at ? true : undefined}
            aria-describedby={errors.returned_at ? 'returned_at-error' : undefined}
            onChange={(event) => changed(setReturnedAt)(event.target.value)}
          />
        </Field>
      </fieldset>

      <fieldset className="grid gap-3">
        <legend className={`${sectionTitle} mb-4`}>Accessories returned</legend>
        {issued.length === 0 ? (
          <p className="text-sm text-muted-foreground">No accessories were issued with this rental.</p>
        ) : (
          issued.map((item) => {
            const id = `returned-${item.name}`
            const isMissing = item.name in missing
            return (
              <div key={item.name} className="grid gap-2">
                <div className="flex items-center gap-3">
                  <input
                    id={id}
                    type="checkbox"
                    className="size-4"
                    checked={!isMissing}
                    onChange={(event) => {
                      const { [item.name]: _removed, ...rest } = missing
                      changed(setMissing)(event.target.checked ? rest : { ...missing, [item.name]: '' })
                    }}
                  />
                  <Label htmlFor={id}>
                    {item.name} × <span className="num">{item.quantity}</span>
                  </Label>
                </div>
                {isMissing ? (
                  <div className="grid max-w-xs gap-1.5 pl-7">
                    <Label htmlFor={`cost-${item.name}`}>Cost of the missing {item.name.toLowerCase()}</Label>
                    <Input
                      id={`cost-${item.name}`}
                      inputMode="decimal"
                      className="num"
                      value={missing[item.name]}
                      onChange={(event) => changed(setMissing)({ ...missing, [item.name]: event.target.value })}
                    />
                  </div>
                ) : null}
              </div>
            )
          })
        )}
        {errors.missing_accessories ? (
          <p className="text-small font-medium text-destructive">{errors.missing_accessories}</p>
        ) : null}
      </fieldset>

      <fieldset className="@container grid gap-5">
        <legend className={`${sectionTitle} mb-1`}>Photographs</legend>
        <p className="text-sm text-muted-foreground">
          One photo of each side, beside the one taken at handover, so new damage stands out.
        </p>
        <div className="grid gap-8">
          {sides.map((side) => {
            const key = `photo_${side.toLowerCase()}`
            return (
              <div key={side} className="grid gap-4 @xl:grid-cols-2">
                <HandoverPhoto report={handover} side={side} />
                <ImagePicker
                  id={key}
                  label={side}
                  file={photos[side] ?? null}
                  error={errors[key] ?? null}
                  onChange={(file, problem) => {
                    setPhotos({ ...photos, [side]: file })
                    setErrors((current) => {
                      const { [key]: _removed, ...rest } = current
                      return problem ? { ...rest, [key]: problem } : rest
                    })
                  }}
                />
              </div>
            )
          })}
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="extra_photos">More photos (optional)</Label>
          <input
            id="extra_photos"
            type="file"
            multiple
            accept={LICENCE_IMAGE_ACCEPT}
            className="max-w-full text-sm text-muted-foreground file:mr-3 file:h-8 file:rounded-md file:border file:border-input file:bg-surface file:px-3 file:text-small file:font-medium file:text-foreground hover:file:bg-muted"
            onChange={(event) => {
              const chosen = Array.from(event.target.files ?? [])
              const problem = chosen.map(checkLicenceImage).find(Boolean)
              if (problem) {
                event.target.value = ''
                setExtras([])
              } else {
                setExtras(chosen)
              }
              setErrors(({ extra_photos: _removed, ...rest }) => (problem ? { ...rest, extra_photos: problem } : rest))
            }}
          />
          {errors.extra_photos ? <p className="text-small font-medium text-destructive">{errors.extra_photos}</p> : null}
        </div>
      </fieldset>

      <fieldset className="@container grid gap-4">
        <legend className={`${sectionTitle} mb-1`}>New damage</legend>
        <VehicleDiagram marks={marks} onChange={setMarks} />
      </fieldset>

      <fieldset className="grid gap-4">
        <legend className={`${sectionTitle} mb-1`}>Damage charges</legend>
        {damage.map((item, index) => {
          const update = (patch: Partial<DamageCharge>) =>
            changed(setDamage)(damage.map((line, i) => (i === index ? { ...line, ...patch } : line)))
          return (
            <div key={index} className="grid gap-3 border-b pb-4 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end">
              <div className="grid gap-1.5">
                <Label htmlFor={`damage-description-${index}`}>Damage {index + 1}</Label>
                <Input
                  id={`damage-description-${index}`}
                  value={item.description}
                  maxLength={150}
                  onChange={(event) => update({ description: event.target.value })}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor={`damage-amount-${index}`}>Amount</Label>
                <Input
                  id={`damage-amount-${index}`}
                  inputMode="decimal"
                  className="num"
                  value={item.amount}
                  onChange={(event) => update({ amount: event.target.value })}
                />
              </div>
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={`Remove damage ${index + 1}`}
                onClick={() => changed(setDamage)(damage.filter((_, i) => i !== index))}
              >
                <X aria-hidden="true" />
              </Button>
              <div className="grid gap-1.5 sm:col-span-3">
                <Label htmlFor={`damage-justification-${index}`}>Justification</Label>
                <Textarea
                  id={`damage-justification-${index}`}
                  value={item.justification}
                  maxLength={500}
                  onChange={(event) => update({ justification: event.target.value })}
                />
              </div>
            </div>
          )
        })}
        {errors.damage_charges ? <p className="text-small font-medium text-destructive">{errors.damage_charges}</p> : null}
        <div>
          <Button
            type="button"
            variant="outline"
            onClick={() => changed(setDamage)([...damage, { description: '', amount: '', justification: '' }])}
          >
            <Plus aria-hidden="true" />
            Add a damage charge
          </Button>
        </div>
      </fieldset>

      <fieldset className="grid gap-4">
        <legend className={`${sectionTitle} mb-1`}>Flag for maintenance</legend>
        <div className="flex items-start gap-3 border-l-2 border-l-status-maintenance pl-3">
          <input
            id="flag"
            type="checkbox"
            className="mt-1 size-4"
            checked={flagged}
            onChange={(event) => setFlagged(event.target.checked)}
          />
          <div className="grid gap-0.5">
            <Label htmlFor="flag">Flag the vehicle for maintenance</Label>
            <p className="text-small text-muted-foreground">A maintenance job is created for the problem you describe.</p>
          </div>
        </div>
        {flagged ? (
          <div className={FORM}>
            <Field id="flag_problem" label="Problem" error={errors.flag_problem}>
              <Textarea
                id="flag_problem"
                value={flag.problem}
                maxLength={1000}
                aria-invalid={errors.flag_problem ? true : undefined}
                aria-describedby={errors.flag_problem ? 'flag_problem-error' : undefined}
                onChange={(event) => setFlag({ ...flag, problem: event.target.value })}
              />
            </Field>
            <Field id="flag_severity" label="Severity" error={errors.flag_severity}>
              <NativeSelect
                id="flag_severity"
                value={flag.severity}
                aria-invalid={errors.flag_severity ? true : undefined}
                aria-describedby={errors.flag_severity ? 'flag_severity-error' : undefined}
                onChange={(event) => setFlag({ ...flag, severity: event.target.value })}
              >
                <option value="">Choose…</option>
                {SEVERITIES.map((severity) => (
                  <option key={severity} value={severity}>
                    {severity}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <div className="flex items-center gap-3">
              <input
                id="flag_unfit"
                type="checkbox"
                className="size-4"
                checked={flag.unfit}
                onChange={(event) => setFlag({ ...flag, unfit: event.target.checked })}
              />
              <Label htmlFor="flag_unfit">The vehicle is unfit for use until it is repaired</Label>
            </div>
          </div>
        ) : null}
      </fieldset>

      <section aria-label="Settlement" className="grid gap-5">
        <div>
          <Button type="button" variant="outline" size="lg" disabled={calculate.isPending} onClick={askForSettlement}>
            <Calculator aria-hidden="true" />
            {calculate.isPending ? 'Calculating…' : 'Calculate settlement'}
          </Button>
        </div>
        {errors.settlement ? <p className="text-small font-medium text-destructive">{errors.settlement}</p> : null}
        {quote ? (
          <div className="enter grid gap-5">
            <StatusMessage message={notice} />
            <SettlementSummary settlement={quote} paid={booking.rental_paid} rentalTotal={booking.total_amount} />
            {cash && Number(quote.refund) > 0 ? (
              <p className="rounded-md border-l-2 border-l-primary bg-primary-tint px-4 py-3 text-sm">
                The deposit was paid in cash. Pay the customer{' '}
                <strong className="num-strong">{money(quote.refund)}</strong> in cash; you, {user.name}, are recorded as
                the staff member who paid it.
              </p>
            ) : null}
            {quote.override_required ? (
              <div className={FORM}>
                <p className="rounded-md border-l-2 border-l-status-unsafe bg-status-unsafe-tint px-4 py-3 text-sm">
                  {quote.distance} km is more than the {quote.plausibility_limit_km} km plausible for this rental. A
                  Branch Manager or an Administrator must approve the reading.
                </p>
                <Field id="override_email" label="Supervisor e-mail">
                  <Input
                    id="override_email"
                    type="email"
                    autoComplete="off"
                    value={override.email}
                    onChange={(event) => setOverride({ ...override, email: event.target.value })}
                  />
                </Field>
                <Field id="override_password" label="Supervisor password" error={errors.override_password}>
                  <Input
                    id="override_password"
                    type="password"
                    autoComplete="off"
                    value={override.password}
                    aria-invalid={errors.override_password ? true : undefined}
                    aria-describedby={errors.override_password ? 'override_password-error' : undefined}
                    onChange={(event) => setOverride({ ...override, password: event.target.value })}
                  />
                </Field>
                <Field id="override_reason" label="Reason" error={errors.override_reason}>
                  <Textarea
                    id="override_reason"
                    value={override.reason}
                    maxLength={500}
                    aria-invalid={errors.override_reason ? true : undefined}
                    aria-describedby={errors.override_reason ? 'override_reason-error' : undefined}
                    onChange={(event) => setOverride({ ...override, reason: event.target.value })}
                  />
                </Field>
              </div>
            ) : null}
            <p className="text-sm text-muted-foreground">
              By signing, the customer acknowledges the return condition report and the settlement above. The signed report
              cannot be changed afterwards.
            </p>
            <SignaturePad
              key={quotes}
              ref={signature}
              id="signature"
              label="Customer signature"
              signed={signed}
              onSignedChange={(next) => {
                setSigned(next)
                if (next) setErrors(({ signature: _removed, ...rest }) => rest)
              }}
              error={errors.signature}
            />
          </div>
        ) : null}
      </section>

      <div>
        <SubmitButton busy={complete.isPending} busyLabel="Settling the return…">
          Settle and complete return
        </SubmitButton>
      </div>
    </form>
  )
}
