import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'
import { WhereToGo } from '@/components/where-to-go'

/** 403: signed in, but this page belongs to another role (SE-4). */
export function ForbiddenPage() {
  return (
    // B14: the quiet photo fills the heading section; the action sits with the
    // title, and "Where to go" runs full width below.
    <section className="stage">
      <PageHeader
        eyebrow={<p className="num mb-1 text-small text-muted-foreground">Error 403</p>}
        title="You don’t have access to this page"
        description="This page is for a different kind of account. If you think you should have access, ask an administrator."
        photo="band-quiet-2"
        actions={
          <Button asChild>
            <Link to="/app">Go to your home page</Link>
          </Button>
        }
      />
      <WhereToGo layout="band" />
    </section>
  )
}
