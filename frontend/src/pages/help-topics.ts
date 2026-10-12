// The help topics shown on /help, and linked from the public home page
// (docs/design/ui-brief.md, 6.2). One copy of the text, used in both places.

export interface HelpTopic {
  id: string
  title: string
  body: string
}

export const HELP_TOPICS: readonly HelpTopic[] = [
  {
    id: 'signing-in',
    title: 'Signing in',
    body:
      'After five failed attempts in a row your account is locked for 15 minutes, and we e-mail the registered address. For your security you are signed out after 30 minutes without activity.',
  },
  {
    id: 'verification-codes',
    title: 'Verification codes',
    body:
      'Codes are sent by SMS and are valid for 10 minutes. You can request a new one after a minute; requesting a new code stops the previous one from working.',
  },
  {
    id: 'driving-licence',
    title: 'Driving licence',
    body:
      'Upload clear photos of the front and back of your licence (JPG or PNG, up to 5 MB each). Our staff verify it before you can book.',
  },
]
