import { ApiError, apiRequest } from './client'
import type { Health } from './types'

export type { Health }

// GET /api/v1/health/ — public. The only source of the agency name and
// currency in the frontend (D7); never hardcode either.
export async function getHealth(): Promise<Health> {
  try {
    return await apiRequest<Health>('/api/v1/health/', { auth: false })
  } catch (error) {
    // 503 still carries a full health body (database unreachable).
    if (error instanceof ApiError && error.status === 503) {
      return error.body as Health
    }
    throw error
  }
}
