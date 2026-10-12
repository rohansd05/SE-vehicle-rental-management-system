import { PageHeader } from '@/components/page'
import { Photo } from '@/components/photo'
import { WhereToGo } from '@/components/where-to-go'
import { PHOTOS } from '@/lib/images'

/**
 * The public "Photo credits" page (D23, imagery-brief.md 6): every photo in
 * the app with its author, source, licence and the changes made, from the
 * same manifest that docs/design/image-credits.md is generated from.
 */
const CREDITS = Object.entries(PHOTOS).sort(([, a], [, b]) => a.title.localeCompare(b.title))

const EXTERNAL = 'font-medium text-foreground underline decoration-line-strong underline-offset-4 transition-colors hover:text-primary hover:decoration-primary'

export function CreditsPage() {
  return (
    <section className="stage">
      <PageHeader
        title="Photo credits"
        description="The photographs in this app, who took them, where they come from and their licences. Vehicle photos are representative images of each model or category, not the vehicles in our fleet."
        photo="band-quiet-2"
      />
      <div className="grid gap-12">
        {/* B14: each credit is a tile led by its photo, whole, at 3:2. */}
        <ul className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {CREDITS.map(([id, photo]) => (
            <li key={id} className="reveal flex flex-col overflow-hidden rounded-xl border bg-surface">
              <Photo id={id} alt="" sizes="(min-width: 1536px) 22vw, (min-width: 1280px) 30vw, (min-width: 640px) 45vw, 100vw" className="aspect-[3/2]" />
              <div className="min-w-0 p-5 text-small">
                <p className="font-medium break-words text-foreground">{photo.title}</p>
                <p className="mt-1 text-muted-foreground">
                  By {photo.author},{' '}
                  <a href={photo.page} className={EXTERNAL} rel="noreferrer" target="_blank">
                    {photo.source}
                  </a>
                  ,{' '}
                  <a href={photo.licenceUrl} className={EXTERNAL} rel="noreferrer" target="_blank">
                    {photo.licence}
                  </a>
                </p>
                <p className="mt-1 text-muted-foreground">Changes made: {photo.changes}.</p>
              </div>
            </li>
          ))}
        </ul>
        <WhereToGo layout="band" />
      </div>
    </section>
  )
}
