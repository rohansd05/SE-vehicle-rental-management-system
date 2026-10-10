// Book Vehicle routes (vehicle detail, payment, history), mounted under /app
// by one line in AppRoutes. Returned as a fragment of <Route>s (not a
// component) so <Routes> can read them. RequireRole only shapes the screen;
// the API refuses anyone but the customer who owns the booking (SE-4, SE-5).

import type { ReactNode } from 'react'
import { Route } from 'react-router-dom'

import { RequireRole } from '@/app/guards'
import { BookingDetailPage } from '@/features/history/BookingDetailPage'
import { BookingHistoryPage } from '@/features/history/BookingHistoryPage'
import { PaymentPage } from '@/features/payment/PaymentPage'

import { VehicleDetailPage } from './VehicleDetailPage'

const customer = (page: ReactNode) => <RequireRole roles={['CUSTOMER']}>{page}</RequireRole>

export function bookingRoutes() {
  return (
    <>
      <Route path="vehicles/:id" element={customer(<VehicleDetailPage />)} />
      <Route path="bookings" element={customer(<BookingHistoryPage />)} />
      <Route path="bookings/:id" element={customer(<BookingDetailPage />)} />
      <Route path="bookings/:id/pay" element={customer(<PaymentPage />)} />
    </>
  )
}
