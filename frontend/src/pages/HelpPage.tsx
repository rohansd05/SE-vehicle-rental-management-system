import { PageHeader } from '@/components/page'

/** UI-2 asks for a help link on every screen; the help system (UD-1) comes later. */
export function HelpPage() {
  return (
    <section className="max-w-2xl">
      <PageHeader
        title="Help"
        description="The full online help, with guides for every screen, is planned for a later release."
      />
      <div className="space-y-4 text-sm">
        <div>
          <h2 className="font-medium">Signing in</h2>
          <p className="mt-1 text-muted-foreground">
            After five failed attempts in a row your account is locked for 15 minutes, and we
            e-mail the registered address. For your security you are signed out after 30 minutes
            without activity.
          </p>
        </div>
        <div>
          <h2 className="font-medium">Verification codes</h2>
          <p className="mt-1 text-muted-foreground">
            Codes are sent by SMS and are valid for 10 minutes. You can request a new one after a
            minute; requesting a new code stops the previous one from working.
          </p>
        </div>
        <div>
          <h2 className="font-medium">Driving licence</h2>
          <p className="mt-1 text-muted-foreground">
            Upload clear photos of the front and back of your licence (JPG or PNG, up to 5 MB
            each). Our staff verify it before you can book.
          </p>
        </div>
      </div>
    </section>
  )
}
