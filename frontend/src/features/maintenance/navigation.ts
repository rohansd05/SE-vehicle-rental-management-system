// Menu entries for the maintenance screens, spread into NAV_ITEMS by one line.
// The technician's "Maintenance jobs" entry (/app/jobs) stays in app/navigation.ts.

import { ShieldAlert, Wrench } from 'lucide-react'

import type { NavItem } from '@/app/navigation'

export const MAINTENANCE_NAV_ITEMS: readonly NavItem[] = [
  {
    to: '/app/maintenance',
    label: 'Maintenance',
    icon: Wrench,
    roles: ['BRANCH_STAFF', 'BRANCH_MANAGER', 'ADMINISTRATOR'],
    available: true,
    description: 'Report faults, assign technicians and follow your branch’s jobs.',
  },
  {
    to: '/app/clearances',
    label: 'Unsafe clearances',
    icon: ShieldAlert,
    roles: ['ADMINISTRATOR'],
    available: true,
    description: 'Review completed work on Unsafe vehicles and clear the flag (BR-16).',
  },
]
