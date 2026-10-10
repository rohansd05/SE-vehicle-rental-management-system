// Friendly names for the generated OpenAPI types (npm run api:types).

import type { components } from './schema'

type Schemas = components['schemas']

export type Role = Schemas['RoleEnum']
export type UserSummary = Schemas['UserSummary']
export type SessionUser = Required<Pick<UserSummary, 'id' | 'email' | 'name' | 'role'>>
export type AccessTokenResponse = Schemas['AccessToken']
export type RegisterRequest = Schemas['Register']
export type RegisterResponse = Schemas['RegisterResponse']
export type Profile = Schemas['Profile']
export type ProfileUpdate = Schemas['PatchedProfileUpdate']
export type ProfileUpdateResponse = Schemas['ProfileUpdateResponse']
export type PasswordChangeRequest = Schemas['PasswordChange']
export type Licence = Schemas['Licence']
export type LicenceReview = Schemas['LicenceReview']
export type LicenceStatus = Schemas['LicenceStatusEnum']
export type LicenceCategory = Schemas['CategoriesEnum']
export type PaginatedLicenceReviews = Schemas['PaginatedLicenceReviewList']
export type Health = Schemas['Health']
export type Detail = Schemas['Detail']

export const ROLES = [
  'CUSTOMER',
  'BRANCH_STAFF',
  'MAINTENANCE_TECHNICIAN',
  'ADMINISTRATOR',
  'BRANCH_MANAGER',
] as const satisfies readonly Role[]

export const ROLE_LABELS: Record<Role, string> = {
  CUSTOMER: 'Customer',
  BRANCH_STAFF: 'Branch Staff',
  MAINTENANCE_TECHNICIAN: 'Maintenance Technician',
  ADMINISTRATOR: 'Administrator',
  BRANCH_MANAGER: 'Branch Manager',
}

/** The API always sends these fields; the schema marks two of them optional. */
export function toSessionUser(user: UserSummary): SessionUser {
  if (user.id === undefined || user.role === undefined) {
    throw new Error('The server sent an incomplete user.')
  }
  return { id: user.id, email: user.email, name: user.name, role: user.role }
}
