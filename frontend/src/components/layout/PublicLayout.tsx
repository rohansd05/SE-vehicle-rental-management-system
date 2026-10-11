import { CircleHelp } from 'lucide-react'
import { Link, Outlet } from 'react-router-dom'

import { SkipLink } from '@/components/page'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-context'
import { useAgency, useRouteFocus } from '@/hooks/page'

/** Layout for pages anyone can open: home, sign-in, registration, help (docs/design/ui-brief.md, 6.1 and 6.2). */
export function PublicLayout() {
  const { status } = useAuth()
  const agency = useAgency()
  const mainRef = useRouteFocus<HTMLElement>()

  return (
    <div className="flex min-h-svh flex-col bg-background text-foreground">
      <SkipLink />
      <header className="border-b">
        <div className="mx-auto flex h-14 w-full max-w-[80rem] items-center gap-2 px-4 sm:px-6 lg:px-8">
          <Link
            to="/"
            className="min-w-0 truncate rounded-sm font-heading text-[15px] font-semibold text-foreground [font-stretch:108%]"
          >
            {agency.name}
          </Link>
          <nav aria-label="Account" className="ml-auto flex items-center gap-1 sm:gap-2">
            <Button asChild variant="ghost" className="px-2.5 sm:px-3">
              <Link to="/help" aria-label="Help">
                <CircleHelp aria-hidden="true" />
                <span className="hidden sm:inline">Help</span>
              </Link>
            </Button>
            {status === 'signed-in' ? (
              <Button asChild>
                <Link to="/app">My account</Link>
              </Button>
            ) : (
              <>
                <Button asChild variant="ghost" className="px-3">
                  <Link to="/login">Sign in</Link>
                </Button>
                <Button asChild className="px-3 sm:px-4">
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
        className="flex-1 px-4 py-8 outline-none sm:px-6 lg:px-8 lg:py-10"
      >
        <div className="mx-auto w-full max-w-[80rem]">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
