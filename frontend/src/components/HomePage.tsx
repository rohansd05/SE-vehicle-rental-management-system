import { ChevronRight } from 'lucide-react'
import { type ReactNode, useEffect } from 'react'
import { Link } from 'react-router-dom'

import { TONE_PILL } from '@/components/status-tone'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-context'
import { Reveal } from '@/components/reveal'
import { PRODUCT_NAME, useAgency } from '@/hooks/page'
import { stagger } from '@/lib/motion'
import { cn } from '@/lib/utils'
import { HELP_TOPICS } from '@/pages/help-topics'

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
    <div className="flex items-center justify-between gap-4 py-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  )
}

/**
 * The public home page (docs/design/ui-brief.md, 6.2): what the service is,
 * how to start, the system status, and the help topics.
 */
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
    <div className="grid gap-16">
      <div className="grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)] lg:gap-24 xl:gap-32">
        <section className="lg:py-8">
          <h1 className="enter display max-w-[16ch] text-display break-words">
            {agencyName ?? (health.isError ? 'Service unavailable' : 'Loading…')}
          </h1>
          <p className="enter mt-5 max-w-[52ch] text-lead text-muted-foreground" style={stagger(1)}>
            Book a car or two-wheeler online for the dates you need, collect it from a branch or
            have it delivered, and pay by card, online or in cash at the branch.
          </p>
          <div className="enter mt-8 flex flex-col gap-3 sm:flex-row" style={stagger(2)}>
            {status === 'signed-in' ? (
              <Button asChild>
                <Link to="/app">Go to my account</Link>
              </Button>
            ) : (
              <>
                <Button asChild>
                  <Link to="/register">Create an account</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link to="/login">Sign in</Link>
                </Button>
              </>
            )}
          </div>
        </section>

        <section aria-labelledby="system-status" className="enter lg:py-8" style={stagger(3)}>
          <h2 id="system-status" className="display text-section">
            System status
          </h2>
          <p className="text-small text-muted-foreground">{PRODUCT_NAME}</p>
          <dl className="mt-3 divide-y border-y">
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
            <Row label="Currency">
              <span className="num">{health.data?.currency ?? '—'}</span>
            </Row>
          </dl>
          <Button
            className="mt-5"
            variant="outline"
            size="sm"
            onClick={() => health.refetch()}
            disabled={health.isFetching}
          >
            {health.isFetching ? 'Checking…' : 'Check again'}
          </Button>
        </section>
      </div>

      <section aria-label="Help topics" className="border-t pt-10">
        <ul className="grid gap-x-12 gap-y-8 md:grid-cols-3">
          {HELP_TOPICS.map((topic, index) => (
            <li key={topic.id}>
              <Reveal style={stagger(index, 90)}>
              <Link
                to={`/help#${topic.id}`}
                className="group block rounded-sm"
              >
                <span className="display flex items-center gap-1.5 text-section group-hover:text-primary">
                  {topic.title}
                  <ChevronRight className="size-4 text-ink-subtle group-hover:text-primary" aria-hidden="true" />
                </span>
                <span className="mt-2 block text-sm text-muted-foreground">{topic.body}</span>
              </Link>
              </Reveal>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
