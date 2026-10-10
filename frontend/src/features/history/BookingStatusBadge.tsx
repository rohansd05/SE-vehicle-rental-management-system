// Booking status (Appendix B). Each status has an icon and its name as well as
// a colour, so colour is never the only cue (WCAG 2.1 1.4.1).

import {
  Ban,
  CircleCheck,
  CircleDashed,
  Clock,
  KeyRound,
  type LucideIcon,
  PartyPopper,
  UserX,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { BookingStatus } from '@/features/booking/api'
import { cn } from '@/lib/utils'

const STYLES: Record<BookingStatus, { icon: LucideIcon; className: string }> = {
  Draft: { icon: CircleDashed, className: 'bg-muted text-muted-foreground' },
  'Pending Payment': { icon: Clock, className: 'bg-amber-500/15 text-amber-900 dark:text-amber-300' },
  Confirmed: { icon: CircleCheck, className: 'bg-emerald-600/10 text-emerald-800 dark:text-emerald-300' },
  Active: { icon: KeyRound, className: 'bg-sky-600/10 text-sky-800 dark:text-sky-300' },
  Completed: { icon: PartyPopper, className: 'bg-muted text-foreground' },
  Cancelled: { icon: Ban, className: 'bg-destructive/10 text-destructive' },
  'No-show': { icon: UserX, className: 'bg-destructive/10 text-destructive' },
}

export function BookingStatusBadge({ status }: { status: BookingStatus }) {
  const { icon: Icon, className } = STYLES[status]
  return (
    <Badge variant="secondary" className={cn('gap-1', className)}>
      <Icon className="size-3" aria-hidden="true" />
      {status}
    </Badge>
  )
}
