import { Clock } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { NavItem } from '@/app/navigation'
import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'
import { WhereToGo } from '@/components/where-to-go'

/** An honest placeholder for a planned feature: no sample or fake data. */
export function NotAvailablePage({ item }: { item: NavItem }) {
  return (
    // B14: the quiet photo fills the heading section, like every other page
    // header; "Where to go" follows, as on the help, 403 and 404 pages (6.9).
    <section className="grid gap-10">
      <div>
        <PageHeader title={item.label} description={item.description} photo="band-quiet-2" />
        <div className="flex max-w-3xl items-start gap-3 rounded-lg border p-5">
          <Clock className="mt-1 size-5 text-muted-foreground" aria-hidden="true" />
          <div>
            <p className="font-medium">Not available yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              This part of the system is planned for a later release. Nothing here is live yet.
            </p>
          </div>
        </div>
        <Button asChild variant="outline" className="mt-6">
          <Link to="/app">Back to home</Link>
        </Button>
      </div>
      <WhereToGo layout="band" />
    </section>
  )
}
