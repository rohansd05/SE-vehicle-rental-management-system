import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, X } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { addArea, type AdminBranch, createBranch, listBranches, removeArea, updateBranch } from '@/api/admin'
import { ApiError } from '@/api/client'
import { Field, FormAlert, StatusMessage, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { FORM, FORM_INDENT } from '@/lib/layout'
import { cn } from '@/lib/utils'

import { BRANCHES_KEY } from './keys'

const message = (error: unknown) => (error instanceof Error ? error.message : 'Something went wrong.')

/** Name and address: adding a branch, or editing one. */
function BranchForm({
  idPrefix,
  branch,
  submitLabel,
  onSaved,
}: {
  idPrefix: string
  branch?: AdminBranch
  submitLabel: string
  onSaved: (note: string) => void
}) {
  const [name, setName] = useState(branch?.branch_name ?? '')
  const [address, setAddress] = useState(branch?.address ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim() || !address.trim()) {
      setError('Enter the branch name and address.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const data = { branch_name: name.trim(), address: address.trim() }
      const saved = branch ? await updateBranch(branch.branch_id, data) : await createBranch(data)
      if (!branch) {
        setName('')
        setAddress('')
      }
      onSaved(`${saved.branch_name} saved.`)
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form noValidate onSubmit={submit} className={FORM}>
      <FormAlert message={error} />
      <Field id={`${idPrefix}-name`} label="Branch name">
        <Input id={`${idPrefix}-name`} value={name} onChange={(event) => setName(event.target.value)} />
      </Field>
      <Field id={`${idPrefix}-address`} label="Address">
        <Textarea id={`${idPrefix}-address`} rows={2} value={address} onChange={(event) => setAddress(event.target.value)} />
      </Field>
      <div className={FORM_INDENT}>
        <SubmitButton busy={busy} busyLabel="Saving…">
          {submitLabel}
        </SubmitButton>
      </div>
    </form>
  )
}

/** Book.Deliver.Location: the pincodes and localities a branch serves. */
function Areas({ branch, onChanged }: { branch: AdminBranch; onChanged: (note: string) => void }) {
  const [pincode, setPincode] = useState('')
  const [locality, setLocality] = useState('')
  const [error, setError] = useState<string | null>(null)
  const id = `areas-${branch.branch_id}`
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await addArea(branch.branch_id, { pincode: pincode.trim(), locality: locality.trim() })
      setPincode('')
      setLocality('')
      onChanged(`Area ${pincode.trim()} added to ${branch.branch_name}.`)
    } catch (failure) {
      setError(failure instanceof ApiError ? Object.values(failure.fieldErrors).flat().join(' ') || failure.message : message(failure))
    }
  }
  return (
    <div className="grid gap-3">
      <h3 className="text-sm font-medium">Serviceable areas</h3>
      {branch.serviceable_areas.length ? (
        <ul aria-label={`Serviceable areas of ${branch.branch_name}`} className="flex flex-wrap gap-2">
          {branch.serviceable_areas.map((area) => (
            <li key={area.id} className="flex items-center gap-1 rounded-md border px-2 py-1 text-sm">
              <span className="num">{area.pincode}</span> {area.locality}
              <Button
                variant="ghost"
                size="xs"
                onClick={() =>
                  void removeArea(branch.branch_id, area.id)
                    .then(() => onChanged(`Area ${area.pincode} removed.`))
                    .catch((failure: unknown) => setError(message(failure)))
                }
              >
                <X aria-hidden="true" />
                <span className="sr-only">Remove {area.pincode} {area.locality}</span>
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">No serviceable areas yet.</p>
      )}
      <form noValidate onSubmit={submit} className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <label htmlFor={`${id}-pincode`} className="text-sm font-medium">
            Pincode
          </label>
          <Input id={`${id}-pincode`} className="w-32" inputMode="numeric" value={pincode} onChange={(event) => setPincode(event.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor={`${id}-locality`} className="text-sm font-medium">
            Locality
          </label>
          <Input id={`${id}-locality`} className="w-56" value={locality} onChange={(event) => setLocality(event.target.value)} />
        </div>
        <Button type="submit" variant="outline">
          Add area
        </Button>
      </form>
      <FormAlert message={error} />
    </div>
  )
}

/** UC 11: the branches, their addresses and serviceable areas. */
export function BranchesPage() {
  const queryClient = useQueryClient()
  const [note, setNote] = useState<string | null>(null)
  const branches = useQuery({ queryKey: BRANCHES_KEY, queryFn: listBranches })
  const changed = (text: string) => {
    void queryClient.invalidateQueries({ queryKey: BRANCHES_KEY })
    setNote(text)
  }

  return (
    <section>
      <Button asChild variant="ghost" className="mb-2 -ml-2 h-10">
        <Link to="/app/fleet">
          <ArrowLeft aria-hidden="true" />
          Back to the fleet
        </Link>
      </Button>
      <PageHeader
        title="Branches"
        photo="band-bookings-1"
        variant="compact"
        description="Each branch's address and the areas it delivers to. Changes are recorded in the audit log."
      />
      <div className="mb-6">
        <StatusMessage message={note} tone="success" />
      </div>
      {branches.isPending ? (
        <LoadingState label="Loading the branches…" rows={3} />
      ) : branches.isError ? (
        <ErrorState title="We couldn’t load the branches" error={branches.error} onRetry={() => void branches.refetch()} />
      ) : (
        <div className="grid gap-10">
          {branches.data.length === 0 ? <EmptyState title="No branches yet" description="Add the first branch below." /> : null}
          {branches.data.map((branch) => (
            <section key={branch.branch_id} aria-labelledby={`branch-${branch.branch_id}`} className="grid gap-5 border-t pt-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-10">
              <div className="grid content-start gap-3">
                <h2 id={`branch-${branch.branch_id}`} className="text-section">
                  {branch.branch_name}
                </h2>
                <p className="text-sm text-muted-foreground">{branch.vehicle_count} vehicles</p>
                <BranchForm idPrefix={`branch-${branch.branch_id}`} branch={branch} submitLabel="Save branch" onSaved={changed} />
              </div>
              <Areas branch={branch} onChanged={changed} />
            </section>
          ))}
          <section aria-labelledby="branch-new" className={cn('grid gap-4 border-t pt-6')}>
            <h2 id="branch-new" className="text-section">
              Add a branch
            </h2>
            <BranchForm idPrefix="branch-new" submitLabel="Add branch" onSaved={changed} />
          </section>
        </div>
      )}
    </section>
  )
}
