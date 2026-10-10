// SE-9 / D19: refresh only after activity; sign out after 30 idle minutes.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { makeAccessToken } from '@/test/server'

import { INACTIVITY_LIMIT_MS, SessionActivity, setAccessToken } from './session'

const MINUTE = 60_000

function activity(refresh = vi.fn(async () => true)) {
  const onIdle = vi.fn()
  const watcher = new SessionActivity({ refresh, onIdle })
  return { watcher, refresh, onIdle }
}

const press = () => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }))

describe('SessionActivity', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setAccessToken(makeAccessToken(5 * 60)) // a 5-minute access token (D19)
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('never refreshes an idle session (no blind timer)', async () => {
    const { watcher, refresh } = activity()
    watcher.start()
    await vi.advanceTimersByTimeAsync(29 * MINUTE)
    expect(refresh).not.toHaveBeenCalled()
    watcher.stop()
  })

  it('signs out after 30 minutes without activity', async () => {
    const { watcher, onIdle } = activity()
    watcher.start()
    await vi.advanceTimersByTimeAsync(INACTIVITY_LIMIT_MS - 1)
    expect(onIdle).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(onIdle).toHaveBeenCalledTimes(1)
    watcher.stop()
  })

  it('refreshes one minute before expiry when the user was active', async () => {
    const refresh = vi.fn(async () => {
      setAccessToken(makeAccessToken(5 * 60))
      return true
    })
    const { watcher } = activity(refresh)
    watcher.start()
    await vi.advanceTimersByTimeAsync(MINUTE)
    press()
    // A JWT exp is in whole seconds, so allow up to a second of rounding.
    await vi.advanceTimersByTimeAsync(3 * MINUTE - 2000)
    expect(refresh).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(2000) // 4 minutes: one minute before expiry
    expect(refresh).toHaveBeenCalledTimes(1)
    watcher.stop()
  })

  it('activity postpones the idle sign-out', async () => {
    const { watcher, onIdle } = activity()
    watcher.start()
    await vi.advanceTimersByTimeAsync(29 * MINUTE)
    press()
    await vi.advanceTimersByTimeAsync(29 * MINUTE)
    expect(onIdle).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(MINUTE)
    expect(onIdle).toHaveBeenCalledTimes(1)
    watcher.stop()
  })

  it('refreshes when the user comes back after the token lapsed', async () => {
    const { watcher, refresh } = activity()
    watcher.start()
    await vi.advanceTimersByTimeAsync(10 * MINUTE) // the 4-minute refresh was skipped
    expect(refresh).not.toHaveBeenCalled()
    press()
    await vi.advanceTimersByTimeAsync(0)
    expect(refresh).toHaveBeenCalledTimes(1)
    watcher.stop()
  })

  it('returning to the tab counts as activity', async () => {
    const { watcher, refresh } = activity()
    watcher.start()
    await vi.advanceTimersByTimeAsync(10 * MINUTE)
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(refresh).toHaveBeenCalledTimes(1)
    watcher.stop()
  })

  it('stops listening once stopped', async () => {
    const { watcher, refresh, onIdle } = activity()
    watcher.start()
    watcher.stop()
    press()
    await vi.advanceTimersByTimeAsync(40 * MINUTE)
    expect(refresh).not.toHaveBeenCalled()
    expect(onIdle).not.toHaveBeenCalled()
  })
})
