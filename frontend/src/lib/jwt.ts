// Read the expiry of a JWT access token. The signature is not checked here:
// the server does that on every request. This only tells the client when
// to refresh.

export function tokenExpiresAt(token: string | null): number | null {
  if (!token) return null
  const payload = token.split('.')[1]
  if (!payload) return null
  try {
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    const exp = (JSON.parse(json) as { exp?: unknown }).exp
    return typeof exp === 'number' ? exp * 1000 : null
  } catch {
    return null
  }
}
