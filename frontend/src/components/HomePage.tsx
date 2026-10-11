import {
  CalendarDays,
  ChevronDown,
  ChevronRight,
  CreditCard,
  FileDown,
  Hammer,
  IdCard,
  type LucideIcon,
  Search,
  ShieldAlert,
  ShieldCheck,
  Wrench,
} from 'lucide-react'
import { type ReactNode, useEffect } from 'react'
import { Link } from 'react-router-dom'

import { Reveal } from '@/components/reveal'
import { TONE_PILL } from '@/components/status-tone'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-context'
import { PRODUCT_NAME, useAgency } from '@/hooks/page'
import { stagger } from '@/lib/motion'
import { cn } from '@/lib/utils'
import { HELP_TOPICS } from '@/pages/help-topics'

// The public landing page (docs/design/ui-brief.md, 6.2 and 6.2.1). Every
// sentence below the hero describes what the app does today; each one and
// its source is listed in the brief. No numbers, prices, ratings,
// testimonials, images or other claims.

type Tone = 'ok' | 'warn' | 'error' | 'muted'

function StatusPill({ tone, children }: { tone: Tone; children: string }) {
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center rounded-md px-2 text-xs font-medium transition-colors duration-300',
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
    <div className="flex items-center justify-between gap-4 py-3.5">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  )
}

/** Page gutters, shared by every band so their edges line up (B4). */
const GUTTER = 'px-4 sm:px-6 lg:px-8'

/** A landing band: a centred heading and one line of context, then full-width content. */
function Band({
  id,
  title,
  intro,
  children,
}: {
  id: string
  title: string
  intro?: string
  children: ReactNode
}) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className={cn('scroll-mt-16 border-t py-20 lg:py-28', GUTTER)}>
      <Reveal className="mx-auto max-w-[46rem] text-center">
        <h2 id={`${id}-heading`} className="text-title">
          {title}
        </h2>
        {intro ? <p className="mx-auto mt-4 max-w-[60ch] text-lead text-muted-foreground">{intro}</p> : null}
      </Reveal>
      <div className="mt-14 lg:mt-16">{children}</div>
    </section>
  )
}

interface Item {
  icon: LucideIcon
  title: string
  body: string
}

/** What the app does today (Search.Available, SE-10, Pay.*, History.Download, BR-16, History.View). */
const FEATURES: readonly Item[] = [
  {
    icon: Search,
    title: 'Find a vehicle',
    body: 'Choose a pickup branch and your rental period. Only vehicles free for the whole period are shown.',
  },
  {
    icon: IdCard,
    title: 'Licence checked by staff',
    body: 'Upload clear photos of the front and back of your licence. Our staff verify it before you can book.',
  },
  {
    icon: CreditCard,
    title: 'Card, online or cash',
    body: 'Pay by card, online or in cash at the branch. The refundable security deposit is held separately and is not part of the total.',
  },
  {
    icon: FileDown,
    title: 'Invoices to download',
    body: 'Once you have paid, your booking shows its invoice, ready to download.',
  },
  {
    icon: ShieldCheck,
    title: 'Unsafe vehicles are never offered',
    body: 'Vehicles under maintenance or flagged Unsafe leave search and booking until they are cleared.',
  },
  {
    icon: CalendarDays,
    title: 'Your booking history',
    body: 'Every booking you have made, the most recent pickup first.',
  },
]

/** The customer's steps, in order (SE-7, Book.Eligible, Search.Available, Book.Hold, Pay.Authorize). */
const STEPS: readonly { title: string; body: string }[] = [
  {
    title: 'Create your account',
    body: "We'll send a code to your mobile number to confirm it's yours.",
  },
  {
    title: 'Submit your licence',
    body: 'Enter the details exactly as printed and add clear photos of both sides. Our staff verify it before you can book.',
  },
  {
    title: 'Search and hold',
    body: 'Choose a pickup branch and your rental period. We hold the vehicle for you for 15 minutes while you pay.',
  },
  {
    title: 'Pay and collect',
    body: 'Pay by card, online or in cash at the branch, then show your pickup code at the branch to collect the vehicle, or have it delivered.',
  },
]

/** The staff side, in the menu's own words (app/navigation.ts, maintenance/navigation.ts). */
const BRANCH_TEAMS: readonly Item[] = [
  { icon: ShieldCheck, title: 'Licence checks', body: 'Verify the driving licences customers have submitted.' },
  { icon: Wrench, title: 'Maintenance', body: 'Report faults, assign technicians and follow your branch’s jobs.' },
  { icon: Hammer, title: 'Maintenance jobs', body: 'The jobs assigned to you, and the work and parts you record.' },
  {
    icon: ShieldAlert,
    title: 'Unsafe clearances',
    body: 'Review completed work on Unsafe vehicles and clear the flag (BR-16).',
  },
]

/** The public landing page: the agency, what it does, how it works, its status and help. */
export function HomePage() {
  const { status } = useAuth()
  const { health } = useAgency()
  const agencyName = health.data?.agency_name
  const signedIn = status === 'signed-in'

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
    <div>
      {/* Hero: fills the first viewport under the 64 px top bar; the group sits
          slightly above the mathematical centre (more padding below than above). */}
      <section className={cn('relative flex min-h-[calc(100svh-4rem)] flex-col items-center justify-center pt-12 pb-[14svh] text-center', GUTTER)}>
        <h1
          className="enter display mx-auto max-w-[18ch] text-display break-words"
          style={stagger(0, 90)}
        >
          {agencyName ?? (health.isError ? 'Service unavailable' : 'Loading…')}
        </h1>
        <p className="enter mx-auto mt-6 max-w-[60ch] text-lead text-muted-foreground" style={stagger(1, 90)}>
          Book a car or two-wheeler online for the dates you need, collect it from a branch or
          have it delivered, and pay by card, online or in cash at the branch.
        </p>
        <div className="enter mt-9 flex w-full flex-col items-center justify-center gap-3 sm:w-auto sm:flex-row" style={stagger(2, 90)}>
          {signedIn ? (
            <Button asChild className="w-full sm:w-auto">
              <Link to="/app">Go to my account</Link>
            </Button>
          ) : (
            <>
              <Button asChild className="w-full sm:w-auto">
                <Link to="/register">Create an account</Link>
              </Button>
              <Button asChild variant="outline" className="w-full sm:w-auto">
                <Link to="/login">Sign in</Link>
              </Button>
            </>
          )}
        </div>
        {/* Scroll cue: named by the first section's heading, so it adds no new text. */}
        <a
          href="#features"
          aria-labelledby="features-heading"
          className="enter absolute bottom-8 left-1/2 flex size-11 -translate-x-1/2 items-center justify-center rounded-full border text-ink-muted transition-colors hover:border-line-strong hover:text-foreground"
          style={stagger(6, 90)}
        >
          <ChevronDown className="size-5" aria-hidden="true" />
        </a>
      </section>

      <Band
        id="features"
        title="Book online, collect at the branch"
        intro="Search, book and pay online. Our staff verify your driving licence before you can book."
      >
        <ul className="grid gap-x-12 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body }, index) => (
            <Reveal as="li" staggered key={title} className="border-t pt-6" style={stagger(index % 3, 70)}>
              <Icon className="size-6 text-primary" aria-hidden="true" />
              <h3 className="mt-4 text-subsection">{title}</h3>
              <p className="mt-2 max-w-[44ch] text-muted-foreground">{body}</p>
            </Reveal>
          ))}
        </ul>
      </Band>

      <Band id="how-it-works" title="How it works" intro="Four steps from your account to the keys.">
        <ol className="grid gap-x-10 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ title, body }, index) => (
            <Reveal as="li" staggered key={title} className="border-t-2 border-foreground pt-5" style={stagger(index, 70)}>
              <span aria-hidden="true" className="num-lg block text-primary">
                {index + 1}
              </span>
              <h3 className="mt-3 text-subsection">{title}</h3>
              <p className="mt-2 text-muted-foreground">{body}</p>
            </Reveal>
          ))}
        </ol>
      </Band>

      <Band
        id="branch-teams"
        title="For branch teams"
        intro="Branch staff, technicians and administrators sign in to the same system."
      >
        <ul className="grid gap-x-12 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {BRANCH_TEAMS.map(({ icon: Icon, title, body }, index) => (
            <Reveal as="li" staggered key={title} className="border-t pt-6" style={stagger(index, 70)}>
              <Icon className="size-6 text-primary" aria-hidden="true" />
              <h3 className="mt-4 text-subsection">{title}</h3>
              <p className="mt-2 text-muted-foreground">{body}</p>
            </Reveal>
          ))}
        </ul>
        <Reveal className="mt-12 flex justify-center">
          <Button asChild variant="outline">
            <Link to="/login">Sign in</Link>
          </Button>
        </Reveal>
      </Band>

      <section aria-label="System status and help" className={cn('border-t py-20 lg:py-28', GUTTER)}>
        <div className="grid gap-16 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:gap-24 xl:gap-32">
          <Reveal>
            <section aria-labelledby="system-status">
              <h2 id="system-status" className="text-section">
                System status
              </h2>
              <p className="text-small text-muted-foreground">{PRODUCT_NAME}</p>
              <dl className="mt-4 divide-y border-y">
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
          </Reveal>

          <section aria-labelledby="help-topics-heading">
            <Reveal>
              <h2 id="help-topics-heading" className="text-section">
                Help
              </h2>
            </Reveal>
            <ul className="mt-4 divide-y border-y">
              {HELP_TOPICS.map((topic, index) => (
                <Reveal as="li" staggered key={topic.id} style={stagger(index, 70)}>
                  <Link to={`/help#${topic.id}`} className="group flex items-start gap-6 py-5">
                    <span className="min-w-0 flex-1">
                      <span className="heading block text-subsection transition-colors group-hover:text-primary">
                        {topic.title}
                      </span>
                      <span className="mt-1 block max-w-[72ch] text-muted-foreground">{topic.body}</span>
                    </span>
                    <ChevronRight
                      className="mt-1.5 size-5 shrink-0 text-ink-subtle transition-colors group-hover:text-primary"
                      aria-hidden="true"
                    />
                  </Link>
                </Reveal>
              ))}
            </ul>
          </section>
        </div>
      </section>

      {/* Final call to action. It reuses the top bar's own labels ("Register",
          "Sign in", "My account") so the hero's actions stay the only
          "Create an account" and "Go to my account" links on the page. */}
      <section aria-labelledby="start-heading" className={cn('border-t py-24 text-center lg:py-32', GUTTER)}>
        <Reveal className="mx-auto flex max-w-[46rem] flex-col items-center">
          <h2 id="start-heading" className="display text-title">
            {signedIn ? (agencyName ?? PRODUCT_NAME) : 'Create your account'}
          </h2>
          <div className="mt-8 flex w-full flex-col items-center justify-center gap-3 sm:w-auto sm:flex-row">
            {signedIn ? (
              <Button asChild className="w-full sm:w-auto">
                <Link to="/app">My account</Link>
              </Button>
            ) : (
              <>
                <Button asChild className="w-full sm:w-auto">
                  <Link to="/register">Register</Link>
                </Button>
                <Button asChild variant="outline" className="w-full sm:w-auto">
                  <Link to="/login">Sign in</Link>
                </Button>
              </>
            )}
          </div>
        </Reveal>
      </section>

      <footer className={cn('flex flex-wrap items-center justify-between gap-4 border-t py-8', GUTTER)}>
        <p className="heading text-subsection">{agencyName ?? PRODUCT_NAME}</p>
        <Link to="/help" className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary">
          Help
        </Link>
      </footer>
    </div>
  )
}
