import type { ReactNode } from 'react'

import { Photo } from '@/components/photo'
import { usePageTitle } from '@/hooks/page'

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
   * A slim decorative photo band above the title (imagery-brief.md, 2):
   * 160 px tall, 192 px from 1024 px, hidden below 640 px so phones keep
   * the content at the top.
   */
  photo?: string
}) {
  usePageTitle(title)
  // Title, one line of context, actions on the right, then a hairline
  // (docs/design/ui-brief.md, 6.3).
  return (
    <>
      {photo ? (
        <Photo
          id={photo}
          alt=""
          sizes="(min-width: 768px) calc(100vw - 19rem), 100vw"
          className="enter mb-8 hidden h-40 rounded-xl sm:block lg:h-48"
        />
      ) : null}
      <div className="mb-8 flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-title break-words text-foreground">
            {title}
          </h1>
          {description ? (
            <p className="mt-2 max-w-[72ch] text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>
    </>
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
