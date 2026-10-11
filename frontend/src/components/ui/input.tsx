import * as React from "react"
import { cn } from "cn"

// forwardRef: the project pins React 18 (handoff stack), where a function
// component does not receive `ref` as a prop. React Hook Form's register()
// reads values through that ref, so without forwardRef every form would
// submit empty values. Height 40 px for comfortable touch targets.
const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  function Input({ className, type, ...props }, ref) {
    return (
      <input
        ref={ref}
        type={type}
        data-slot="input"
        className={cn(
          "h-10 w-full min-w-0 rounded-md border border-input bg-surface px-3 py-1 text-base text-foreground transition-colors file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-ink-subtle focus-visible:border-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-muted disabled:text-ink-muted aria-invalid:border-destructive md:text-sm",
          className
        )}
        {...props}
      />
    )
  }
)

export { Input }
