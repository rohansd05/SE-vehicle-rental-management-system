import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ShieldCheck } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { type Path, useForm, useWatch } from 'react-hook-form'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import {
  createStaff,
  getStaff,
  listBranches,
  setStaffActive,
  setUnsafeAuthorisation,
  STAFF_ROLES,
  type StaffAccount,
  updateStaff,
} from '@/api/admin'
import { ROLE_LABELS } from '@/api/types'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { StickyRail } from '@/components/sticky-rail'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { formatDateTime } from '@/lib/dates'
import { applyServerErrors, describedBy } from '@/lib/form'
import { DETAILS_LIST, FORM, FORM_INDENT, RAIL_LAYOUT } from '@/lib/layout'
import { cn } from '@/lib/utils'

import { BRANCHES_KEY, STAFF_KEY, staffKey } from './keys'
import { ReasonDialog } from './ReasonDialog'
import { type StaffValues, staffSchema } from './schemas'
import { ActiveBadge } from './UsersPage'

const FIELDS = ['role', 'name', 'email', 'mobile_no', 'address', 'branch', 'workshop', 'password'] as const

function BackToUsers() {
  return (
    <Button asChild variant="ghost" className="mb-2 -ml-2 h-10">
      <Link to="/app/users">
        <ArrowLeft aria-hidden="true" />
        Back to users
      </Link>
    </Button>
  )
}

/** Fleet.Users (UC 12 step 1): a Branch Staff, Technician or Branch Manager account. */
export function StaffFormPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const branches = useQuery({ queryKey: BRANCHES_KEY, queryFn: listBranches })
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors },
  } = useForm<StaffValues>({
    resolver: zodResolver(staffSchema),
    defaultValues: { name: '', email: '', mobile_no: '', address: '', branch: '', workshop: '', password: '' },
  })
  const role = useWatch({ control, name: 'role' })
  const save = useMutation({
    mutationFn: (values: StaffValues) =>
      createStaff({
        ...values,
        branch: values.role === 'MAINTENANCE_TECHNICIAN' ? null : Number(values.branch),
        workshop: values.role === 'MAINTENANCE_TECHNICIAN' ? values.workshop : '',
      }),
    onSuccess: async (account) => {
      await queryClient.invalidateQueries({ queryKey: STAFF_KEY })
      navigate(`/app/users/${account.id}`, {
        state: { flash: `${ROLE_LABELS[account.role]} account created for ${account.name}. They can sign in now.` },
      })
    },
    onError: (error) => setFormError(applyServerErrors(error, setError, FIELDS)),
  })

  const field = (name: Path<StaffValues>, label: string, control: ReactNode, hint?: string) => (
    <Field id={`staff-${name}`} label={label} hint={hint} error={errors[name]?.message}>
      {control}
    </Field>
  )
  const props = (name: Path<StaffValues>, hint = false) => ({
    id: `staff-${name}`,
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': describedBy(`staff-${name}`, { hint, error: Boolean(errors[name]) }),
    ...register(name),
  })

  return (
    <section>
      <BackToUsers />
      <PageHeader
        title="Add a staff account"
        photo="band-licence-checks-1"
        variant="compact"
        description="Branch Staff and Branch Managers work for one branch; a technician for a workshop. The account can sign in at once."
      />
      <form
        noValidate
        className={cn(FORM, 'max-w-4xl')}
        onSubmit={handleSubmit((values) => {
          setFormError(null)
          save.mutate(values)
        })}
      >
        <FormAlert message={formError} />
        {field(
          'role',
          'Role',
          <NativeSelect defaultValue="" {...props('role')}>
            <option value="" disabled>
              Choose a role
            </option>
            {STAFF_ROLES.map((value) => (
              <option key={value} value={value}>
                {ROLE_LABELS[value]}
              </option>
            ))}
          </NativeSelect>,
        )}
        {field('name', 'Full name', <Input autoComplete="off" {...props('name')} />)}
        <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
          {field('email', 'E-mail', <Input type="email" autoComplete="off" {...props('email')} />)}
          {field('mobile_no', 'Mobile number', <Input type="tel" inputMode="tel" {...props('mobile_no')} />)}
        </div>
        {field('address', 'Address', <Textarea rows={2} {...props('address')} />)}
        {role === 'MAINTENANCE_TECHNICIAN'
          ? field('workshop', 'Workshop', <Input {...props('workshop')} />)
          : field(
              'branch',
              'Branch',
              <NativeSelect {...props('branch')}>
                <option value="">Choose a branch</option>
                {(branches.data ?? []).map((branch) => (
                  <option key={branch.branch_id} value={branch.branch_id}>
                    {branch.branch_name}
                  </option>
                ))}
              </NativeSelect>,
            )}
        {field(
          'password',
          'First password',
          <Input type="password" autoComplete="new-password" {...props('password', true)} />,
          'Give it to the person; they can change it after signing in. It is never shown again.',
        )}
        <div className={FORM_INDENT}>
          <SubmitButton busy={save.isPending} busyLabel="Creating…">
            Create account
          </SubmitButton>
        </div>
      </form>
    </section>
  )
}

type EditValues = { name: string; email: string; mobile_no: string; address: string; branch: string; workshop: string }

function EditStaff({ account, onSaved }: { account: StaffAccount; onSaved: (next: StaffAccount) => void }) {
  const branches = useQuery({ queryKey: BRANCHES_KEY, queryFn: listBranches })
  const [formError, setFormError] = useState<string | null>(null)
  const technician = account.role === 'MAINTENANCE_TECHNICIAN'
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<EditValues>({
    defaultValues: {
      name: account.name,
      email: account.email,
      mobile_no: account.mobile_no,
      address: account.address,
      branch: account.branch === null ? '' : String(account.branch),
      workshop: account.workshop ?? '',
    },
  })
  const save = useMutation({
    mutationFn: (values: EditValues) => {
      const { branch, workshop, ...rest } = values
      return updateStaff(account.id, technician ? { ...rest, workshop } : { ...rest, branch: Number(branch) })
    },
    onSuccess: onSaved,
    onError: (error) => setFormError(applyServerErrors(error, setError, ['name', 'email', 'mobile_no', 'address', 'branch', 'workshop'])),
  })
  const text = (name: keyof EditValues, label: string, control?: ReactNode) => (
    <Field id={`edit-${name}`} label={label} error={errors[name]?.message}>
      {control ?? <Input id={`edit-${name}`} aria-invalid={errors[name] ? true : undefined} {...register(name)} />}
    </Field>
  )
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Account details</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form
          noValidate
          className={FORM}
          onSubmit={handleSubmit((values) => {
            setFormError(null)
            save.mutate(values)
          })}
        >
          <FormAlert message={formError} />
          {text('name', 'Full name')}
          <div className="grid gap-5 @lg/form:grid-cols-2 @3xl/form:grid-cols-1">
            {text('email', 'E-mail')}
            {text('mobile_no', 'Mobile number')}
          </div>
          {text('address', 'Address', <Textarea id="edit-address" rows={2} {...register('address')} />)}
          {technician
            ? text('workshop', 'Workshop')
            : text(
                'branch',
                'Branch',
                <NativeSelect id="edit-branch" {...register('branch')}>
                  {(branches.data ?? [{ branch_id: account.branch ?? 0, branch_name: account.branch_name ?? '' }]).map((branch) => (
                    <option key={branch.branch_id} value={branch.branch_id}>
                      {branch.branch_name}
                    </option>
                  ))}
                </NativeSelect>,
              )}
          <div className={FORM_INDENT}>
            <SubmitButton busy={save.isPending} busyLabel="Saving…">
              Save changes
            </SubmitButton>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

/** One staff account: edit, disable or re-enable (Fleet.Users), and BR-16 for a technician. */
export function StaffPage() {
  const { id } = useParams()
  const accountId = Number(id)
  const location = useLocation()
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string | null>((location.state as { flash?: string } | null)?.flash ?? null)
  const [error, setError] = useState<string | null>(null)
  const account = useQuery({ queryKey: staffKey(accountId), queryFn: () => getStaff(accountId) })

  const changed = (next: StaffAccount | null, note: string) => {
    if (next) queryClient.setQueryData(staffKey(accountId), next)
    else void queryClient.invalidateQueries({ queryKey: staffKey(accountId) })
    void queryClient.invalidateQueries({ queryKey: STAFF_KEY })
    setError(null)
    setMessage(note)
  }

  if (account.isPending || account.isError) {
    return (
      <section>
        <BackToUsers />
        <PageHeader title="Staff account" />
        {account.isPending ? (
          <LoadingState label="Loading the account…" />
        ) : (
          <ErrorState title="We couldn’t load this account" error={account.error} onRetry={() => void account.refetch()} />
        )}
      </section>
    )
  }
  const data = account.data
  const technician = data.role === 'MAINTENANCE_TECHNICIAN'
  return (
    <section>
      <BackToUsers />
      <PageHeader
        title={data.name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <ActiveBadge active={data.is_active} />
            {ROLE_LABELS[data.role]}, {data.branch_name ?? data.workshop}
          </span>
        }
      />
      <div className="mb-6 grid gap-4">
        <StatusMessage message={message} tone="success" />
        <FormAlert message={error} />
      </div>
      <div className={RAIL_LAYOUT}>
        <div className="grid min-w-0 content-start gap-8">
          <EditStaff key={data.id} account={data} onSaved={(next) => changed(next, 'Account saved.')} />
          <div className="@container">
            <dl className={DETAILS_LIST}>
              <dt className="text-muted-foreground">Joined</dt>
              <dd className="font-medium">{formatDateTime(data.date_joined)}</dd>
              <dt className="text-muted-foreground">Last signed in</dt>
              <dd className="font-medium">{formatDateTime(data.last_login)}</dd>
            </dl>
          </div>
        </div>
        <StickyRail>
          <div className="grid gap-6 lg:pt-1">
            {data.is_active ? (
              <ReasonDialog
                id="disable"
                trigger="Disable account"
                variant="destructive"
                title={`Disable ${data.name}'s account?`}
                description="Their sessions end at once and sign-in is refused. What they did before stays on record."
                submitLabel="Disable account"
                busyLabel="Disabling…"
                cancelLabel="Keep it active"
                onConfirm={async (reason) => changed(await setStaffActive(data.id, false, reason), 'Account disabled; every session has ended.')}
              />
            ) : (
              <ReasonDialog
                id="enable"
                trigger="Re-enable account"
                title={`Re-enable ${data.name}'s account?`}
                description="They can sign in again with their password."
                submitLabel="Re-enable account"
                busyLabel="Re-enabling…"
                cancelLabel="Keep it disabled"
                onConfirm={async (reason) => changed(await setStaffActive(data.id, true, reason), 'Account re-enabled.')}
              />
            )}
            {technician && data.technician_id !== null ? (
              <div className="grid gap-3 border-t pt-5">
                <p className="flex items-center gap-2 font-medium">
                  <ShieldCheck className="size-4.5" aria-hidden="true" />
                  {data.authorised_to_clear_unsafe ? 'May clear Unsafe flags' : 'Not authorised to clear Unsafe flags'}
                </p>
                <p className="text-sm text-muted-foreground">
                  An authorised technician may clear a vehicle's Unsafe flag while closing their job, and is recorded
                  (BR-16).
                </p>
                <div>
                  <Button
                    variant="outline"
                    disabled={!data.is_active}
                    onClick={() =>
                      void setUnsafeAuthorisation(data.technician_id as number, !data.authorised_to_clear_unsafe)
                        .then(() =>
                          changed(null, data.authorised_to_clear_unsafe ? 'Authorisation revoked.' : 'Technician authorised to clear Unsafe flags.'),
                        )
                        .catch((failure: unknown) => setError(failure instanceof Error ? failure.message : 'Something went wrong.'))
                    }
                  >
                    {data.authorised_to_clear_unsafe ? 'Revoke authorisation' : 'Authorise to clear Unsafe'}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </StickyRail>
      </div>
    </section>
  )
}
