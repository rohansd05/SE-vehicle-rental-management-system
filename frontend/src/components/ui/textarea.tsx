import * as React from "react"
import { cn } from "cn"

// forwardRef for React 18 so React Hook Form can read the value (see input.tsx).
const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<"textarea">>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        data-slot="textarea"
        className={cn(
          "flex field-sizing-content min-h-24 w-full rounded-md border border-input bg-surface px-3 py-2.5 text-base text-foreground transition-colors placeholder:text-ink-subtle focus-visible:border-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-muted disabled:text-ink-muted aria-invalid:border-destructive",
          className
        )}
        {...props}
      />
    )
  }
)

export { Textarea }
