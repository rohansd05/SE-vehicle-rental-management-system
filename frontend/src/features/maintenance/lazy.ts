import { lazy } from 'react'

// Loaded on demand (Module N4): the maintenance screens are not in every other page's bundle.
export const ClearanceQueuePage = lazy(() => import('./ClearanceQueuePage').then((module) => ({ default: module.ClearanceQueuePage })))
export const JobDetailPage = lazy(() => import('./JobDetailPage').then((module) => ({ default: module.JobDetailPage })))
export const BranchJobsPage = lazy(() => import('./JobsPage').then((module) => ({ default: module.BranchJobsPage })))
export const MyJobsPage = lazy(() => import('./JobsPage').then((module) => ({ default: module.MyJobsPage })))
export const ReportFaultPage = lazy(() => import('./ReportFaultPage').then((module) => ({ default: module.ReportFaultPage })))
export const VehicleHistoryPage = lazy(() => import('./VehicleHistoryPage').then((module) => ({ default: module.VehicleHistoryPage })))
