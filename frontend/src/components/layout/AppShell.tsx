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
 * Navigation is a sidebar on wider screens and a drawer on phones (OE-3).
 */
export function AppShell() {
  const user = useSignedInUser()
  const { signOut } = useAuth()
  const agency = useAgency()
  const items = navItemsFor(user.role)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const mainRef = useRouteFocus<HTMLElement>()
  const roleLabel = ROLE_LABELS[user.role]

  return (
    <div className="min-h-svh bg-background text-foreground">
      <SkipLink />
      <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex h-14 items-center gap-2 px-3 sm:px-4">
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon-lg" className="md:hidden" aria-label="Open menu">
                <Menu aria-hidden="true" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-0">
              <SheetHeader className="border-b">
                <SheetTitle>{agency.name}</SheetTitle>
                <SheetDescription>
                  {user.name} · {roleLabel}
                </SheetDescription>
              </SheetHeader>
              <nav aria-label="Main">
                <NavList items={items} onNavigate={() => setDrawerOpen(false)} />
              </nav>
            </SheetContent>
          </Sheet>

          <Link
            to="/app"
            className="min-w-0 truncate rounded-sm font-semibold tracking-tight focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {agency.name}
          </Link>

          <div className="ml-auto flex items-center gap-1">
            <div className="flex items-center gap-2 pr-1">
              <span className="sr-only">
                Signed in as {user.name}, {roleLabel}
              </span>
              <span
                aria-hidden="true"
                className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary"
              >
                {initials(user.name)}
              </span>
              <span aria-hidden="true" className="hidden text-right leading-tight sm:block">
                <span className="block max-w-40 truncate text-sm font-medium">{user.name}</span>
                <span className="block text-xs text-muted-foreground">{roleLabel}</span>
              </span>
            </div>
            <Button asChild variant="ghost" size="lg">
              <Link to="/help" aria-label="Help">
                <CircleHelp aria-hidden="true" />
                <span className="hidden sm:inline">Help</span>
              </Link>
            </Button>
            <Button variant="outline" size="lg" onClick={() => void signOut()} aria-label="Sign out">
              <LogOut aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </div>
      </header>

      <div className="flex">
        <aside className="hidden w-60 shrink-0 border-r md:block">
          <nav aria-label="Main" className="sticky top-14">
            <NavList items={items} />
          </nav>
        </aside>
        <main
          id="main-content"
          ref={mainRef}
          tabIndex={-1}
          className="min-w-0 flex-1 px-4 py-6 outline-none sm:px-6 lg:px-8"
        >
          <div className="mx-auto max-w-4xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
