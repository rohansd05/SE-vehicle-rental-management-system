import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { submitLicence } from '@/api/licences'
import type { Licence } from '@/api/types'
import { Field, FormAlert, SubmitButton } from '@/components/form'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { todayISO } from '@/lib/dates'
import { applyServerErrors, describedBy } from '@/lib/form'

import { ImagePicker } from './ImagePicker'
import { LICENCE_CATEGORIES, type LicenceDetailsValues, licenceDetailsSchema } from './rules'

const SERVER_FIELDS = [
  'licence_number',
  'issuing_authority',
  'issue_date',
  'expiry_date',
  'categories',
] as const

interface Images {
  front: File | null
  back: File | null
  frontError: string | null
  backError: string | null
}

/** Submit or resubmit the licence (Appendix A fields, both images). */
export function LicenceForm({
  current,
  onSubmitted,
  onCancel,
}: {
  current: Licence
  onSubmitted: (licence: Licence) => void
  onCancel?: () => void
}) {
  const [formError, setFormError] = useState<string | null>(null)
  const [images, setImages] = useState<Images>({
    front: null,
    back: null,
    frontError: null,
    backError: null,
  })
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LicenceDetailsValues>({
    resolver: zodResolver(licenceDetailsSchema),
    defaultValues: {
      licence_number: current.licence_number,
      issuing_authority: current.issuing_authority,
      issue_date: current.issue_date ?? '',
      expiry_date: current.status === 'Expired' ? '' : (current.expiry_date ?? ''),
      categories: current.categories.filter((c): c is 'Car' | 'Two-Wheeler' =>
        (LICENCE_CATEGORIES as readonly string[]).includes(c),
      ),
    },
  })

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    const missingFront = images.front ? null : (images.frontError ?? 'Add a photo of the front of the licence.')
    const missingBack = images.back ? null : (images.backError ?? 'Add a photo of the back of the licence.')
    if (missingFront || missingBack) {
      setImages((state) => ({ ...state, frontError: missingFront, backError: missingBack }))
      document.getElementById(missingFront ? 'front_image' : 'back_image')?.focus()
      return
    }
    try {
      const licence = await submitLicence({
        ...values,
        front_image: images.front!,
        back_image: images.back!,
      })
      onSubmitted(licence)
    } catch (error) {
      const message = applyServerErrors(error, setError, SERVER_FIELDS)
      const fieldErrors = (error as { fieldErrors?: Record<string, string[]> }).fieldErrors ?? {}
      if (fieldErrors.front_image || fieldErrors.back_image) {
        setImages((state) => ({
          ...state,
          frontError: fieldErrors.front_image?.join(' ') ?? state.frontError,
          backError: fieldErrors.back_image?.join(' ') ?? state.backError,
        }))
        document.getElementById(fieldErrors.front_image ? 'front_image' : 'back_image')?.focus()
      }
      const imageOnly = Object.keys(fieldErrors).every((key) => key.endsWith('_image'))
      setFormError(imageOnly && Object.keys(fieldErrors).length ? null : message)
    }
  })

  const field = (name: Exclude<keyof LicenceDetailsValues, 'categories'>) => ({
    id: name,
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': describedBy(name, { error: Boolean(errors[name]) }),
    ...register(name),
  })

  return (
    <form onSubmit={onSubmit} noValidate className="grid gap-5">
      <FormAlert message={formError} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="licence_number" label="Licence number" error={errors.licence_number?.message}>
          <Input autoComplete="off" {...field('licence_number')} />
        </Field>
        <Field id="issuing_authority" label="Issued by" error={errors.issuing_authority?.message}>
          <Input autoComplete="off" placeholder="RTO and city" {...field('issuing_authority')} />
        </Field>
        <Field id="issue_date" label="Issue date" error={errors.issue_date?.message}>
          <Input type="date" max={todayISO()} {...field('issue_date')} />
        </Field>
        <Field id="expiry_date" label="Expiry date" error={errors.expiry_date?.message}>
          <Input type="date" min={todayISO()} {...field('expiry_date')} />
        </Field>
      </div>

      <fieldset
        className="grid gap-2"
        aria-describedby={errors.categories ? 'categories-error' : undefined}
      >
        <legend className="mb-1 text-sm font-medium">Categories the licence covers</legend>
        <div className="flex flex-wrap gap-4">
          {LICENCE_CATEGORIES.map((category) => (
            <label key={category} className="flex min-h-10 items-center gap-2 text-sm">
              <input
                type="checkbox"
                value={category}
                className="size-4 accent-[var(--brand)]"
                {...register('categories')}
              />
              {category}
            </label>
          ))}
        </div>
        {errors.categories ? (
          <p id="categories-error" className="text-sm text-destructive">
            {errors.categories.message}
          </p>
        ) : null}
      </fieldset>

      <div className="grid gap-5">
        <ImagePicker
          id="front_image"
          label="Front of the licence"
          file={images.front}
          error={images.frontError}
          onChange={(file, error) => setImages((state) => ({ ...state, front: file, frontError: error }))}
        />
        <ImagePicker
          id="back_image"
          label="Back of the licence"
          file={images.back}
          error={images.backError}
          onChange={(file, error) => setImages((state) => ({ ...state, back: file, backError: error }))}
        />
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <SubmitButton busy={isSubmitting} busyLabel="Uploading…">
          Submit for verification
        </SubmitButton>
        {onCancel ? (
          <Button type="button" variant="outline" size="lg" className="h-10" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  )
}
