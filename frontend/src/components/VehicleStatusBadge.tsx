// Vehicle status (Fleet.Status, Appendix B). One badge everywhere a vehicle's
// status appears, so the same status always looks the same. Each status has
// an icon and its name as well as a colour, so colour is never the only cue
// (WCAG 2.1 1.4.1).

import { Archive, CircleCheck, KeyRound, type LucideIcon, TriangleAlert, Wrench } from 'lucide-react'

import type { VehicleStatus } from '@/api/maintenance'
import { TONE_PILL, type StatusTone } from '@/components/status-tone'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const STYLES: Record<VehicleStatus, { icon: LucideIcon; tone: StatusTone }> = {
  Available: { icon: CircleCheck, tone: 'available' },
  'On Rent': { icon: KeyRound, tone: 'booked' },
  'Under Maintenance': { icon: Wrench, tone: 'maintenance' },
  Unsafe: { icon: TriangleAlert, tone: 'unsafe' },
  Retired: { icon: Archive, tone: 'inactive' },
}

export function VehicleStatusBadge({
  status,
  className,
}: {
  status: VehicleStatus
  className?: string
}) {
  const { icon: Icon, tone } = STYLES[status]
  return (
    <Badge variant="secondary" className={cn(TONE_PILL[tone], className)}>
      <Icon aria-hidden="true" />
      {status}
    </Badge>
  )
}
