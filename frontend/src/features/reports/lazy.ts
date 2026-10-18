import { lazy } from 'react'

// Loaded on demand, so the charts (Recharts) are not in every other page's bundle (PE-6).
export const ReportsPage = lazy(() => import('./ReportsPage').then((module) => ({ default: module.ReportsPage })))
