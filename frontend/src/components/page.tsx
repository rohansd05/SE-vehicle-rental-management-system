import type { ReactNode } from 'react'

import { Photo } from '@/components/photo'
import { usePageTitle } from '@/hooks/page'
import { stagger } from '@/lib/motion'

export function PageHeader({
  title,
  description,
  actions,
  photo,
  eyebrow,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
  /** A short line above the title, such as "Error 404" (existing copy only). */
  eyebrow?: ReactNode
  /**
   * The heading section's photo (B14). From 1024 px the header is one frame
   * at the content width, 280 px tall at least and about 300 to 360 px at
   * 1440 to 1536 (a minimum, so long text grows the frame): the title,
   * subtitle and action in the left half, vertically centred, and the photo
   * filling the right half to the frame's top, right and bottom edges. Below 1024 px the photo runs full width
   * above the text (3:2 on phones, 16:9 from 640 px). The photo is fitted
   * from its subject box (B13), decorative, and loads first.
   */
  photo?: string
}) {
  usePageTitle(title)
  if (!photo) {
    // Title, one line of context, actions on the right, then a hairline
    // (docs/design/ui-brief.md, 6.3).
    return (
      <div className="mb-8 flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-end sm:justify-between sm:gap-8">
        <div className="min-w-0 flex-1">
          {eyebrow}
          <h1 className="text-title text-foreground">{title}</h1>
          {description ? <p className="mt-3 max-w-[60ch] text-lead text-muted-foreground">{description}</p> : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-3">{actions}</div> : null}
      </div>
    )
  }
  return (
    <div className="@container mb-10">
      <div className="enter grid overflow-hidden rounded-xl border bg-canvas-sunken lg:min-h-[clamp(17.5rem,30cqi,22.5rem)] lg:grid-cols-2">
        <div className="relative lg:order-last">
          <Photo
            id={photo}
            alt=""
            priority
            sizes="(min-width: 1024px) 50vw, 100vw"
            className="aspect-[3/2] sm:aspect-video lg:absolute lg:inset-0 lg:aspect-auto lg:size-full"
          />
          <div className="absolute inset-0 bg-photo-overlay-soft" />
        </div>
        <div className="enter flex min-w-0 flex-col justify-center gap-4 p-4 sm:p-8 lg:py-8 lg:pr-(--header-gap) lg:pl-6 xl:pl-(--header-gap)" style={stagger(1)}>
          {eyebrow}
          <h1 className="text-header-title text-foreground lg:text-header-title-split">{title}</h1>
          {description ? <p className="text-lead text-muted-foreground">{description}</p> : null}
          {actions ? <div className="mt-2 flex flex-wrap gap-3">{actions}</div> : null}
        </div>
      </div>
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
