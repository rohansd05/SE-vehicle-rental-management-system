import { Car, CreditCard, IdCard, MapPin, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { PageHeader } from '@/components/page'
import { Photo } from '@/components/photo'
import { useAgency } from '@/hooks/page'
import { stagger } from '@/lib/motion'
import { cn } from '@/lib/utils'

// The sign-in, registration and verification screens share one split
// layout (docs/design/ui-brief.md, 6.1): the form on the left, and on the
// right a photo panel under the petrol overlay (imagery-brief.md, 4: white
// text on primary-hover at 75% is at least 5.1:1) with four short product
// facts. Each fact is reworded from copy the app already shows (the brief
// lists the sources). Below 1024 px the panel is hidden and the form takes
// the page.
const FACTS: readonly { icon: LucideIcon; text: string }[] = [
  { icon: Car, text: 'Cars and two-wheelers, free for the dates you choose.' },
  { icon: MapPin, text: 'Collect at a branch or have it delivered.' },
  { icon: CreditCard, text: 'Pay by card, online, or in cash at the branch.' },
  { icon: IdCard, text: 'Your driving licence is verified by our staff before you book.' },
]

export function AuthLayout({
  title,
  description,
  wide = false,
  children,
}: {
  title: string
  description?: ReactNode
  /** Registration needs room for two columns of fields. */
  wide?: boolean
  children: ReactNode
}) {
  const agency = useAgency()
  return (
    <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,1fr)] lg:gap-16 xl:gap-24">
      <div className={cn('stage w-full lg:py-4', wide ? 'max-w-[40rem]' : 'max-w-[28rem]')}>
        <PageHeader title={title} description={description} />
        <div>{children}</div>
      </div>
      <aside
        aria-hidden="true"
        className="enter relative hidden min-h-[36rem] overflow-hidden rounded-xl bg-primary-hover text-primary-foreground lg:sticky lg:top-24 lg:flex"
        style={stagger(2)}
      >
        <Photo id="auth-2" alt="" sizes="(min-width: 1280px) 40vw, 45vw" className="absolute inset-0" />
        <div className="absolute inset-0 bg-primary-hover/75" />
        <div className="relative flex flex-1 flex-col justify-between px-10 py-10 xl:px-14 xl:py-14">
          <p className="enter display text-display-sm" style={stagger(4)}>
            {agency.name}
          </p>
          <ul className="mt-16 grid gap-0 divide-y divide-primary-foreground/25">
            {FACTS.map(({ icon: Icon, text }, index) => (
              <li key={text} className="enter flex items-start gap-4 py-5" style={stagger(5 + index)}>
                <Icon className="mt-1 size-5 shrink-0 text-signal" />
                <span className="text-lead">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  )
}
