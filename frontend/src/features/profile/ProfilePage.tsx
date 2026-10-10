import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { changePassword, confirmMobile, getProfile, updateProfile } from '@/api/auth'
import { ApiError } from '@/api/client'
import { type Profile, ROLE_LABELS } from '@/api/types'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/features/auth/auth-context'
import { MOBILE_HINT, OTP_LENGTH, OTP_RESEND_COOLDOWN_SECONDS, PASSWORD_RULES } from '@/features/auth/schemas'
import { useCountdown } from '@/hooks/countdown'
import { applyServerErrors, describedBy } from '@/lib/form'

import {
  type DetailsValues,
  detailsSchema,
  type MobileCodeValues,
  mobileCodeSchema,
  type MobileValues,
  mobileSchema,
  type PasswordValues,
  passwordSchema,
} from './schemas'

const PROFILE_KEY = ['profile'] as const

export function ProfilePage() {
  const profile = useQuery({ queryKey: PROFILE_KEY, queryFn: getProfile })

  return (
    <section>
      <PageHeader title="My profile" description="Your details, mobile number and password." />
      {profile.isPending ? (
        <LoadingState label="Loading your profile…" />
      ) : profile.isError ? (
        <ErrorState title="We couldn’t load your profile" error={profile.error} onRetry={() => void profile.refetch()} />
      ) : (
        <div className="grid gap-6">
          <DetailsCard profile={profile.data} />
          <MobileCard profile={profile.data} />
          <PasswordCard />
        </div>
      )}
    </section>
  )
}

function DetailsCard({ profile }: { profile: Profile }) {
  const queryClient = useQueryClient()
  const { updateUser } = useAuth()
  const [editing, setEditing] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<DetailsValues>({
    resolver: zodResolver(detailsSchema),
    values: { name: profile.name, address: profile.address },
  })

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      const updated = await updateProfile(values)
      queryClient.setQueryData<Profile>(PROFILE_KEY, (current) =>
        current ? { ...current, name: updated.name, address: updated.address } : current,
      )
      updateUser({ name: updated.name })
      setEditing(false)
      setSaved('Your details have been saved.')
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ['name', 'address']))
    }
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Your details</h2>
        </CardTitle>
        <CardDescription>Your e-mail address identifies your account and cannot be changed here.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <StatusMessage message={saved} tone="success" />
        {editing ? (
          <form onSubmit={onSubmit} noValidate className="grid gap-4">
            <FormAlert message={formError} />
            <Field id="profile-name" label="Full name" error={errors.name?.message}>
              <Input
                id="profile-name"
                autoComplete="name"
                aria-invalid={errors.name ? true : undefined}
                aria-describedby={describedBy('profile-name', { error: Boolean(errors.name) })}
                {...register('name')}
              />
            </Field>
            <Field id="profile-address" label="Address" error={errors.address?.message}>
              <Textarea
                id="profile-address"
                rows={3}
                autoComplete="street-address"
                aria-invalid={errors.address ? true : undefined}
                aria-describedby={describedBy('profile-address', { error: Boolean(errors.address) })}
                {...register('address')}
              />
            </Field>
            <div className="flex flex-col gap-2 sm:flex-row">
              <SubmitButton busy={isSubmitting} busyLabel="Saving…">
                Save details
              </SubmitButton>
              <Button
                type="button"
                variant="outline"
                size="lg"
                className="h-10"
                onClick={() => {
                  reset()
                  setFormError(null)
                  setEditing(false)
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <>
            <dl className="grid gap-3 text-sm sm:grid-cols-[10rem_1fr]">
              <dt className="text-muted-foreground">Name</dt>
              <dd className="font-medium">{profile.name}</dd>
              <dt className="text-muted-foreground">E-mail</dt>
              <dd className="font-medium break-all">{profile.email}</dd>
              <dt className="text-muted-foreground">Address</dt>
              <dd className="font-medium whitespace-pre-line">{profile.address || '—'}</dd>
              <dt className="text-muted-foreground">Account type</dt>
              <dd className="font-medium">{ROLE_LABELS[profile.role]}</dd>
            </dl>
            <div>
              <Button
                variant="outline"
                size="lg"
                className="h-10"
                onClick={() => {
                  setSaved(null)
                  setEditing(true)
                }}
              >
                Edit details
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

/** SE-7, A10: a new number is used only after the code sent to it is confirmed. */
function MobileCard({ profile }: { profile: Profile }) {
  const queryClient = useQueryClient()
  const [pendingMobile, setPendingMobile] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [remaining, restartCountdown] = useCountdown(0)

  const numberForm = useForm<MobileValues>({ resolver: zodResolver(mobileSchema) })
  const codeForm = useForm<MobileCodeValues>({ resolver: zodResolver(mobileCodeSchema) })

  const requestCode = async (mobile: string) => {
    setFormError(null)
    try {
      const response = await updateProfile({ mobile_no: mobile })
      if (!response.mobile_change_pending) {
        setStatus('That is already your mobile number.')
        return
      }
      setPendingMobile(mobile)
      restartCountdown(OTP_RESEND_COOLDOWN_SECONDS)
      setStatus(`We sent a ${OTP_LENGTH}-digit code to ${mobile}. It is valid for 10 minutes.`)
    } catch (error) {
      setFormError(applyServerErrors(error, numberForm.setError, ['mobile_no']))
    }
  }

  const onRequest = numberForm.handleSubmit(({ mobile_no }) => requestCode(mobile_no))

  const onConfirm = codeForm.handleSubmit(async ({ code }) => {
    setFormError(null)
    try {
      const updated = await confirmMobile(code)
      queryClient.setQueryData<Profile>(PROFILE_KEY, updated)
      setPendingMobile(null)
      numberForm.reset({ mobile_no: '' })
      codeForm.reset()
      setStatus('Your mobile number has been changed.')
    } catch (error) {
      setFormError(
        error instanceof ApiError && error.status === 400
          ? 'That code is wrong or has expired. Check it, or send a new code.'
          : error instanceof Error
            ? error.message
            : 'Something went wrong.',
      )
    }
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Mobile number</h2>
        </CardTitle>
        <CardDescription>
          Current number: <span className="font-medium text-foreground">{profile.mobile_no}</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <FormAlert message={formError} />
        <StatusMessage message={status} tone={pendingMobile ? 'info' : 'success'} />
        {pendingMobile ? (
          // Distinct keys: React must not reuse the number input as the code input.
          <form key="confirm-code" onSubmit={onConfirm} noValidate className="grid gap-4">
            <Field
              id="mobile-code"
              label={`Code sent to ${pendingMobile}`}
              error={codeForm.formState.errors.code?.message}
            >
              <Input
                id="mobile-code"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={OTP_LENGTH}
                className="h-11 max-w-48 text-center font-mono text-lg tracking-[0.4em]"
                aria-invalid={codeForm.formState.errors.code ? true : undefined}
                aria-describedby={describedBy('mobile-code', {
                  error: Boolean(codeForm.formState.errors.code),
                })}
                {...codeForm.register('code')}
              />
            </Field>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              <SubmitButton busy={codeForm.formState.isSubmitting} busyLabel="Checking…">
                Confirm new number
              </SubmitButton>
              <Button
                type="button"
                variant="outline"
                size="lg"
                className="h-10"
                disabled={remaining > 0}
                onClick={() => void requestCode(pendingMobile)}
              >
                {remaining > 0 ? `Send a new code in ${remaining} s` : 'Send a new code'}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="lg"
                className="h-10"
                onClick={() => {
                  setPendingMobile(null)
                  setStatus(null)
                  setFormError(null)
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <form key="request-code" onSubmit={onRequest} noValidate className="grid gap-4">
            <Field
              id="new-mobile"
              label="New mobile number"
              hint={`${MOBILE_HINT} We’ll send a code to the new number to confirm it.`}
              error={numberForm.formState.errors.mobile_no?.message}
            >
              <Input
                id="new-mobile"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                aria-invalid={numberForm.formState.errors.mobile_no ? true : undefined}
                aria-describedby={describedBy('new-mobile', {
                  hint: true,
                  error: Boolean(numberForm.formState.errors.mobile_no),
                })}
                {...numberForm.register('mobile_no')}
              />
            </Field>
            <SubmitButton busy={numberForm.formState.isSubmitting} busyLabel="Sending code…">
              Send code
            </SubmitButton>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

/** A11: a successful change ends every session, this one included. */
function PasswordCard() {
  const { signOut } = useAuth()
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<PasswordValues>({ resolver: zodResolver(passwordSchema) })

  const onSubmit = handleSubmit(async ({ current_password, new_password }) => {
    setFormError(null)
    try {
      await changePassword({ current_password, new_password })
      // The server has revoked every session; leave and explain on sign-in.
      await signOut('password-changed')
    } catch (error) {
      if (error instanceof ApiError && error.fieldErrors.password) {
        setError('new_password', { type: 'server', message: error.fieldErrors.password.join(' ') }, { shouldFocus: true })
        return
      }
      setFormError(applyServerErrors(error, setError, ['current_password', 'new_password']))
    }
  })

  const field = (name: keyof PasswordValues, hint = false) => ({
    id: name,
    type: 'password' as const,
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': describedBy(name, { hint, error: Boolean(errors[name]) }),
    ...register(name),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Password</h2>
        </CardTitle>
        <CardDescription>
          Changing your password signs you out on every device, including this one.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="grid gap-4">
          <FormAlert message={formError} />
          <Field id="current_password" label="Current password" error={errors.current_password?.message}>
            <Input autoComplete="current-password" {...field('current_password')} />
          </Field>
          <Field
            id="new_password"
            label="New password"
            hint={`Your password must be: ${PASSWORD_RULES.join(' ')}`}
            error={errors.new_password?.message}
          >
            <Input autoComplete="new-password" {...field('new_password', true)} />
          </Field>
          <Field id="confirm_password" label="Confirm new password" error={errors.confirm_password?.message}>
            <Input autoComplete="new-password" {...field('confirm_password')} />
          </Field>
          <SubmitButton busy={isSubmitting} busyLabel="Changing password…">
            Change password
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  )
}
