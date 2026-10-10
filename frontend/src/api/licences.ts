// Driving-licence endpoints (Book.Eligible.*, BR-2, BR-3, SE-10, SI-3).

import { apiRequest } from './client'
import type { Licence, LicenceCategory, LicenceReview, PaginatedLicenceReviews } from './types'

export interface LicenceSubmission {
  licence_number: string
  issuing_authority: string
  issue_date: string
  expiry_date: string
  categories: LicenceCategory[]
  front_image: File
  back_image: File
}

export const getMyLicence = () => apiRequest<Licence>('/api/v1/licence/')

export function submitLicence(data: LicenceSubmission) {
  const form = new FormData()
  form.append('licence_number', data.licence_number)
  form.append('issuing_authority', data.issuing_authority)
  form.append('issue_date', data.issue_date)
  form.append('expiry_date', data.expiry_date)
  for (const category of data.categories) form.append('categories', category)
  form.append('front_image', data.front_image)
  form.append('back_image', data.back_image)
  return apiRequest<Licence>('/api/v1/licence/', { method: 'POST', form })
}

export const listPendingLicences = () =>
  apiRequest<PaginatedLicenceReviews>('/api/v1/licences/')

export const approveLicence = (id: number) =>
  apiRequest<LicenceReview>(`/api/v1/licences/${id}/approve/`, { method: 'POST' })

export const rejectLicence = (id: number, reason: string) =>
  apiRequest<LicenceReview>(`/api/v1/licences/${id}/reject/`, {
    method: 'POST',
    json: { reason },
  })
