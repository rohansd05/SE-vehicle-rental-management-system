import type { RefundStatus } from './api'

export const DUE_KEY = ['payments', 'due'] as const
export const REFUNDS_KEY = ['payments', 'refunds'] as const
export const refundsKey = (status: RefundStatus) => ['payments', 'refunds', status] as const
export const AWAITING_CASH_KEY = ['bookings', 'awaiting-cash'] as const
