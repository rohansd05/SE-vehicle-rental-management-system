import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { approveLicence, listPendingLicences, rejectLicence } from '@/api/licences'
import type { LicenceReview } from '@/api/types'
import { FormAlert } from '@/components/form'
import { PageHeader } from '@/components/page'
import { StickyRail } from '@/components/sticky-rail'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatDateTime } from '@/lib/dates'
import { DETAILS_LIST, RAIL_LAYOUT } from '@/lib/layout'
import { cn } from '@/lib/utils'

import { PENDING_LICENCES_KEY } from './keys'
import { RejectDialog } from './RejectDialog'
import { ageFrom } from './rules'

function LicenceImage({ src, label }: { src: string | null; label: string }) {
  const [broken, setBroken] = useState(false)
  return (
    <figure className="grid gap-2">
      <figcaption className="text-sm font-medium">{label}</figcaption>
      {src && !broken ? (
        <a href={src} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-md border focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          <img src={src} alt={label} className="aspect-[3/2] w-full bg-canvas-sunken object-contain" onError={() => setBroken(true)} />
          <span className="sr-only"> (opens the full image in a new tab)</span>
        </a>
      ) : (
        <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
          {src
            ? 'The secure link to this image has expired (links last 15 minutes). Reload the page.'
            : 'No image was uploaded.'}
        </p>
      )}
    </figure>
  )
}

/**
 * Review one pending licence. There is no single-licence endpoint, so the
 * licence comes from the queue (passed when opened, or found in the queue).
 */
export function LicenceReviewPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const passed = (useLocation().state as { licence?: LicenceReview } | null)?.licence
  const licenceId = Number(id)
  const queue = useQuery({
    queryKey: PENDING_LICENCES_KEY,
    queryFn: listPendingLicences,
    enabled: !passed || passed.id !== licenceId,
  })
  const licence =
    passed && passed.id === licenceId ? passed : queue.data?.results.find((item) => item.id === licenceId)

  const finish = async (message: string) => {
    await queryClient.invalidateQueries({ queryKey: PENDING_LICENCES_KEY })
    navigate('/app/licences', { state: { flash: message } })
  }

  const approve = useMutation({
    mutationFn: () => approveLicence(licenceId),
    onSuccess: (decided) => finish(`Licence approved for ${decided.customer.name}. They have been e-mailed.`),
  })

  const reject = async (reason: string) => {
    const decided = await rejectLicence(licenceId, reason)
    await finish(`Licence rejected for ${decided.customer.name}. They have been e-mailed the reason.`)
  }

  const back = (
    <Button asChild variant="ghost" className="mb-2 -ml-2 h-10">
      <Link to="/app/licences">
        <ArrowLeft aria-hidden="true" />
        Back to the queue
      </Link>
    </Button>
  )

  if (!licence) {
    return (
      <section>
        {back}
        <PageHeader title="Review licence" />
        {queue.isPending ? (
          <LoadingState label="Loading the licence…" />
        ) : queue.isError ? (
          <ErrorState error={queue.error} onRetry={() => void queue.refetch()} />
        ) : (
          <EmptyState
            title="This licence isn’t waiting for a decision"
            description="It may already have been approved or rejected. Open the queue to see what is still waiting."
          />
        )}
      </section>
    )
  }

  const age = ageFrom(licence.customer.date_of_birth)

  return (
    <section>
      {back}
      <PageHeader
        title={`Review licence: ${licence.customer.name}`}
        description={`Submitted ${formatDateTime(licence.updated_at)}`}
      />
      <FormAlert message={approve.error instanceof Error ? approve.error.message : null} />
      {/* Main column (details, photos) and the decision in a sticky right rail (ui-brief.md 6.6). */}
      <div className={cn(RAIL_LAYOUT, 'mt-2')}>
        <div className="grid min-w-0 content-start gap-8">
        <Card>
          <CardHeader>
            <CardTitle>
              <h2>Details</h2>
            </CardTitle>
          </CardHeader>
          <CardContent className="@container">
            <dl className={DETAILS_LIST}>
              <dt className="text-muted-foreground">Customer</dt>
              <dd className="font-medium">{licence.customer.name}</dd>
              <dt className="text-muted-foreground">E-mail</dt>
              <dd className="font-medium break-all">{licence.customer.email}</dd>
              <dt className="text-muted-foreground">Mobile</dt>
              <dd className="font-medium">{licence.customer.mobile_no}</dd>
              <dt className="text-muted-foreground">Date of birth</dt>
              <dd className="font-medium">
                {formatDate(licence.customer.date_of_birth)} (age {age})
              </dd>
              <dt className="text-muted-foreground">Licence number</dt>
              <dd className="num font-medium whitespace-nowrap">{licence.licence_number}</dd>
              <dt className="text-muted-foreground">Issued by</dt>
              <dd className="font-medium">{licence.issuing_authority}</dd>
              <dt className="text-muted-foreground">Valid</dt>
              <dd className="font-medium">
                {formatDate(licence.issue_date)} to {formatDate(licence.expiry_date)}
              </dd>
              <dt className="text-muted-foreground">Categories claimed</dt>
              <dd className="font-medium">{licence.categories.join(', ')}</dd>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>
              <h2>Photos</h2>
            </CardTitle>
          </CardHeader>
          <CardContent className="@container grid gap-6 @xl:grid-cols-2">
            <LicenceImage src={licence.front_image_url} label="Front of the licence" />
            <LicenceImage src={licence.back_image_url} label="Back of the licence" />
          </CardContent>
        </Card>
        </div>
        <StickyRail>
        <div className="flex flex-col gap-3 lg:pt-1">
          <Button
           
           
            onClick={() => approve.mutate()}
            disabled={approve.isPending}
            aria-busy={approve.isPending}
          >
            {approve.isPending ? 'Approving…' : 'Approve'}
          </Button>
          <RejectDialog customerName={licence.customer.name} onReject={reject} />
        </div>
        </StickyRail>
      </div>
    </section>
  )
}
