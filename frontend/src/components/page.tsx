import type { ReactNode } from 'react'

import { usePageTitle } from '@/hooks/page'

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  usePageTitle(title)
  // Title, one line of context, actions on the right, then a hairline
  // (docs/design/ui-brief.md, 6.3).
  return (
    <div className="mb-6 flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-title font-semibold break-words text-foreground [font-stretch:104%]">
          {title}
        </h1>
        {description ? (
          <p className="mt-1 max-w-[72ch] text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
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
