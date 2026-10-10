import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { getMyLicence } from '@/api/licences'
import type { Licence } from '@/api/types'
import { StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

import { MY_LICENCE_KEY } from './keys'
import { LicenceForm } from './LicenceForm'
import { LicenceStatusCard } from './LicenceStatusCard'

const NEEDS_SUBMISSION: readonly Licence['status'][] = ['Not Submitted', 'Rejected', 'Expired']

/** Customer: licence status and submission (Book.Eligible.No, BR-2, BR-3). */
export function MyLicencePage() {
  const queryClient = useQueryClient()
  const licence = useQuery({ queryKey: MY_LICENCE_KEY, queryFn: getMyLicence })
  const [updating, setUpdating] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const onSubmitted = (updated: Licence) => {
    queryClient.setQueryData(MY_LICENCE_KEY, updated)
    setUpdating(false)
    setNotice('Your licence has been submitted. We’ll e-mail you once it has been checked.')
  }

  return (
    <section>
      <PageHeader
        title="Driving licence"
        description="A verified licence that covers the vehicle’s category is needed before you can book."
      />
      {licence.isPending ? (
        <LoadingState label="Loading your licence…" />
      ) : licence.isError ? (
        <ErrorState
          title="We couldn’t load your licence"
          error={licence.error}
          onRetry={() => void licence.refetch()}
        />
      ) : (
        <div className="grid gap-6">
          <StatusMessage message={notice} tone="success" />
          <LicenceStatusCard licence={licence.data} />
          {NEEDS_SUBMISSION.includes(licence.data.status) || updating ? (
            <Card>
              <CardHeader>
                <CardTitle>
                  <h2>
                    {licence.data.status === 'Not Submitted' ? 'Submit your licence' : 'Submit your licence again'}
                  </h2>
                </CardTitle>
                <CardDescription>
                  Enter the details exactly as printed and add clear photos of both sides.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <LicenceForm
                  current={licence.data}
                  onSubmitted={onSubmitted}
                  onCancel={updating ? () => setUpdating(false) : undefined}
                />
              </CardContent>
            </Card>
          ) : (
            <div>
              <Button
                variant="outline"
                size="lg"
                className="h-10"
                onClick={() => {
                  setNotice(null)
                  setUpdating(true)
                }}
              >
                Update licence details
              </Button>
              <p className="mt-2 text-sm text-muted-foreground">
                For example after renewing it. Your licence will need to be verified again.
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
