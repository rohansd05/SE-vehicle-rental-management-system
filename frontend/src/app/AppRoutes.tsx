import { Route, Routes } from 'react-router-dom'

import { HomePage } from '@/components/HomePage'
import { AppShell } from '@/components/layout/AppShell'
import { PublicLayout } from '@/components/layout/PublicLayout'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { VerifyOtpPage } from '@/features/auth/VerifyOtpPage'
import { LicenceQueuePage } from '@/features/licence/LicenceQueuePage'
import { LicenceReviewPage } from '@/features/licence/LicenceReviewPage'
import { MyLicencePage } from '@/features/licence/MyLicencePage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { DashboardPage } from '@/pages/DashboardPage'
import { HelpPage } from '@/pages/HelpPage'
import { NotAvailablePage } from '@/pages/NotAvailablePage'
import { NotFoundPage } from '@/pages/NotFoundPage'

import { RedirectIfSignedIn, RequireAuth, RequireRole } from './guards'
import { UPCOMING_ITEMS } from './navigation'

/** Branch Staff and Administrators verify licences (SE-10). */
const LICENCE_VERIFIERS = ['BRANCH_STAFF', 'ADMINISTRATOR'] as const

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<HomePage />} />
        <Route
          path="login"
          element={
            <RedirectIfSignedIn>
              <LoginPage />
            </RedirectIfSignedIn>
          }
        />
        <Route
          path="register"
          element={
            <RedirectIfSignedIn>
              <RegisterPage />
            </RedirectIfSignedIn>
          }
        />
        <Route
          path="verify"
          element={
            <RedirectIfSignedIn>
              <VerifyOtpPage />
            </RedirectIfSignedIn>
          }
        />
        <Route path="help" element={<HelpPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route
        path="app"
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route
          path="licence"
          element={
            <RequireRole roles={['CUSTOMER']}>
              <MyLicencePage />
            </RequireRole>
          }
        />
        <Route
          path="licences"
          element={
            <RequireRole roles={LICENCE_VERIFIERS}>
              <LicenceQueuePage />
            </RequireRole>
          }
        />
        <Route
          path="licences/:id"
          element={
            <RequireRole roles={LICENCE_VERIFIERS}>
              <LicenceReviewPage />
            </RequireRole>
          }
        />
        {UPCOMING_ITEMS.map((item) => (
          <Route
            key={item.to}
            path={item.to.replace('/app/', '')}
            element={
              <RequireRole roles={item.roles}>
                <NotAvailablePage item={item} />
              </RequireRole>
            }
          />
        ))}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
