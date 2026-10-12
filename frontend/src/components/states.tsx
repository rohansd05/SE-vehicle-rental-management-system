// Loading, error and empty states shared by every page (UI-8: anything
// slower than two seconds shows progress).

import { CircleAlert, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'

import { Photo } from '@/components/photo'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export function LoadingState({ label = 'Loading…', rows = 0 }: { label?: string; rows?: number }) {
  return (
    <div>
      <div role="status" className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin text-primary" aria-hidden="true" />
        <span>{label}</span>
      </div>
      {/* Queue skeletons (Stage 5): the rows' shape in the token tones, so nothing jumps when they arrive. */}
      {rows ? (
        <ul aria-hidden="true" className="border-t">
          {Array.from({ length: rows }, (_, index) => (
            <li key={index} className="grid gap-2.5 border-b py-5">
              <Skeleton className="h-5 w-1/3" />
              <Skeleton className="h-4 w-2/3" />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

export function ErrorState({
  title = 'Something went wrong',
  error,
  onRetry,
}: {
  title?: string
  error?: unknown
  onRetry?: () => void
}) {
  const message =
    error instanceof Error ? error.message : 'Please try again in a moment.'
  return (
    <div
      role="alert"
      className="enter flex flex-col items-start gap-3 rounded-md border-l-2 border-l-status-unsafe bg-status-unsafe-tint px-4 py-3"
    >
      <div className="flex items-start gap-2">
        <CircleAlert className="mt-[3px] size-4 shrink-0 text-status-unsafe" aria-hidden="true" />
        <div>
          <p className="font-medium text-foreground">{title}</p>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    // B14: the quiet photo fills its share of the empty state (whole, 3:2)
    // beside the message from 640 px, and above it on phones.
    <div className="enter grid items-center gap-6 border-y py-8 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] sm:gap-10">
      <Photo id="band-quiet-2" alt="" sizes="(min-width: 640px) 30vw, 100vw" className="aspect-[3/2] rounded-xl" />
      <div className="flex min-w-0 flex-col items-start gap-2">
        <p className="text-subsection font-medium text-foreground">{title}</p>
        {description ? <p className="max-w-prose text-sm text-muted-foreground">{description}</p> : null}
        {action ? <div className="mt-3">{action}</div> : null}
      </div>
    </div>
  )
}
