import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'

import { register as registerAccount } from '@/api/auth'
import { Field, FormAlert, SubmitButton } from '@/components/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { now, todayISO } from '@/lib/dates'
import { applyServerErrors, describedBy } from '@/lib/form'

import { AuthLayout } from './AuthLayout'
import {
  MOBILE_HINT,
  PASSWORD_RULES,
  type RegisterValues,
  registerSchema,
} from './schemas'

const SERVER_FIELDS = [
  'name',
  'email',
  'mobile_no',
  'address',
  'date_of_birth',
  'emergency_contact_name',
  'emergency_contact_mobile',
  'password',
] as const

/** Customer self-registration (SE-7). Staff accounts are created by an administrator. */
export function RegisterPage() {
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema), mode: 'onBlur' })

  const onSubmit = handleSubmit(async ({ confirm_password: _confirm, ...values }) => {
    setFormError(null)
    try {
      const response = await registerAccount(values)
      navigate('/verify', {
        state: { email: response.email, mobile: values.mobile_no, sentAt: now() },
      })
    } catch (error) {
      setFormError(applyServerErrors(error, setError, SERVER_FIELDS))
    }
  })

  const field = (name: keyof RegisterValues, hint = false) => ({
    id: name,
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': describedBy(name, { hint, error: Boolean(errors[name]) }),
    ...register(name),
  })

  return (
    <AuthLayout
      title="Create your account"
      description="We'll send a code to your mobile number to confirm it's yours."
      wide
    >
      <form onSubmit={onSubmit} noValidate className="grid gap-5">
        <FormAlert message={formError} />

        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="name" label="Full name" error={errors.name?.message}>
            <Input autoComplete="name" {...field('name')} />
          </Field>
          <Field id="email" label="E-mail" error={errors.email?.message}>
            <Input type="email" autoComplete="email" {...field('email')} />
          </Field>
          <Field id="mobile_no" label="Mobile number" hint={MOBILE_HINT} error={errors.mobile_no?.message}>
            <Input type="tel" inputMode="tel" autoComplete="tel" {...field('mobile_no', true)} />
          </Field>
          <Field
            id="date_of_birth"
            label="Date of birth"
            hint="You must be 18 to rent a two-wheeler and 21 to rent a car."
            error={errors.date_of_birth?.message}
          >
            <Input type="date" max={todayISO()} autoComplete="bday" {...field('date_of_birth', true)} />
          </Field>
        </div>
        <Field id="address" label="Address" error={errors.address?.message}>
          <Textarea autoComplete="street-address" rows={3} {...field('address')} />
        </Field>

        <fieldset className="grid gap-5 border-t pt-5">
          <legend className="float-left mb-4 font-heading text-section font-semibold">
            Emergency contact
          </legend>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field
              id="emergency_contact_name"
              label="Name"
              error={errors.emergency_contact_name?.message}
            >
              <Input autoComplete="off" {...field('emergency_contact_name')} />
            </Field>
            <Field
              id="emergency_contact_mobile"
              label="Mobile number"
              hint={MOBILE_HINT}
              error={errors.emergency_contact_mobile?.message}
            >
              <Input type="tel" inputMode="tel" autoComplete="off" {...field('emergency_contact_mobile', true)} />
            </Field>
          </div>
        </fieldset>

        <div className="grid gap-5 border-t pt-5 sm:grid-cols-2">
          <Field
            id="password"
            label="Password"
            hint={
              <span>
                Your password must be:
                <ul className="mt-1 list-disc pl-5">
                  {PASSWORD_RULES.map((rule) => (
                    <li key={rule}>{rule}</li>
                  ))}
                </ul>
              </span>
            }
            error={errors.password?.message}
          >
            <Input type="password" autoComplete="new-password" {...field('password', true)} />
          </Field>
          <Field id="confirm_password" label="Confirm password" error={errors.confirm_password?.message}>
            <Input type="password" autoComplete="new-password" {...field('confirm_password')} />
          </Field>
        </div>

        <div className="flex flex-col-reverse gap-4 border-t pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            Already registered?{' '}
            <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
              Sign in
            </Link>
          </p>
          <SubmitButton busy={isSubmitting} busyLabel="Creating your account…">
            Create account
          </SubmitButton>
        </div>
      </form>
    </AuthLayout>
  )
}
