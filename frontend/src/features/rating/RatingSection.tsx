import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Star } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import { ApiError } from '@/api/client'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { BookingDetail } from '@/features/booking/api'
import { bookingKey } from '@/features/booking/keys'
import { formatDateTime, now } from '@/lib/dates'

import { rateBooking, type RatingInput } from './api'

const SCORES = [1, 2, 3, 4, 5] as const
type Score = 'vehicle_rating' | 'service_rating'

function ScorePicker({
  name,
  legend,
  value,
  error,
  onChange,
}: {
  name: Score
  legend: string
  value: number
  error?: string
  onChange: (value: number) => void
}) {
  return (
    <fieldset className="grid gap-2" aria-describedby={error ? `${name}-error` : undefined}>
      <legend className="text-label font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {SCORES.map((score) => (
          <label
            key={score}
            className="flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-1.5 rounded-md border px-3 text-sm has-checked:border-primary has-checked:bg-primary-tint"
          >
            <input
              type="radio"
              name={name}
              value={score}
              className="sr-only"
              checked={value === score}
              onChange={() => onChange(score)}
            />
            <Star className="size-3.5 text-signal" aria-hidden="true" />
            <span className="num">{score}</span>
            <span className="sr-only"> out of 5</span>
          </label>
        ))}
      </div>
      {error ? (
        <p id={`${name}-error`} className="text-small font-medium text-destructive">
          {error}
        </p>
      ) : null}
    </fieldset>
  )
}

function RatingForm({
  booking,
  edit,
  onSaved,
  onCancel,
}: {
  booking: BookingDetail
  edit: boolean
  onSaved: () => void
  onCancel: () => void
}) {
  const queryClient = useQueryClient()
  const [values, setValues] = useState<RatingInput>({
    vehicle_rating: booking.rating?.vehicle_rating ?? 0,
    service_rating: booking.rating?.service_rating ?? 0,
    comment: booking.rating?.comment ?? '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const save = useMutation({
    mutationFn: () => rateBooking(booking.id, values, edit),
    onSuccess: (detail) => {
      queryClient.setQueryData(bookingKey(booking.id), detail)
      onSaved()
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setErrors(Object.fromEntries(Object.entries(error.fieldErrors).map(([field, messages]) => [field, messages.join(' ')])))
      }
    },
  })
  const refusal = save.error instanceof ApiError && !Object.keys(save.error.fieldErrors).length ? save.error.message : null

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    // Usability only; the server checks the scores again (CO-3).
    const missing: Record<string, string> = {}
    if (!values.vehicle_rating) missing.vehicle_rating = 'Rate the vehicle from 1 to 5.'
    if (!values.service_rating) missing.service_rating = 'Rate the service from 1 to 5.'
    setErrors(missing)
    if (!Object.keys(missing).length) save.mutate()
  }

  return (
    <form onSubmit={onSubmit} noValidate aria-label={edit ? 'Edit your review' : 'Rate this rental'} className="grid gap-5">
      <FormAlert message={refusal} />
      <ScorePicker
        name="vehicle_rating"
        legend="The vehicle"
        value={values.vehicle_rating}
        error={errors.vehicle_rating}
        onChange={(vehicle_rating) => setValues({ ...values, vehicle_rating })}
      />
      <ScorePicker
        name="service_rating"
        legend="Our service"
        value={values.service_rating}
        error={errors.service_rating}
        onChange={(service_rating) => setValues({ ...values, service_rating })}
      />
      <Field id="rating-comment" label="Comment (optional)" error={errors.comment}>
        <Textarea
          id="rating-comment"
          rows={3}
          maxLength={1000}
          value={values.comment}
          onChange={(event) => setValues({ ...values, comment: event.target.value })}
        />
      </Field>
      <div className="flex flex-wrap gap-3">
        <SubmitButton busy={save.isPending} busyLabel="Saving…">
          {edit ? 'Save changes' : 'Submit rating'}
        </SubmitButton>
        {edit ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Keep my review
          </Button>
        ) : null}
      </div>
    </form>
  )
}

/**
 * Exp 2 UC 6 Rate Vehicle on a booking: step 1 invites a rating while it can be
 * given (14 days after the return); the review can be edited for 24 hours
 * (extension 2a). Nothing shows for a booking that cannot be rated.
 */
export function RatingSection({ booking }: { booking: BookingDetail }) {
  const [editing, setEditing] = useState(false)
  const [saved, setSaved] = useState(false)
  const rating = booking.rating
  if (!rating && !booking.rating_open_until) return null
  const editable = rating ? new Date(rating.editable_until).getTime() > now() : false
  return (
    <section aria-labelledby="rating-heading" className="reveal grid gap-4 border-t pt-6">
      <div>
        <h2 id="rating-heading" className="text-section">
          {rating ? 'Your review' : 'Rate this rental'}
        </h2>
        {!rating && booking.rating_open_until ? (
          <p className="mt-1 text-sm text-muted-foreground">
            Rate the vehicle and our service from 1 to 5, until{' '}
            <span className="num">{formatDateTime(booking.rating_open_until)}</span>.
          </p>
        ) : null}
      </div>
      {saved ? <StatusMessage tone="success" message="Thank you. Your review is saved." /> : null}
      {!rating || editing ? (
        <RatingForm
          booking={booking}
          edit={Boolean(rating)}
          onSaved={() => {
            setSaved(true)
            setEditing(false)
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <div className="grid gap-3">
          <dl className="grid grid-cols-[9rem_minmax(0,1fr)] gap-x-6 gap-y-2 text-sm">
            <dt className="text-muted-foreground">The vehicle</dt>
            <dd>{rating.vehicle_rating} out of 5</dd>
            <dt className="text-muted-foreground">Our service</dt>
            <dd>{rating.service_rating} out of 5</dd>
            {rating.comment ? (
              <>
                <dt className="text-muted-foreground">Comment</dt>
                <dd className="break-words">{rating.comment}</dd>
              </>
            ) : null}
          </dl>
          {editable ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" onClick={() => setEditing(true)}>
                Edit review
              </Button>
              <span className="text-small text-muted-foreground">
                You can edit it until <span className="num">{formatDateTime(rating.editable_until)}</span>.
              </span>
            </div>
          ) : null}
        </div>
      )}
    </section>
  )
}
