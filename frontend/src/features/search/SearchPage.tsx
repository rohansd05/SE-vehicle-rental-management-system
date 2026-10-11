import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { Field, FormAlert, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { formatDateTime } from '@/lib/dates'
import { describedBy } from '@/lib/form'

import { listBranches, listCategories, type SearchQuery, searchVehicles } from './api'
import { BRANCHES_KEY, CATEGORIES_KEY, searchKey } from './keys'
import { isoToLocal, localToISO, type SearchValues, searchSchema } from './schema'
import { VehicleResults } from './VehicleResults'

const FIELDS = ['branch', 'category', 'pickup_datetime', 'return_datetime'] as const
type FieldName = (typeof FIELDS)[number]

/** The search kept in the address, so a reload or the back button shows it again. */
function readQuery(params: URLSearchParams): SearchQuery | null {
  const branch = params.get('branch')
  const pickup = params.get('pickup_datetime')
  const ret = params.get('return_datetime')
  if (!branch || !pickup || !ret) return null
  const page = Number(params.get('page') ?? '1')
  return {
    branch,
    pickup_datetime: pickup,
    return_datetime: ret,
    category: params.get('category') ?? undefined,
    page: Number.isInteger(page) && page > 1 ? page : 1,
  }
}

function writeQuery(query: SearchQuery): Record<string, string> {
  const next: Record<string, string> = {
    branch: query.branch,
    pickup_datetime: query.pickup_datetime,
    return_datetime: query.return_datetime,
  }
  if (query.category) next.category = query.category
  if (query.page && query.page > 1) next.page = String(query.page)
  return next
}

/** What a refused search says that no form field shows: non-field errors, other fields, or the detail. */
function formLevelMessage(error: ApiError): string | null {
  const isField = (key: string) => (FIELDS as readonly string[]).includes(key)
  const leftovers = [
    ...error.nonFieldErrors,
    ...Object.entries(error.fieldErrors).flatMap(([key, messages]) => (isField(key) ? [] : messages)),
  ]
  if (leftovers.length) return leftovers.join(' ')
  return Object.keys(error.fieldErrors).some(isField) ? null : error.message
}

/** SRS 3.2: choose a branch and a period; see the vehicles free for all of it (Search.Available). */
export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const query = readQuery(params)

  const branches = useQuery({ queryKey: BRANCHES_KEY, queryFn: listBranches, staleTime: 5 * 60_000 })
  const categories = useQuery({
    queryKey: CATEGORIES_KEY,
    queryFn: listCategories,
    staleTime: 5 * 60_000,
  })
  const results = useQuery({
    queryKey: query ? searchKey(query) : ['fleet', 'search', 'none'],
    queryFn: () => searchVehicles(query!),
    enabled: query !== null,
  })

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SearchValues>({
    resolver: zodResolver(searchSchema),
    defaultValues: {
      branch: query?.branch ?? '',
      category: query?.category ?? '',
      pickup_datetime: query ? isoToLocal(query.pickup_datetime) : '',
      return_datetime: query ? isoToLocal(query.return_datetime) : '',
    },
  })

  // The server re-checks the search (CO-3); its 400 messages go next to the fields.
  const rejected = results.error instanceof ApiError && results.error.status === 400 ? results.error : null
  const errorFor = (field: FieldName) =>
    errors[field]?.message ?? rejected?.fieldErrors[field]?.join(' ')
  const formError = rejected ? formLevelMessage(rejected) : null

  const onSubmit = handleSubmit((values) => {
    setParams(
      writeQuery({
        branch: values.branch,
        category: values.category || undefined,
        pickup_datetime: localToISO(values.pickup_datetime),
        return_datetime: localToISO(values.return_datetime),
      }),
    )
  })

  const goToPage = (page: number) => query && setParams(writeQuery({ ...query, page }))
  const branchName = (id: string) =>
    branches.data?.find((branch) => String(branch.branch_id) === id)?.branch_name ?? 'the branch'

  const fieldProps = (field: FieldName, hint = false) => ({
    'aria-invalid': errorFor(field) ? true : undefined,
    'aria-describedby': describedBy(`search-${field}`, { hint, error: Boolean(errorFor(field)) }),
  })

  return (
    <section>
      <PageHeader
        title="Find a vehicle"
        description="Choose a pickup branch and your rental period. Only vehicles free for the whole period are shown."
      />

      {branches.isPending || categories.isPending ? (
        <LoadingState label="Loading branches and categories…" />
      ) : branches.isError || categories.isError ? (
        <ErrorState
          title="We couldn’t load the search form"
          error={branches.error ?? categories.error}
          onRetry={() => {
            void branches.refetch()
            void categories.refetch()
          }}
        />
      ) : branches.data.length === 0 ? (
        <EmptyState title="No branches yet" description="There are no pickup branches to search." />
      ) : (
        <div className="-mx-4 mb-8 border-y bg-canvas-sunken px-4 py-5 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <form onSubmit={onSubmit} noValidate className="grid gap-5" aria-label="Search vehicles">
            <FormAlert message={formError} />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-[1.25fr_1fr_1fr_1fr_auto] lg:items-start">
              <Field id="search-branch" label="Pickup branch" error={errorFor('branch')}>
                <NativeSelect id="search-branch" {...fieldProps('branch')} {...register('branch')}>
                  <option value="">Choose a branch</option>
                  {branches.data.map((branch) => (
                    <option key={branch.branch_id} value={branch.branch_id}>
                      {branch.branch_name}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <Field id="search-category" label="Vehicle category" error={errorFor('category')}>
                <NativeSelect id="search-category" {...fieldProps('category')} {...register('category')}>
                  <option value="">Any category</option>
                  {categories.data.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name} ({category.vehicle_type})
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <Field id="search-pickup_datetime" label="Pickup" error={errorFor('pickup_datetime')}>
                <Input
                  id="search-pickup_datetime"
                  type="datetime-local"
                  {...fieldProps('pickup_datetime')}
                  {...register('pickup_datetime')}
                />
              </Field>
              <Field
                id="search-return_datetime"
                label="Return"
                hint="A rental lasts from 4 hours to 30 days."
                error={errorFor('return_datetime')}
              >
                <Input
                  id="search-return_datetime"
                  type="datetime-local"
                  {...fieldProps('return_datetime', true)}
                  {...register('return_datetime')}
                />
              </Field>
              <div className="lg:pt-[26px]">
                <SubmitButton busy={results.isFetching} busyLabel="Searching…">
                  Search
                </SubmitButton>
              </div>
            </div>
          </form>
        </div>
      )}

      {!query || rejected ? null : results.isPending ? (
        <LoadingState label="Finding available vehicles…" />
      ) : results.isError ? (
        <ErrorState
          title="We couldn’t search right now"
          error={results.error}
          onRetry={() => void results.refetch()}
        />
      ) : (
        <section aria-labelledby="results-heading" className="grid gap-4">
          <div className="enter">
            <h2 id="results-heading" className="text-section font-semibold">
              Available vehicles
            </h2>
            <p role="status" className="text-sm text-muted-foreground">
              {results.data.count === 1 ? '1 vehicle is' : `${results.data.count} vehicles are`} free
              at {branchName(query.branch)} from {formatDateTime(query.pickup_datetime)} to{' '}
              {formatDateTime(query.return_datetime)}.
            </p>
          </div>
          {results.data.count === 0 ? (
            <EmptyState
              title="No vehicles are free for these dates"
              description="Try different dates, another category or another branch."
            />
          ) : (
            <VehicleResults
              vehicles={results.data.results}
              hrefFor={(vehicle) =>
                `/app/vehicles/${vehicle.id}?${new URLSearchParams({
                  pickup_datetime: query.pickup_datetime,
                  return_datetime: query.return_datetime,
                })}`
              }
              hasPrevious={Boolean(results.data.previous)}
              hasNext={Boolean(results.data.next)}
              onPrevious={() => goToPage((query.page ?? 1) - 1)}
              onNext={() => goToPage((query.page ?? 1) + 1)}
            />
          )}
        </section>
      )}
    </section>
  )
}
