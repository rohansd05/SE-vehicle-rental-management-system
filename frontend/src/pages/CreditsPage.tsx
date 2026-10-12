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
    <section className="stage grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,22rem)] lg:gap-16 xl:gap-24">
      <div>
        <PageHeader
          title="Photo credits"
          description="The photographs in this app, who took them, where they come from and their licences. Vehicle photos are representative images of each model or category, not the vehicles in our fleet."
        />
        <ul className="grid gap-x-10 sm:grid-cols-2">
          {CREDITS.map(([id, photo]) => (
            <li key={id} className="reveal flex items-start gap-4 border-b py-5">
              <Photo id={id} alt="" sizes="6rem" className="aspect-[4/3] w-24 shrink-0 rounded-md" />
              <div className="min-w-0 text-small">
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
      </div>
      <WhereToGo />
    </section>
  )
}
