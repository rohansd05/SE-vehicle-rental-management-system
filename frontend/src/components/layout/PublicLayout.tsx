import { CircleHelp } from 'lucide-react'
import { Link, Outlet, useLocation } from 'react-router-dom'

import { SkipLink } from '@/components/page'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-context'
import { useAgency, useRouteFocus } from '@/hooks/page'
import { useScrolled } from '@/hooks/scroll'
import { cn } from '@/lib/utils'

/**
 * Layout for pages anyone can open: home, sign-in, registration, help
 * (docs/design/ui-brief.md, 6.1 and 6.2). The top bar stays at the top and
 * shows its hairline edge once content scrolls under it (B5). The landing
 * page sets its own gutters, because its hero and bands run edge to edge.
 */
export function PublicLayout() {
  const { status } = useAuth()
  const agency = useAgency()
  const mainRef = useRouteFocus<HTMLElement>()
  const scrolled = useScrolled()
  const isLanding = useLocation().pathname === '/'

  return (
    <div className="flex min-h-svh flex-col bg-background text-foreground">
      <SkipLink />
      <header
        data-scrolled={scrolled ? '' : undefined}
        className="sticky top-0 z-20 border-b border-transparent bg-background transition-colors duration-200 data-scrolled:border-hairline"
      >
        <div className="flex h-16 w-full items-center gap-2 px-4 sm:px-6 lg:px-8">
          <Link
            to="/"
            className="heading min-w-0 truncate rounded-sm text-subsection text-foreground"
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
        className={cn('flex-1 outline-none', isLanding ? null : 'px-4 py-8 sm:px-6 lg:px-8 lg:py-10')}
      >
        <Outlet />
      </main>
    </div>
  )
}
