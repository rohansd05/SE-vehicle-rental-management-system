import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <section className="max-w-xl">
      <p className="text-sm font-medium text-muted-foreground">Error 404</p>
      <PageHeader
        title="Page not found"
        description="The address may be mistyped, or the page has moved."
      />
      <Button asChild>
        <Link to="/">Go to the home page</Link>
      </Button>
    </section>
  )
}
