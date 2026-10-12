import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { WhereToGo } from '@/components/where-to-go'

import { HELP_TOPICS } from './help-topics'

/** UI-2 asks for a help link on every screen; the help system (UD-1) comes later. */
export function HelpPage() {
  // A home-page link opens a topic directly (/help#signing-in).
  const { hash } = useLocation()
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView()
  }, [hash])
  return (
    <section className="stage">
      <PageHeader
        title="Help"
        description="The full online help, with guides for every screen, is planned for a later release."
        photo="band-quiet-2"
      />
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,22rem)] lg:gap-16 xl:gap-24">
        <div className="divide-y">
          {HELP_TOPICS.map((topic) => (
            <div key={topic.id} id={topic.id} className="reveal scroll-mt-24 py-6 first:pt-0">
              <h2 className="text-section">{topic.title}</h2>
              <p className="mt-2 max-w-[68ch] text-sm text-muted-foreground">{topic.body}</p>
            </div>
          ))}
        </div>
        <WhereToGo />
      </div>
    </section>
  )
}
