import { lazy } from 'react'

// Loaded on demand (Module N4): the administration screens are not in every other page's bundle.
export const AuditPage = lazy(() => import('./AuditPage').then((module) => ({ default: module.AuditPage })))
export const BranchesPage = lazy(() => import('./BranchesPage').then((module) => ({ default: module.BranchesPage })))
export const CustomerPage = lazy(() => import('./CustomerPage').then((module) => ({ default: module.CustomerPage })))
export const FleetPage = lazy(() => import('./FleetPage').then((module) => ({ default: module.FleetPage })))
export const StaffFormPage = lazy(() => import('./StaffPages').then((module) => ({ default: module.StaffFormPage })))
export const StaffPage = lazy(() => import('./StaffPages').then((module) => ({ default: module.StaffPage })))
export const TariffsPage = lazy(() => import('./TariffsPage').then((module) => ({ default: module.TariffsPage })))
export const UsersPage = lazy(() => import('./UsersPage').then((module) => ({ default: module.UsersPage })))
export const VehicleFormPage = lazy(() => import('./VehicleFormPage').then((module) => ({ default: module.VehicleFormPage })))
export const VehiclePage = lazy(() => import('./VehiclePage').then((module) => ({ default: module.VehiclePage })))
