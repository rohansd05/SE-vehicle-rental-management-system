import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'
import { WhereToGo } from '@/components/where-to-go'

/** 403: signed in, but this page belongs to another role (SE-4). */
export function ForbiddenPage() {
  return (
    <section className="stage grid gap-10 lg:grid-cols-[minmax(0,42rem)_minmax(16rem,1fr)] lg:gap-16 xl:gap-24">
      <div>
        <p className="num mb-2 text-small text-muted-foreground">Error 403</p>
        <PageHeader
          title="You don’t have access to this page"
          description="This page is for a different kind of account. If you think you should have access, ask an administrator."
        />
        <Button asChild>
          <Link to="/app">Go to your home page</Link>
        </Button>
      </div>
      <WhereToGo />
    </section>
  )
}
