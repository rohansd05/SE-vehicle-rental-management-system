"""D21: the refresh token lives only in an httpOnly cookie.

- httpOnly: page scripts can never read it, so an XSS bug cannot steal it.
- SameSite=Strict: browsers never send it on a cross-site request, which
  is the CSRF protection for the refresh and sign-out endpoints.
- Secure everywhere except local development (plain http://localhost).
- Path /api/v1/auth/: sent only to the auth endpoints, never to the rest
  of the API.

Rotation and blacklisting are unchanged (D19).
"""

from django.conf import settings


def _lifetime_seconds() -> int:
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=_lifetime_seconds(),
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite="Strict",
    )


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        samesite="Strict",
    )


def read_refresh_cookie(request) -> str | None:
    return request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME) or None
