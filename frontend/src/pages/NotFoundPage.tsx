import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'
import { WhereToGo } from '@/components/where-to-go'

export function NotFoundPage() {
  return (
    // B14: the quiet photo fills the heading section; the action sits with the
    // title, and "Where to go" runs full width below.
    <section className="stage">
      <PageHeader
        eyebrow={<p className="num mb-1 text-small text-muted-foreground">Error 404</p>}
        title="Page not found"
        description="The address may be mistyped, or the page has moved."
        photo="band-quiet-2"
        actions={
          <Button asChild>
            <Link to="/">Go to the home page</Link>
          </Button>
        }
      />
      <WhereToGo layout="band" />
    </section>
  )
}
