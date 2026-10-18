// Administration form rules, checked in the browser for usability only; the server
// re-validates everything (CO-3). Money stays a decimal string (CO-6).

import { z } from 'zod'

import { DOCUMENT_TYPES, FUEL_TYPES, STAFF_ROLES } from '@/api/admin'

const MONEY = /^\d{1,10}(\.\d{1,2})?$/
const required = (label: string) => z.string().trim().min(1, { error: `Enter the ${label}.` })
const money = (label: string) =>
  required(label).regex(MONEY, { error: `Enter the ${label} in rupees, for example 150 or 150.50.` })
const wholeNumber = (label: string) =>
  required(label).regex(/^\d{1,7}$/, { error: `Enter the ${label} as a whole number.` })

// Fleet.Add (UC 11 step 1): the master data, photos and each statutory document's expiry.
export const vehicleSchema = z.object({
  registration_no: required('registration number').max(16),
  category: z.string().min(1, { error: 'Choose the category.' }),
  brand: required('brand').max(64),
  model: required('model').max(64),
  year: required('year').regex(/^(19|20|21)\d{2}$/, { error: 'Enter a year such as 2025.' }),
  colour: required('colour').max(32),
  fuel_type: z.enum(FUEL_TYPES, { error: 'Choose the fuel type.' }),
  transmission: z.string(),
  seating_capacity: z.string(),
  engine_cc: z.string(),
  chassis_number: required('chassis number').max(32),
  home_branch: z.string().min(1, { error: 'Choose the home branch.' }),
  odometer: wholeNumber('odometer reading'),
  fuel_capacity: required('capacity').regex(/^(?=.*[1-9])\d{1,4}(\.\d{1,2})?$/, {
    error: 'Enter the capacity, for example 37 or 5.5.',
  }),
  available_from: z.string().min(1, { error: 'Enter the date it can first be booked.' }),
  expiry_insurance: expiry('Insurance'),
  expiry_pollution_certificate: expiry('Pollution Certificate'),
  expiry_fitness_certificate: expiry('Fitness Certificate'),
  expiry_road_tax: expiry('Road Tax'),
})
export type VehicleValues = z.infer<typeof vehicleSchema>

function expiry(type: (typeof DOCUMENT_TYPES)[number]) {
  return z.string().min(1, { error: `Enter the ${type.toLowerCase()} expiry date.` })
}

/** The form field holding a statutory document's expiry date. */
export const DOCUMENT_FIELDS = {
  Insurance: 'expiry_insurance',
  'Pollution Certificate': 'expiry_pollution_certificate',
  'Fitness Certificate': 'expiry_fitness_certificate',
  'Road Tax': 'expiry_road_tax',
} as const satisfies Record<(typeof DOCUMENT_TYPES)[number], keyof VehicleValues>

// Fleet.Tariff (BR-13): the rates for a category from an effective date (empty: now).
export const tariffSchema = z.object({
  vehicle_category: z.string().min(1, { error: 'Choose the category.' }),
  hourly_rate: money('hourly rate'),
  daily_rate: money('daily rate'),
  weekly_rate: money('weekly rate'),
  free_km_allowance: wholeNumber('free kilometres'),
  excess_km_rate: money('excess-kilometre rate'),
  effective_from: z.string(),
})
export type TariffValues = z.infer<typeof tariffSchema>

// Fleet.Users (UC 12 step 1).
export const staffSchema = z
  .object({
    role: z.enum(STAFF_ROLES, { error: 'Choose the role.' }),
    name: required('name').max(150),
    email: z.email({ error: 'Enter a valid e-mail address.' }),
    mobile_no: z.string().regex(/^\+?[0-9]{10,15}$/, {
      error: 'Enter a mobile number of 10 to 15 digits, optionally starting with +.',
    }),
    address: z.string().max(1000),
    branch: z.string(),
    workshop: z.string().max(150),
    password: z.string().min(8, { error: 'Use at least 8 characters.' }),
  })
  .refine((data) => data.role === 'MAINTENANCE_TECHNICIAN' || data.branch !== '', {
    path: ['branch'],
    error: 'Assign the account to a branch.',
  })
  .refine((data) => data.role !== 'MAINTENANCE_TECHNICIAN' || data.workshop.trim() !== '', {
    path: ['workshop'],
    error: "Enter the technician's workshop.",
  })
export type StaffValues = z.infer<typeof staffSchema>
