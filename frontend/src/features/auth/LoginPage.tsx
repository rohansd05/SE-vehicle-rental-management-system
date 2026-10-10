import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, type Location, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { describedBy } from '@/lib/form'

import { useAuth } from './auth-context'
import { LOCKED_MESSAGE, SIGN_OUT_MESSAGES } from './messages'
import { type LoginValues, loginSchema } from './schemas'

interface LoginState {
  from?: Location
  verifiedEmail?: string
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const state = (location.state ?? {}) as LoginState
  const { signIn, signOutReason } = useAuth()
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: state.verifiedEmail ?? '', password: '' },
  })

  const onSubmit = handleSubmit(async ({ email, password }) => {
    setFormError(null)
    try {
      await signIn(email, password)
      const from = state.from
      navigate(from ? `${from.pathname}${from.search}` : '/app', { replace: true })
    } catch (error) {
      if (error instanceof ApiError && error.status === 403 && error.code === 'account_locked') {
        setFormError(LOCKED_MESSAGE) // SE-8
      } else {
        // 401: the server's generic message, the same for an unknown,
        // unverified or disabled account (SE-8, A9).
        setFormError(error instanceof Error ? error.message : 'Something went wrong.')
      }
    }
  })

  const notice = state.verifiedEmail
    ? 'Your account is verified. Sign in to continue.'
    : signOutReason && signOutReason !== 'signed-out'
      ? SIGN_OUT_MESSAGES[signOutReason]
      : null

  return (
    <div className="mx-auto max-w-md">
      <PageHeader title="Sign in" />
      <Card>
        <CardContent>
          <form onSubmit={onSubmit} noValidate className="grid gap-4">
            <StatusMessage message={notice} tone={state.verifiedEmail ? 'success' : 'info'} />
            <FormAlert message={formError} />
            <Field id="email" label="E-mail" error={errors.email?.message}>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                aria-invalid={errors.email ? true : undefined}
                aria-describedby={describedBy('email', { error: Boolean(errors.email) })}
                {...register('email')}
              />
            </Field>
            <Field id="password" label="Password" error={errors.password?.message}>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={errors.password ? true : undefined}
                aria-describedby={describedBy('password', { error: Boolean(errors.password) })}
                {...register('password')}
              />
            </Field>
            <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                New here?{' '}
                <Link to="/register" className="font-medium text-primary underline-offset-4 hover:underline">
                  Create an account
                </Link>
              </p>
              <SubmitButton busy={isSubmitting} busyLabel="Signing in…">
                Sign in
              </SubmitButton>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
