import { type ReactNode, useEffect } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { TONE_PILL } from '@/components/status-tone'
import { useAuth } from '@/features/auth/auth-context'
import { PRODUCT_NAME, useAgency } from '@/hooks/page'
import { cn } from '@/lib/utils'

type Tone = 'ok' | 'warn' | 'error' | 'muted'

function StatusPill({ tone, children }: { tone: Tone; children: string }) {
  return (
    <span
      className={cn(
        'inline-flex h-5 items-center rounded-md px-1.5 text-xs font-medium',
        tone === 'ok' && TONE_PILL.available,
        tone === 'warn' && TONE_PILL.maintenance,
        tone === 'error' && TONE_PILL.unsafe,
        tone === 'muted' && TONE_PILL.inactive,
      )}
    >
      {children}
    </span>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  )
}

/** The public home page: what the service is, how to start, and the system status. */
export function HomePage() {
  const { status } = useAuth()
  const { health } = useAgency()
  const agencyName = health.data?.agency_name

  useEffect(() => {
    document.title = agencyName || PRODUCT_NAME
  }, [agencyName])

  let apiTone: Tone = 'muted'
  let apiLabel = 'Checking…'
  if (health.isError) {
    apiTone = 'error'
    apiLabel = 'Unreachable'
  } else if (health.data) {
    apiTone = health.data.status === 'ok' ? 'ok' : 'warn'
    apiLabel = health.data.status === 'ok' ? 'Online' : 'Degraded'
  }

  return (
    <div className="grid items-start gap-8 md:grid-cols-[1fr_minmax(0,22rem)]">
      <section>
        <h1 className="text-3xl font-semibold tracking-tight break-words sm:text-4xl">
          {agencyName ?? (health.isError ? 'Service unavailable' : 'Loading…')}
        </h1>
        <p className="mt-3 max-w-prose text-muted-foreground">
          Book a car or two-wheeler online for the dates you need, collect it from a branch or
          have it delivered, and pay by card, online or in cash at the branch.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          {status === 'signed-in' ? (
            <Button asChild size="lg" className="h-10">
              <Link to="/app">Go to my account</Link>
            </Button>
          ) : (
            <>
              <Button asChild size="lg" className="h-10">
                <Link to="/register">Create an account</Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="h-10">
                <Link to="/login">Sign in</Link>
              </Button>
            </>
          )}
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>System status</CardTitle>
          <CardDescription>{PRODUCT_NAME}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="divide-y">
            <Row label="Backend">
              <StatusPill tone={apiTone}>{apiLabel}</StatusPill>
            </Row>
            <Row label="Database">
              {health.data ? (
                <StatusPill tone={health.data.database === 'ok' ? 'ok' : 'error'}>
                  {health.data.database === 'ok' ? 'Reachable' : 'Unreachable'}
                </StatusPill>
              ) : (
                <StatusPill tone="muted">—</StatusPill>
              )}
            </Row>
            <Row label="Currency">{health.data?.currency ?? '—'}</Row>
          </dl>
        </CardContent>
        <CardFooter>
          <Button
            className="w-full sm:w-auto"
            variant="outline"
            onClick={() => health.refetch()}
            disabled={health.isFetching}
          >
            {health.isFetching ? 'Checking…' : 'Check again'}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
