// Vehicle status (Fleet.Status, Appendix B). One badge everywhere a vehicle's
// status appears, so the same status always looks the same. Each status has
// an icon and its name as well as a colour, so colour is never the only cue
// (WCAG 2.1 1.4.1).

import { Archive, CircleCheck, KeyRound, type LucideIcon, TriangleAlert, Wrench } from 'lucide-react'

import type { VehicleStatus } from '@/api/maintenance'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const STYLES: Record<VehicleStatus, { icon: LucideIcon; className: string }> = {
  Available: {
    icon: CircleCheck,
    className: 'bg-emerald-600/10 text-emerald-800 dark:text-emerald-300',
  },
  'On Rent': { icon: KeyRound, className: 'bg-sky-600/10 text-sky-800 dark:text-sky-300' },
  'Under Maintenance': {
    icon: Wrench,
    className: 'bg-amber-500/15 text-amber-900 dark:text-amber-300',
  },
  Unsafe: { icon: TriangleAlert, className: 'bg-destructive/10 text-destructive' },
  Retired: { icon: Archive, className: 'bg-muted text-muted-foreground' },
}

export function VehicleStatusBadge({
  status,
  className,
}: {
  status: VehicleStatus
  className?: string
}) {
  const { icon: Icon, className: tone } = STYLES[status]
  return (
    <Badge variant="secondary" className={cn(tone, className)}>
      <Icon aria-hidden="true" />
      {status}
    </Badge>
  )
}
