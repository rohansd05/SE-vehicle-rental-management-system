// MSW: the API, mocked at the network layer, so the real client, auth
// provider and screens run unchanged in tests.

import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { Role } from '@/api/types'
import { EMPTY_REPORTS, makeDashboard } from '@/features/reports/fixtures'

export const API = '*/api/v1'

/** A JWT-shaped access token that expires `seconds` from now (unsigned; tests only). */
export function makeAccessToken(seconds = 300, userId = 1): string {
  const encode = (value: object) =>
    btoa(JSON.stringify(value)).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
  const exp = Math.floor(Date.now() / 1000) + seconds
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ user_id: String(userId), exp })}.sig`
}

export const USERS: Record<Role, { id: number; email: string; name: string; role: Role }> = {
  CUSTOMER: { id: 1, email: 'customer@vrms.test', name: 'Asha Rao', role: 'CUSTOMER' },
  BRANCH_STAFF: { id: 2, email: 'staff@vrms.test', name: 'Ravi Staff', role: 'BRANCH_STAFF' },
  MAINTENANCE_TECHNICIAN: {
    id: 3,
    email: 'tech@vrms.test',
    name: 'Tara Tech',
    role: 'MAINTENANCE_TECHNICIAN',
  },
  ADMINISTRATOR: { id: 4, email: 'admin@vrms.test', name: 'Anil Admin', role: 'ADMINISTRATOR' },
  BRANCH_MANAGER: {
    id: 5,
    email: 'manager@vrms.test',
    name: 'Meera Manager',
    role: 'BRANCH_MANAGER',
  },
}

export const healthHandler = http.get(`${API}/health/`, () =>
  HttpResponse.json({ status: 'ok', database: 'ok', agency_name: 'Test Rentals', currency: 'INR' }),
)

const sessionEnded = () =>
  HttpResponse.json({ detail: 'Your session has ended. Please sign in again.', code: 'session_ended' }, { status: 401 })

export const defaultHandlers = [
  healthHandler,
  http.post(`${API}/auth/refresh/`, sessionEnded), // no session to restore
  http.post(`${API}/auth/logout/`, () => new HttpResponse(null, { status: 204 })),
  // The customer home page asks for the outstanding due (Pay.Dues); none by default.
  http.get(`${API}/payments/due/`, () => HttpResponse.json({ outstanding_due: '0.00' })),
  // The Administrator's and Branch Manager's home and Reports pages (Report.Dashboard, UC 14).
  http.get(`${API}/reports/summary/`, () => HttpResponse.json(makeDashboard())),
  http.get(`${API}/reports/:type/`, ({ params }) =>
    HttpResponse.json(EMPTY_REPORTS[params.type as keyof typeof EMPTY_REPORTS]),
  ),
]

export const server = setupServer(...defaultHandlers)

/** Make the page-load refresh restore a session for this role. */
export function signedInAs(role: Role, tokenSeconds = 300) {
  server.use(
    http.post(`${API}/auth/refresh/`, () =>
      HttpResponse.json({ access: makeAccessToken(tokenSeconds, USERS[role].id), user: USERS[role] }),
    ),
  )
  return USERS[role]
}
