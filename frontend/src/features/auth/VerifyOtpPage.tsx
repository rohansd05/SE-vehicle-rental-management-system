import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useLocation, useNavigate } from 'react-router-dom'

import { resendOtp, verifyOtp } from '@/api/auth'
import { ApiError } from '@/api/client'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useCountdown } from '@/hooks/countdown'
import { now } from '@/lib/dates'
import { describedBy } from '@/lib/form'

import { OTP_MESSAGES } from './messages'
import {
  OTP_LENGTH,
  OTP_LIFETIME_MS,
  OTP_MAX_ATTEMPTS,
  OTP_RESEND_COOLDOWN_SECONDS,
  type OtpValues,
  otpSchema,
} from './schemas'

interface VerifyState {
  email?: string
  mobile?: string
  sentAt?: number
}


/**
 * SE-7: confirm the mobile number with the SMS code. The server answers
 * every failure the same way; this screen knows when the code was sent and
 * how many tries were made, so it can say which case applies.
 */
export function VerifyOtpPage() {
  const navigate = useNavigate()
  const state = (useLocation().state ?? {}) as VerifyState
  const [email, setEmail] = useState(state.email ?? '')
  const [sentAt, setSentAt] = useState<number | null>(state.sentAt ?? null)
  const [failures, setFailures] = useState(0)
  const [formError, setFormError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [resending, setResending] = useState(false)
  const [remaining, restartCountdown] = useCountdown(
    state.sentAt ? OTP_RESEND_COOLDOWN_SECONDS : 0,
  )

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<OtpValues>({ resolver: zodResolver(otpSchema) })

  const codeIsDead = failures >= OTP_MAX_ATTEMPTS
  const isExpired = () => sentAt !== null && now() - sentAt > OTP_LIFETIME_MS

  const onSubmit = handleSubmit(async ({ code }) => {
    setStatus(null)
    if (!email) {
      setFormError('Enter the e-mail address you registered with.')
      return
    }
    if (isExpired()) {
      setFormError(OTP_MESSAGES.expired)
      return
    }
    setFormError(null)
    try {
      await verifyOtp(email, code)
      navigate('/login', { state: { verifiedEmail: email } })
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 400) {
        setFormError(error instanceof Error ? error.message : 'Something went wrong.')
        return
      }
      if (isExpired()) {
        setFormError(OTP_MESSAGES.expired)
        return
      }
      const next = failures + 1
      setFailures(next)
      if (sentAt === null) setFormError(error.message)
      else if (next >= OTP_MAX_ATTEMPTS) setFormError(OTP_MESSAGES.tooMany)
      else setFormError(OTP_MESSAGES.wrong(OTP_MAX_ATTEMPTS - next))
    }
  })

  const onResend = async () => {
    if (!email) {
      setFormError('Enter the e-mail address you registered with.')
      return
    }
    setResending(true)
    setFormError(null)
    try {
      await resendOtp(email)
      setSentAt(now())
      setFailures(0)
      reset()
      restartCountdown(OTP_RESEND_COOLDOWN_SECONDS)
      setStatus('A new code is on its way. The previous code no longer works.')
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        restartCountdown(error.retryAfterSeconds ?? OTP_RESEND_COOLDOWN_SECONDS)
        setStatus('Please wait before asking for another code.')
      } else {
        setFormError(error instanceof Error ? error.message : 'Something went wrong.')
      }
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <PageHeader
        title="Verify your mobile number"
        description={
          state.mobile
            ? `Enter the ${OTP_LENGTH}-digit code we sent by SMS to ${state.mobile}.`
            : `Enter the ${OTP_LENGTH}-digit code we sent to your mobile by SMS.`
        }
      />
      <Card>
        <CardContent className="grid gap-4">
          <FormAlert message={formError} />
          <StatusMessage message={status} />
          <form onSubmit={onSubmit} noValidate className="grid gap-4">
            {state.email ? null : (
              <Field id="verify-email" label="E-mail you registered with">
                <Input
                  id="verify-email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </Field>
            )}
            <Field
              id="code"
              label="Verification code"
              hint="The code is valid for 10 minutes."
              error={errors.code?.message}
            >
              <Input
                id="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={OTP_LENGTH}
                className="h-11 max-w-48 text-center font-mono text-lg tracking-[0.4em]"
                aria-invalid={errors.code ? true : undefined}
                aria-describedby={describedBy('code', { hint: true, error: Boolean(errors.code) })}
                {...register('code')}
              />
            </Field>
            <SubmitButton busy={isSubmitting} busyLabel="Checking…" disabled={codeIsDead}>
              Verify
            </SubmitButton>
          </form>
          <div className="flex flex-wrap items-center gap-2 border-t pt-4 text-sm">
            <span className="text-muted-foreground">Didn’t get it?</span>
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={() => void onResend()}
              disabled={remaining > 0 || resending}
            >
              {remaining > 0 ? `Send a new code in ${remaining} s` : 'Send a new code'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
