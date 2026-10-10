// Session rules (SE-9, D19, D21).
//
// - The access token lives only in this module's memory. It is never put in
//   localStorage or sessionStorage; a page reload loses it and the session is
//   restored from the httpOnly refresh cookie instead.
// - The access token is refreshed shortly before it expires, but only if the
//   user did something (pointer, keyboard, touch, returning to the tab)
//   since the last refresh. There is no blind timer: an idle tab stops
//   refreshing, so the server-side refresh cookie runs out.
// - After 30 minutes without activity the session ends.

import { tokenExpiresAt } from './jwt'

export const INACTIVITY_LIMIT_MS = 30 * 60 * 1000 // SE-9
export const REFRESH_LEAD_MS = 60 * 1000 // refresh one minute before expiry

let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'touchstart'] as const

interface ActivityOptions {
  /** Refresh the access token; resolves false when the session is gone. */
  refresh: () => Promise<boolean>
  /** Called once after INACTIVITY_LIMIT_MS without activity. */
  onIdle: () => void
}

/** Watches user activity while signed in and drives refresh and idle sign-out. */
export class SessionActivity {
  private lastActivity = Date.now()
  private lastRefresh = Date.now()
  private refreshTimer: ReturnType<typeof setTimeout> | undefined
  private idleTimer: ReturnType<typeof setTimeout> | undefined
  private refreshSkipped = false
  private running = false
  private readonly options: ActivityOptions

  constructor(options: ActivityOptions) {
    this.options = options
  }

  start(): void {
    if (this.running) return
    this.running = true
    this.lastActivity = Date.now()
    this.lastRefresh = Date.now()
    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, this.handleActivity, { passive: true })
    }
    document.addEventListener('visibilitychange', this.handleVisibility)
    this.scheduleRefresh()
    this.resetIdleTimer()
  }

  stop(): void {
    this.running = false
    for (const event of ACTIVITY_EVENTS) {
      window.removeEventListener(event, this.handleActivity)
    }
    document.removeEventListener('visibilitychange', this.handleVisibility)
    clearTimeout(this.refreshTimer)
    clearTimeout(this.idleTimer)
  }

  /** Call after any successful refresh (including the client's 401 retry). */
  markRefreshed(): void {
    this.lastRefresh = Date.now()
    this.refreshSkipped = false
    this.scheduleRefresh()
  }

  private readonly handleVisibility = () => {
    if (document.visibilityState === 'visible') this.handleActivity()
  }

  private readonly handleActivity = () => {
    if (!this.running) return
    this.lastActivity = Date.now()
    this.resetIdleTimer()
    // The token was left to lapse while the user was away; they are back.
    if (this.refreshSkipped) void this.runRefresh()
  }

  private scheduleRefresh(): void {
    clearTimeout(this.refreshTimer)
    if (!this.running) return
    const expiresAt = tokenExpiresAt(getAccessToken())
    if (expiresAt === null) return
    const delay = Math.max(0, expiresAt - Date.now() - REFRESH_LEAD_MS)
    this.refreshTimer = setTimeout(this.handleRefreshDue, delay)
  }

  private readonly handleRefreshDue = () => {
    if (this.lastActivity > this.lastRefresh) {
      void this.runRefresh()
    } else {
      this.refreshSkipped = true // no activity: let it lapse, never refresh blindly
    }
  }

  private async runRefresh(): Promise<void> {
    this.refreshSkipped = false
    const ok = await this.options.refresh()
    if (ok) this.markRefreshed()
  }

  private resetIdleTimer(): void {
    clearTimeout(this.idleTimer)
    this.idleTimer = setTimeout(() => {
      if (this.running) this.options.onIdle()
    }, INACTIVITY_LIMIT_MS)
  }
}
