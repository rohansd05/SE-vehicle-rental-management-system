// Booking status (Appendix B). Each status has an icon and its name as well as
// a colour, so colour is never the only cue (WCAG 2.1 1.4.1).

import {
  Ban,
  CircleCheck,
  CircleCheckBig,
  CircleDashed,
  Clock,
  KeyRound,
  type LucideIcon,
  UserX,
} from 'lucide-react'

import { TONE_PILL, type StatusTone } from '@/components/status-tone'
import { Badge } from '@/components/ui/badge'
import type { BookingStatus } from '@/features/booking/api'
import { cn } from '@/lib/utils'

const STYLES: Record<BookingStatus, { icon: LucideIcon; tone: StatusTone }> = {
  Draft: { icon: CircleDashed, tone: 'inactive' },
  'Pending Payment': { icon: Clock, tone: 'maintenance' },
  Confirmed: { icon: CircleCheck, tone: 'available' },
  Active: { icon: KeyRound, tone: 'booked' },
  Completed: { icon: CircleCheckBig, tone: 'inactive' },
  Cancelled: { icon: Ban, tone: 'unsafe' },
  'No-show': { icon: UserX, tone: 'unsafe' },
}

export function BookingStatusBadge({ status }: { status: BookingStatus }) {
  const { icon: Icon, tone } = STYLES[status]
  return (
    <Badge variant="secondary" className={cn('gap-1', TONE_PILL[tone])}>
      <Icon className="size-3" aria-hidden="true" />
      {status}
    </Badge>
  )
}
