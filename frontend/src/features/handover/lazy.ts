import { lazy } from 'react'

// Loaded on demand (Module N4): the handover and return screens are not in every other page's bundle.
export const BranchBookingsPage = lazy(() => import('./CollectionsPage').then((module) => ({ default: module.BranchBookingsPage })))
export const HandoverDeskPage = lazy(() => import('./CollectionsPage').then((module) => ({ default: module.HandoverDeskPage })))
export const HandoverPage = lazy(() => import('./HandoverPage').then((module) => ({ default: module.HandoverPage })))
export const ReturnPage = lazy(() => import('./ReturnPage').then((module) => ({ default: module.ReturnPage })))
