import { CircleHelp } from 'lucide-react'
import { Link, Outlet } from 'react-router-dom'

import { SkipLink } from '@/components/page'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-context'
import { useAgency, useRouteFocus } from '@/hooks/page'

/** Layout for pages anyone can open: home, sign-in, registration, help. */
export function PublicLayout() {
  const { status } = useAuth()
  const agency = useAgency()
  const mainRef = useRouteFocus<HTMLElement>()

  return (
    <div className="flex min-h-svh flex-col bg-background text-foreground">
      <SkipLink />
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-2 px-4">
          <Link
            to="/"
            className="min-w-0 truncate rounded-sm font-semibold tracking-tight focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {agency.name}
          </Link>
          <nav aria-label="Account" className="ml-auto flex items-center gap-1">
            <Button asChild variant="ghost" size="lg">
              <Link to="/help" aria-label="Help">
                <CircleHelp aria-hidden="true" />
                <span className="hidden sm:inline">Help</span>
              </Link>
            </Button>
            {status === 'signed-in' ? (
              <Button asChild size="lg">
                <Link to="/app">My account</Link>
              </Button>
            ) : (
              <>
                <Button asChild variant="ghost" size="lg">
                  <Link to="/login">Sign in</Link>
                </Button>
                <Button asChild size="lg">
                  <Link to="/register">Register</Link>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>
      <main
        id="main-content"
        ref={mainRef}
        tabIndex={-1}
        className="flex-1 px-4 py-8 outline-none"
      >
        <div className="mx-auto max-w-5xl">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
