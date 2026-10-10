import { Clock } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { NavItem } from '@/app/navigation'
import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'

/** An honest placeholder for a planned feature: no sample or fake data. */
export function NotAvailablePage({ item }: { item: NavItem }) {
  return (
    <section className="max-w-xl">
      <PageHeader title={item.label} description={item.description} />
      <div className="flex items-start gap-3 rounded-lg border p-4">
        <Clock className="mt-0.5 size-5 text-muted-foreground" aria-hidden="true" />
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
    </section>
  )
}
