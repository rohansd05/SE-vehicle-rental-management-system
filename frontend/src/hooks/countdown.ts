import { useCallback, useEffect, useState } from 'react'

/** Seconds left on a visible countdown (the OTP resend cooldown). */
export function useCountdown(initialSeconds: number) {
  const [remaining, setRemaining] = useState(initialSeconds)

  useEffect(() => {
    if (remaining <= 0) return
    const timer = setTimeout(() => setRemaining((value) => Math.max(0, value - 1)), 1000)
    return () => clearTimeout(timer)
  }, [remaining])

  const restart = useCallback((seconds: number) => setRemaining(seconds), [])
  return [remaining, restart] as const
}
