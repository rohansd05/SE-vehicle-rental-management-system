// Maintenance form rules, checked in the browser for usability only; the
// server re-validates everything (CO-3). Money and quantities stay decimal
// strings and are never turned into floating-point numbers (CO-6).

import { z } from 'zod'

import { JOB_TYPES, SEVERITIES } from '@/api/maintenance'
import { todayISO } from '@/lib/dates'

const MONEY = /^\d{1,10}(\.\d{1,2})?$/
const POSITIVE_DECIMAL = /^(?=.*[1-9])\d{1,8}(\.\d{1,2})?$/

const money = (label: string) =>
  z
    .string()
    .trim()
    .min(1, { error: `Enter the ${label}.` })
    .regex(MONEY, { error: `Enter the ${label} in rupees, for example 1450 or 1450.50.` })

// Maint.Create, Maint.Unsafe.
export const reportSchema = z.object({
  vehicle: z.string().min(1, { error: 'Choose the vehicle.' }),
  job_type: z.enum(JOB_TYPES, { error: 'Choose the job type.' }),
  severity: z.enum(SEVERITIES, { error: 'Choose the severity.' }),
  reported_problem: z
    .string()
    .trim()
    .min(1, { error: 'Describe the problem.' })
    .max(2000, { error: 'Keep the description under 2,000 characters.' }),
  flag_unsafe: z.boolean(),
})
export type ReportValues = z.infer<typeof reportSchema>

// Maint.Schedule.
export const scheduleSchema = z
  .object({
    technician: z.string().min(1, { error: 'Choose a technician.' }),
    scheduled_from: z.string().min(1, { error: 'Enter when the work starts.' }),
    scheduled_to: z.string().min(1, { error: 'Enter when the work ends.' }),
  })
  .refine((data) => !data.scheduled_from || !data.scheduled_to || data.scheduled_to > data.scheduled_from, {
    path: ['scheduled_to'],
    error: 'The end must be after the start.',
  })
export type ScheduleValues = z.infer<typeof scheduleSchema>

// Maint.Record.
export const recordSchema = z.object({
  service_date: z
    .string()
    .min(1, { error: 'Enter the service date.' })
    .refine((value) => value <= todayISO(), { error: 'The service date cannot be in the future.' }),
  odometer_at_service: z
    .string()
    .trim()
    .min(1, { error: 'Enter the odometer reading.' })
    .regex(/^\d{1,7}$/, { error: 'Enter the reading in whole kilometres.' }),
  work_description: z
    .string()
    .trim()
    .min(1, { error: 'Describe the work performed.' })
    .max(5000, { error: 'Keep the description under 5,000 characters.' }),
  labour_cost: money('labour cost'),
  downtime_hours: z
    .string()
    .trim()
    .min(1, { error: 'Enter the downtime.' })
    .regex(/^\d{1,5}(\.\d{1,2})?$/, { error: 'Enter the downtime in hours, for example 6 or 6.5.' }),
  parts: z.array(
    z.object({
      part_name: z.string().trim().min(1, { error: 'Name the part.' }).max(150),
      quantity: z
        .string()
        .trim()
        .regex(POSITIVE_DECIMAL, { error: 'Enter a quantity above 0.' }),
      unit_cost: money('unit cost'),
    }),
  ),
})
export type RecordValues = z.infer<typeof recordSchema>

export const cancelSchema = z.object({
  reason: z.string().trim().min(1, { error: 'Give a reason.' }).max(1000),
})
export type CancelValues = z.infer<typeof cancelSchema>

/** A datetime-local value ("2026-10-14T10:00") as a UTC ISO timestamp (CO-6). */
export const localToISO = (value: string) => new Date(value).toISOString()
