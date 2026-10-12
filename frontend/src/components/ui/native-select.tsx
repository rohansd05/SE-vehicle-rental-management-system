import { forwardRef, type ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/**
 * A native select styled like Input: accessible and usable on touch screens
 * (docs/design/ui-brief.md, section 7). forwardRef so React Hook Form's
 * register() can read the value under React 18 (see input.tsx).
 */
export const NativeSelect = forwardRef<HTMLSelectElement, ComponentProps<'select'>>(
  function NativeSelect({ className, ...props }, ref) {
    return (
      <select
        ref={ref}
        data-slot="native-select"
        className={cn(
          'h-12 w-full min-w-0 rounded-md border border-input bg-surface px-3.5 text-base text-foreground transition-colors focus-visible:border-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-muted disabled:text-ink-muted aria-invalid:border-destructive',
          className,
        )}
        {...props}
      />
    )
  },
)
