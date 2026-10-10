import {
  ArrowLeftRight,
  Building2,
  CalendarDays,
  Car,
  ChartColumn,
  CircleUser,
  House,
  IdCard,
  type LucideIcon,
  ScrollText,
  Search,
  ShieldCheck,
  Tags,
  Users,
  Wrench,
} from 'lucide-react'

import { ROLES, type Role } from '@/api/types'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  roles: readonly Role[]
  /** false: the feature is planned for a later phase; its page says so honestly. */
  available: boolean
  description: string
}

const ALL: readonly Role[] = ROLES

// One entry per screen of the signed-in app (UI-1: the menu follows the role).
export const NAV_ITEMS: readonly NavItem[] = [
  {
    to: '/app',
    label: 'Home',
    icon: House,
    roles: ALL,
    available: true,
    description: 'Your starting point.',
  },
  {
    to: '/app/search',
    label: 'Find a vehicle',
    icon: Search,
    roles: ['CUSTOMER'],
    available: false,
    description: 'Search cars and two-wheelers that are free for your dates.',
  },
  {
    to: '/app/bookings',
    label: 'My bookings',
    icon: CalendarDays,
    roles: ['CUSTOMER'],
    available: false,
    description: 'Your bookings, invoices and rental history.',
  },
  {
    to: '/app/licence',
    label: 'Driving licence',
    icon: IdCard,
    roles: ['CUSTOMER'],
    available: true,
    description: 'Submit your licence for verification and see its status.',
  },
  {
    to: '/app/licences',
    label: 'Licence checks',
    icon: ShieldCheck,
    roles: ['BRANCH_STAFF', 'ADMINISTRATOR'],
    available: true,
    description: 'Verify the driving licences customers have submitted.',
  },
  {
    to: '/app/handover',
    label: 'Handover and return',
    icon: ArrowLeftRight,
    roles: ['BRANCH_STAFF'],
    available: false,
    description: 'Hand vehicles over to customers and record their return.',
  },
  {
    to: '/app/branch-bookings',
    label: 'Branch bookings',
    icon: Building2,
    roles: ['BRANCH_STAFF', 'BRANCH_MANAGER'],
    available: false,
    description: "Today's collections and returns at your branch.",
  },
  {
    to: '/app/jobs',
    label: 'Maintenance jobs',
    icon: Wrench,
    roles: ['MAINTENANCE_TECHNICIAN'],
    available: false,
    description: 'The jobs assigned to you, and the work and parts you record.',
  },
  {
    to: '/app/fleet',
    label: 'Fleet',
    icon: Car,
    roles: ['ADMINISTRATOR'],
    available: false,
    description: 'Vehicles, branches and statutory documents.',
  },
  {
    to: '/app/tariffs',
    label: 'Tariffs',
    icon: Tags,
    roles: ['ADMINISTRATOR'],
    available: false,
    description: 'Tariffs, add-ons and discount codes.',
  },
  {
    to: '/app/users',
    label: 'Users',
    icon: Users,
    roles: ['ADMINISTRATOR'],
    available: false,
    description: 'Staff accounts and the customer blacklist.',
  },
  {
    to: '/app/reports',
    label: 'Reports',
    icon: ChartColumn,
    roles: ['ADMINISTRATOR', 'BRANCH_MANAGER'],
    available: false,
    description: 'Utilisation, revenue and maintenance-cost reports.',
  },
  {
    to: '/app/audit',
    label: 'Audit log',
    icon: ScrollText,
    roles: ['ADMINISTRATOR'],
    available: false,
    description: 'Every change to fleet, tariff, branch and user data.',
  },
  {
    to: '/app/profile',
    label: 'My profile',
    icon: CircleUser,
    roles: ALL,
    available: true,
    description: 'Your details, mobile number and password.',
  },
]

export function navItemsFor(role: Role): NavItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role))
}

/** Planned features: each gets an honest "not available yet" page. */
export const UPCOMING_ITEMS = NAV_ITEMS.filter((item) => !item.available)
