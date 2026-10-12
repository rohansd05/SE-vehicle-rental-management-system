// Job status and severity badges (Maint.Status, Appendix B). Text and an icon
// carry the meaning; colour only reinforces it.

import {
  CircleCheck,
  CircleDashed,
  CircleSlash,
  Clock,
  Hammer,
  type LucideIcon,
  ShieldAlert,
} from 'lucide-react'

import type { JobStatus, MaintenanceJob, Severity } from '@/api/maintenance'
import { TONE_DOT, TONE_PILL, type StatusTone } from '@/components/status-tone'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const JOB: Record<JobStatus, { icon: LucideIcon; tone: StatusTone }> = {
  Reported: { icon: CircleDashed, tone: 'inactive' },
  Scheduled: { icon: Clock, tone: 'booked' },
  'In Progress': { icon: Hammer, tone: 'maintenance' },
  Completed: { icon: CircleCheck, tone: 'available' },
  Cancelled: { icon: CircleSlash, tone: 'inactive' },
}

/** The job's status, or "Awaiting clearance" while an Administrator must clear it (BR-16). */
export function JobStatusBadge({ job }: { job: Pick<MaintenanceJob, 'status' | 'awaiting_clearance'> }) {
  if (job.awaiting_clearance) {
    return (
      <Badge variant="secondary" className={TONE_PILL.unsafe}>
        <ShieldAlert aria-hidden="true" />
        Awaiting clearance
      </Badge>
    )
  }
  const { icon: Icon, tone } = JOB[job.status]
  return (
    <Badge variant="secondary" className={TONE_PILL[tone]}>
      <Icon aria-hidden="true" />
      {job.status}
    </Badge>
  )
}

const SEVERITY: Record<Severity, StatusTone> = {
  Low: 'inactive',
  Medium: 'inactive',
  High: 'maintenance',
  Critical: 'unsafe',
}

/** Severity is quiet text with a dot, not a third pill (docs/design/ui-brief.md, 3.3). */
export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium whitespace-nowrap text-foreground">
      <span aria-hidden="true" className={cn('size-1.5 shrink-0 rounded-full', TONE_DOT[SEVERITY[severity]])} />
      {severity} severity
    </span>
  )
}
