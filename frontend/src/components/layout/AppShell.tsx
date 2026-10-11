import { CircleHelp, LogOut, Menu } from 'lucide-react'
import { useState } from 'react'
import { Link, Outlet } from 'react-router-dom'

import { ROLE_LABELS } from '@/api/types'
import { navItemsFor } from '@/app/navigation'
import { SkipLink } from '@/components/page'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { useSignedInUser, useAuth } from '@/features/auth/auth-context'
import { useAgency, useRouteFocus } from '@/hooks/page'
import { useScrolled } from '@/hooks/scroll'
import { cn } from '@/lib/utils'

import { NavList } from './NavList'

function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || '?'
  )
}

/**
 * The signed-in layout (UI-1, UI-2): every screen shows the application
 * name, who is signed in, a help link and sign-out in the same places.
 * Navigation is a fixed sidebar on wider screens and a drawer on phones
 * (OE-3); the top bar is slim (docs/design/ui-brief.md, 6.0).
 */
export function AppShell() {
  const user = useSignedInUser()
  const { signOut } = useAuth()
  const agency = useAgency()
  const items = navItemsFor(user.role)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const mainRef = useRouteFocus<HTMLElement>()
  const roleLabel = ROLE_LABELS[user.role]
  // The top bar shows its hairline edge once content has scrolled under it (B5).
  const scrolled = useScrolled()

  const brandLink = (className: string) => (
    <Link
      to="/app"
      className={cn(
        'heading min-w-0 truncate rounded-sm text-foreground',
        className,
      )}
    >
      {agency.name}
    </Link>
  )

  return (
    <div className="min-h-svh bg-background text-foreground">
      <SkipLink />
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[17rem] flex-col border-r border-sidebar-border bg-sidebar md:flex">
        <div className="flex h-16 shrink-0 items-center border-b border-sidebar-border px-6">
          {brandLink('text-subsection')}
        </div>
        <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto">
          <NavList items={items} />
        </nav>
      </aside>

      <div className="md:pl-[17rem]">
        <header
          data-scrolled={scrolled ? '' : undefined}
          className="sticky top-0 z-20 border-b border-transparent bg-background transition-colors duration-200 data-scrolled:border-hairline"
        >
          <div className="flex h-16 items-center gap-2 px-3 sm:px-6 lg:px-8">
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon-lg" className="-ml-1 md:hidden" aria-label="Open menu">
                  <Menu aria-hidden="true" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-72 gap-0 bg-sidebar p-0">
                <SheetHeader className="border-b border-sidebar-border px-6 py-4">
                  <SheetTitle className="pr-8">{agency.name}</SheetTitle>
                  <SheetDescription>
                    {user.name} · {roleLabel}
                  </SheetDescription>
                </SheetHeader>
                <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto">
                  <NavList items={items} onNavigate={() => setDrawerOpen(false)} />
                </nav>
              </SheetContent>
            </Sheet>

            {brandLink('text-subsection md:hidden')}

            <div className="ml-auto flex items-center gap-1 sm:gap-2">
              <div className="flex items-center gap-2.5 pr-1 sm:pr-2">
                <span className="sr-only">
                  Signed in as {user.name}, {roleLabel}
                </span>
                <span
                  aria-hidden="true"
                  className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary-tint text-xs font-semibold text-primary"
                >
                  {initials(user.name)}
                </span>
                <span aria-hidden="true" className="hidden text-right sm:block">
                  <span className="block max-w-56 truncate text-sm leading-5 font-medium">{user.name}</span>
                  <span className="block text-small leading-4 text-muted-foreground">{roleLabel}</span>
                </span>
              </div>
              <Button asChild variant="ghost" className="px-2.5 sm:px-3">
                <Link to="/help" aria-label="Help">
                  <CircleHelp aria-hidden="true" />
                  <span className="hidden sm:inline">Help</span>
                </Link>
              </Button>
              <Button variant="outline" className="px-2.5 sm:px-3" onClick={() => void signOut()} aria-label="Sign out">
                <LogOut aria-hidden="true" />
                <span className="hidden sm:inline">Sign out</span>
              </Button>
            </div>
          </div>
        </header>

        <main
          id="main-content"
          ref={mainRef}
          tabIndex={-1}
          className="min-w-0 px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8"
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
