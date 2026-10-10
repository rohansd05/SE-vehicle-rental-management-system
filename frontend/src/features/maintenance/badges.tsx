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
import { Badge } from '@/components/ui/badge'

const JOB: Record<JobStatus, { icon: LucideIcon; className: string }> = {
  Reported: { icon: CircleDashed, className: 'bg-muted text-foreground' },
  Scheduled: { icon: Clock, className: 'bg-sky-600/10 text-sky-800 dark:text-sky-300' },
  'In Progress': {
    icon: Hammer,
    className: 'bg-amber-500/15 text-amber-900 dark:text-amber-300',
  },
  Completed: {
    icon: CircleCheck,
    className: 'bg-emerald-600/10 text-emerald-800 dark:text-emerald-300',
  },
  Cancelled: { icon: CircleSlash, className: 'bg-muted text-muted-foreground' },
}

/** The job's status, or "Awaiting clearance" while an Administrator must clear it (BR-16). */
export function JobStatusBadge({ job }: { job: Pick<MaintenanceJob, 'status' | 'awaiting_clearance'> }) {
  if (job.awaiting_clearance) {
    return (
      <Badge variant="secondary" className="bg-destructive/10 text-destructive">
        <ShieldAlert aria-hidden="true" />
        Awaiting clearance
      </Badge>
    )
  }
  const { icon: Icon, className } = JOB[job.status]
  return (
    <Badge variant="secondary" className={className}>
      <Icon aria-hidden="true" />
      {job.status}
    </Badge>
  )
}

const SEVERITY: Record<Severity, string> = {
  Low: 'border-border text-muted-foreground',
  Medium: 'border-border text-foreground',
  High: 'border-amber-600/50 text-amber-900 dark:text-amber-300',
  Critical: 'border-destructive/60 text-destructive',
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge variant="outline" className={SEVERITY[severity]}>
      {severity} severity
    </Badge>
  )
}
