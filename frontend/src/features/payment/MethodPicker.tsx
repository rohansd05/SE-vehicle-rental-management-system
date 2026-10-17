import { Field } from '@/components/form'
import { Input } from '@/components/ui/input'
import { describedBy } from '@/lib/form'

import { CHANNELS, type Method, type MethodChoice, ONLINE_TOKENS, TEST_TOKENS } from './method'

const ROW = 'flex min-h-14 items-center gap-3 text-sm'

function Radios<T extends string>({
  name,
  options,
  value,
  onChange,
}: {
  name: string
  options: readonly { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div className="divide-y border-y">
      {options.map((option) => (
        <label key={option.value} className={ROW}>
          <input
            type="radio"
            name={name}
            value={option.value}
            className="size-4"
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
          {option.label}
        </label>
      ))}
    </div>
  )
}

/**
 * Pay.Method: card, on-line transfer or wallet, or (for a booking collected
 * at a branch) cash at the time of collection (BR-9).
 */
export function MethodPicker({
  value,
  onChange,
  allowCash,
  cashNote,
  upiError,
}: {
  value: MethodChoice
  onChange: (next: MethodChoice) => void
  allowCash: boolean
  cashNote?: string
  upiError?: string
}) {
  const set = (patch: Partial<MethodChoice>) => onChange({ ...value, ...patch })
  const methods: { value: Method; label: string }[] = [
    { value: 'card', label: 'Card' },
    { value: 'online', label: 'UPI, net banking or wallet' },
    ...(allowCash ? [{ value: 'cash' as const, label: 'Cash when I collect the vehicle' }] : []),
  ]
  return (
    <div className="grid gap-6">
      <fieldset className="grid gap-1">
        <legend className="heading text-section">How would you like to pay?</legend>
        <Radios name="method" options={methods} value={value.method} onChange={(method) => set({ method })} />
      </fieldset>
      {value.method === 'card' ? (
        <fieldset className="grid gap-1">
          <legend className="heading text-section">Payment method (sandbox)</legend>
          <p className="mb-2 text-small text-muted-foreground">
            This is the test mode: no real money moves and no card details are entered here.
          </p>
          <Radios name="payment_token" options={TEST_TOKENS} value={value.cardToken} onChange={(cardToken) => set({ cardToken })} />
        </fieldset>
      ) : null}
      {value.method === 'online' ? (
        <fieldset className="grid gap-4">
          <legend className="heading text-section">Online transfer or wallet (sandbox)</legend>
          <p className="text-small text-muted-foreground">
            This is the test mode: no real money moves. A live payment would continue on the provider’s own page.
          </p>
          <Radios name="channel" options={CHANNELS} value={value.channel} onChange={(channel) => set({ channel })} />
          {value.channel === 'UPI' ? (
            <Field id="upi-id" label="UPI ID (optional)" hint="For example name@bank." error={upiError} className="max-w-sm">
              <Input
                id="upi-id"
                value={value.upiId}
                autoComplete="off"
                aria-invalid={upiError ? true : undefined}
                aria-describedby={describedBy('upi-id', { hint: true, error: Boolean(upiError) })}
                onChange={(event) => set({ upiId: event.target.value })}
              />
            </Field>
          ) : null}
          <Radios name="online_token" options={ONLINE_TOKENS} value={value.onlineToken} onChange={(onlineToken) => set({ onlineToken })} />
        </fieldset>
      ) : null}
      {value.method === 'cash' && cashNote ? <p className="max-w-prose text-sm text-muted-foreground">{cashNote}</p> : null}
    </div>
  )
}
