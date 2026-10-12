import type { ReactNode } from 'react'

import { Photo } from '@/components/photo'
import { usePageTitle } from '@/hooks/page'
import { cn } from '@/lib/utils'

export function PageHeader({
  title,
  description,
  actions,
  photo,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
  /**
   * A decorative photo beside the title (imagery-brief.md, 2; B13): whole, at
   * its own shape, under the soft petrol tint, vertically centred against the
   * title block and never above the page's content or actions. 128 px tall,
   * from 1280 px only, so narrower screens keep the title and actions whole
   * and the content first.
   */
  photo?: string
}) {
  usePageTitle(title)
  // Title, one line of context, actions on the right, then a hairline
  // (docs/design/ui-brief.md, 6.3).
  return (
    <div
      className={cn(
        'mb-8 flex flex-col gap-4 border-b pb-6 sm:flex-row sm:justify-between sm:gap-8',
        photo ? 'sm:items-center' : 'sm:items-end',
      )}
    >
      <div className="min-w-0 flex-1">
        <h1 className="text-title break-words text-foreground">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-[72ch] text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      {photo ? (
        <div className="enter relative hidden shrink-0 overflow-hidden rounded-xl xl:block">
          <Photo id={photo} alt="" aspect="native" sizes="12rem" className="h-32 w-auto" />
          <div className="absolute inset-0 bg-photo-overlay-soft" />
        </div>
      ) : null}
    </div>
  )
}

export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:font-medium focus:text-foreground focus:shadow-overlay"
    >
      Skip to main content
    </a>
  )
}
