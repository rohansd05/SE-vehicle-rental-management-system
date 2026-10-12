import { Car, CreditCard, IdCard, MapPin, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { PageHeader } from '@/components/page'
import { Photo } from '@/components/photo'
import { useAgency } from '@/hooks/page'
import { stagger } from '@/lib/motion'
import { cn } from '@/lib/utils'

// The sign-in, registration and verification screens share one split
// layout (docs/design/ui-brief.md, 6.1): the form on the left, and on the
// right a petrol panel: the photo on top, whole subject in view under the
// light petrol tint (B13), then the agency name and four short product facts
// on the solid petrol, so no text sits on the photo. Each fact is reworded
// from copy the app already shows (the brief lists the sources). Below
// 1024 px the panel is hidden and the form takes the page.
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
        className="enter hidden flex-col overflow-hidden rounded-xl bg-primary-hover text-primary-foreground lg:sticky lg:top-24 lg:flex"
        style={stagger(2)}
      >
        <div className="relative">
          <Photo id="auth-2" alt="" sizes="(min-width: 1280px) 40vw, 45vw" className="aspect-video" />
          <div className="absolute inset-0 bg-photo-overlay-strong" />
        </div>
        <div className="flex flex-1 flex-col px-10 pt-8 pb-6 xl:px-12">
          <p className="enter display text-display-sm" style={stagger(4)}>
            {agency.name}
          </p>
          <ul className="mt-6 grid gap-0 divide-y divide-primary-foreground/25">
            {FACTS.map(({ icon: Icon, text }, index) => (
              <li key={text} className="enter flex items-start gap-4 py-4" style={stagger(5 + index)}>
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
