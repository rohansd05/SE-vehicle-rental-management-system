import type { AddOnChoice, BookingStatus, Period } from './api'

export const vehicleKey = (id: number) => ['fleet', 'vehicle', id] as const
export const addOnsKey = (vehicleType: string) => ['pricing', 'add-ons', vehicleType] as const
export const quoteKey = (vehicle: number, period: Period, addOns: AddOnChoice[], code: string) =>
  ['pricing', 'quote', vehicle, period, addOns, code] as const
export const BOOKINGS_KEY = ['bookings'] as const
export const bookingsKey = (status: BookingStatus | '', page: number) => ['bookings', 'list', status, page] as const
export const bookingKey = (id: number) => ['bookings', 'detail', id] as const
