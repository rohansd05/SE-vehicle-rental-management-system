import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'
import { WhereToGo } from '@/components/where-to-go'

export function NotFoundPage() {
  return (
    <section className="grid gap-10 lg:grid-cols-[minmax(0,42rem)_minmax(16rem,1fr)] lg:gap-16">
      <div>
        <p className="num mb-2 text-small text-muted-foreground">Error 404</p>
        <PageHeader
          title="Page not found"
          description="The address may be mistyped, or the page has moved."
        />
        <Button asChild>
          <Link to="/">Go to the home page</Link>
        </Button>
      </div>
      <WhereToGo />
    </section>
  )
}
