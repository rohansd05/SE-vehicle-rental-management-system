import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { Button } from '@/components/ui/button'

/** 403: signed in, but this page belongs to another role (SE-4). */
export function ForbiddenPage() {
  return (
    <section className="max-w-xl">
      <p className="text-sm font-medium text-muted-foreground">Error 403</p>
      <PageHeader
        title="You don’t have access to this page"
        description="This page is for a different kind of account. If you think you should have access, ask an administrator."
      />
      <Button asChild>
        <Link to="/app">Go to your home page</Link>
      </Button>
    </section>
  )
}
