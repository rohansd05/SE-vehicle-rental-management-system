import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useRef, useState } from 'react'

import { ApiError } from '@/api/client'
import { Field, FormAlert, SubmitButton } from '@/components/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TermsList } from '@/features/booking/PriceSummary'
import { ImagePicker } from '@/features/licence/ImagePicker'
import { checkLicenceImage, LICENCE_IMAGE_ACCEPT } from '@/features/licence/rules'
import { FORM } from '@/lib/layout'

import { completeHandover, type DamageMark, type HandoverDetail, type HandoverRefused, type Refusal } from './api'
import { COLLECTIONS_KEY, handoverKey } from './keys'
import { SignaturePad, type SignaturePadHandle } from './SignaturePad'
import { VehicleDiagram } from './VehicleDiagram'

type Errors = Record<string, string>

const sectionTitle = 'text-subsection font-semibold text-foreground'

/** The checklist values the browser can check before sending (the server checks all again, CO-3). */
function check(odometer: string, fuel: string, photos: Record<string, File | null>, sides: string[], signed: boolean) {
  const errors: Errors = {}
  if (!/^\d+$/.test(odometer.trim())) errors.odometer_reading = 'Enter the odometer reading in whole km.'
  const level = Number(fuel)
  if (fuel.trim() === '' || Number.isNaN(level) || level < 0 || level > 100) {
    errors.fuel_level = 'Enter the fuel or charge level, from 0 to 100%.'
  }
  for (const side of sides) {
    if (!photos[side]) errors[`photo_${side.toLowerCase()}`] = `Add a photo of the ${side.toLowerCase()} of the vehicle.`
  }
  if (!signed) errors.signature = 'The customer must sign the condition report.'
  return errors
}

/**
 * Handover.Checklist and Handover.Sign (Exp 5: recording and signing run side
 * by side and join in one submit). The server stores the report, signs it
 * off for good, sets the booking Active and the vehicle On Rent, and e-mails
 * the customer a copy (Handover.Activate).
 */
export function HandoverForm({
  handover,
  onDone,
  onRefused,
}: {
  handover: HandoverDetail
  onDone: (next: HandoverDetail) => void
  onRefused: (refusals: Refusal[]) => void
}) {
  const queryClient = useQueryClient()
  const signature = useRef<SignaturePadHandle>(null)
  const sides = handover.photo_sides
  const [odometer, setOdometer] = useState(String(handover.vehicle.odometer))
  const [fuel, setFuel] = useState('')
  const [issued, setIssued] = useState<Record<string, boolean>>({})
  const [photos, setPhotos] = useState<Record<string, File | null>>({})
  const [extras, setExtras] = useState<File[]>([])
  const [marks, setMarks] = useState<DamageMark[]>([])
  const [signed, setSigned] = useState(false)
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const complete = useMutation({
    mutationFn: async () => {
      const blob = await signature.current?.toBlob()
      if (!blob) throw new ApiError(400, 'The customer must sign the condition report.')
      return completeHandover(handover.id, {
        odometer_reading: odometer.trim(),
        fuel_level: fuel.trim(),
        accessories: handover.accessories.filter((item) => issued[item.name]),
        damage_marks: marks,
        photos: Object.fromEntries(sides.map((side) => [side, photos[side] as File])),
        extra_photos: extras,
        signature: blob,
      })
    },
    onSuccess: (next) => {
      queryClient.setQueryData(handoverKey(handover.id), next)
      void queryClient.invalidateQueries({ queryKey: COLLECTIONS_KEY })
      onDone(next)
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        const body = error.body as Partial<HandoverRefused> | undefined
        if (body?.refusals?.length) {
          void queryClient.invalidateQueries({ queryKey: handoverKey(handover.id) })
          onRefused(body.refusals)
          return
        }
      }
      if (error instanceof ApiError && Object.keys(error.fieldErrors).length) {
        setErrors(Object.fromEntries(Object.entries(error.fieldErrors).map(([key, value]) => [key, value.join(' ')])))
      }
      setFormError(error instanceof Error ? error.message : 'The handover could not be completed.')
    },
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found = check(odometer, fuel, photos, sides, signed)
    setErrors(found)
    if (Object.keys(found).length) {
      setFormError('Complete the checklist and the signature before you finish the handover.')
      return
    }
    setFormError(null)
    complete.mutate()
  }

  return (
    <form noValidate onSubmit={submit} aria-labelledby="handover-form-title" className="grid gap-10">
      <h2 id="handover-form-title">Handover checklist</h2>
      <FormAlert message={formError} />

      <fieldset className={FORM}>
        <legend className={`${sectionTitle} mb-4`}>Readings</legend>
        <Field id="odometer_reading" label="Odometer (km)" error={errors.odometer_reading}>
          <Input
            id="odometer_reading"
            inputMode="numeric"
            className="num"
            value={odometer}
            aria-invalid={errors.odometer_reading ? true : undefined}
            aria-describedby={errors.odometer_reading ? 'odometer_reading-error' : undefined}
            onChange={(event) => setOdometer(event.target.value)}
          />
        </Field>
        <Field id="fuel_level" label="Fuel or charge level (%)" error={errors.fuel_level}>
          <Input
            id="fuel_level"
            inputMode="decimal"
            className="num"
            value={fuel}
            aria-invalid={errors.fuel_level ? true : undefined}
            aria-describedby={errors.fuel_level ? 'fuel_level-error' : undefined}
            onChange={(event) => setFuel(event.target.value)}
          />
        </Field>
      </fieldset>

      <fieldset className="grid gap-3">
        <legend className={`${sectionTitle} mb-4`}>Accessories issued</legend>
        {handover.accessories.length === 0 ? (
          <p className="text-sm text-muted-foreground">No accessories are booked with this rental.</p>
        ) : (
          handover.accessories.map((item) => {
            const id = `accessory-${item.name}`
            return (
              <div key={item.name} className="flex items-center gap-3">
                <input
                  id={id}
                  type="checkbox"
                  className="size-4"
                  checked={Boolean(issued[item.name])}
                  onChange={(event) => setIssued({ ...issued, [item.name]: event.target.checked })}
                />
                <Label htmlFor={id}>
                  {item.name} × <span className="num">{item.quantity}</span>
                </Label>
              </div>
            )
          })
        )}
      </fieldset>

      <fieldset className="grid gap-5">
        <legend className={`${sectionTitle} mb-1`}>Photographs</legend>
        <p className="text-sm text-muted-foreground">One photo of each side of the vehicle, at least four in all.</p>
        <div className="grid gap-6 sm:grid-cols-2">
          {sides.map((side) => {
            const key = `photo_${side.toLowerCase()}`
            return (
              <ImagePicker
                key={side}
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
            aria-describedby={errors.extra_photos ? 'extra_photos-error' : undefined}
            className="max-w-full text-sm text-muted-foreground file:mr-3 file:h-8 file:rounded-md file:border file:border-input file:bg-surface file:px-3 file:text-small file:font-medium file:text-foreground hover:file:bg-muted"
            onChange={(event) => {
              const chosen = Array.from(event.target.files ?? [])
              const problem = chosen.map(checkLicenceImage).find(Boolean)
              if (problem) {
                event.target.value = ''
                setExtras([])
                setErrors({ ...errors, extra_photos: problem })
              } else {
                setExtras(chosen)
                const { extra_photos: _removed, ...rest } = errors
                setErrors(rest)
              }
            }}
          />
          {errors.extra_photos ? (
            <p id="extra_photos-error" className="text-small font-medium text-destructive">
              {errors.extra_photos}
            </p>
          ) : null}
        </div>
      </fieldset>

      <fieldset className="@container grid gap-4">
        <legend className={`${sectionTitle} mb-1`}>Existing damage</legend>
        <VehicleDiagram marks={marks} onChange={setMarks} />
        {errors.damage_marks ? <p className="text-small font-medium text-destructive">{errors.damage_marks}</p> : null}
      </fieldset>

      <fieldset className="grid gap-5">
        <legend className={`${sectionTitle} mb-1`}>Rental agreement and signature</legend>
        <TermsList terms={handover.terms} />
        <p className="text-sm text-muted-foreground">
          By signing, the customer accepts this condition report and the rental terms above. The signed
          report cannot be changed afterwards, and a copy is e-mailed to the customer.
        </p>
        <SignaturePad
          ref={signature}
          id="signature"
          label="Customer signature"
          signed={signed}
          onSignedChange={(next) => {
            setSigned(next)
            if (next) {
              const { signature: _removed, ...rest } = errors
              setErrors(rest)
            }
          }}
          error={errors.signature}
        />
      </fieldset>

      <div>
        <SubmitButton busy={complete.isPending} busyLabel="Completing the handover…">
          Complete handover
        </SubmitButton>
      </div>
    </form>
  )
}
