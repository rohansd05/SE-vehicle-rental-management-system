// Loading, error and empty states shared by every page (UI-8: anything
// slower than two seconds shows progress).

import { CircleAlert, Inbox, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
      <LoaderCircle className="size-4 animate-spin text-primary" aria-hidden="true" />
      <span>{label}</span>
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
      className="flex flex-col items-start gap-3 rounded-md border-l-2 border-l-status-unsafe bg-status-unsafe-tint px-4 py-3"
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
    <div className="flex items-start gap-3 border-y py-8">
      <Inbox className="mt-0.5 size-5 shrink-0 text-ink-subtle" aria-hidden="true" />
      <div className="flex min-w-0 flex-col items-start gap-1">
        <p className="font-medium text-foreground">{title}</p>
        {description ? <p className="max-w-prose text-sm text-muted-foreground">{description}</p> : null}
        {action ? <div className="mt-3">{action}</div> : null}
      </div>
    </div>
  )
}
