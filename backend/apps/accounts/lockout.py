"""SE-8 account lockout hooks for django-axes.

- axes_username: the account identifier axes counts failures against. It is
  the lower-cased e-mail, so "A@x.com" and "a@x.com" share one counter.
- lockout_response: what a locked-out client sees. The message is the same
  whether or not the account exists, as SE-8 requires.
- on_locked_out: notifies the registered e-mail address (once per lock) and
  writes an audit entry (SE-10).
"""

from datetime import timedelta

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

LOCKOUT_MESSAGE = "Too many failed sign-in attempts. Please try again in {minutes} minutes."


def _lockout_minutes() -> int:
    return int(settings.LOGIN_LOCKOUT_DURATION.total_seconds() // 60)


def axes_username(request, credentials) -> str | None:
    value = None
    if credentials:
        value = credentials.get("username") or credentials.get("email")
    if value is None and request is not None:
        data = getattr(request, "data", None) or getattr(request, "POST", {})
        value = data.get("username") or data.get("email")
    value = (value or "").strip().lower()
    return value or None


def lockout_response(request, credentials):
    message = LOCKOUT_MESSAGE.format(minutes=_lockout_minutes())
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": message, "code": "account_locked"}, status=403)
    return HttpResponse(message, status=403)


def on_locked_out(sender, request, username, ip_address, **kwargs) -> None:
    from apps.core.audit import record_audit
    from apps.notifications.models import Notification
    from apps.notifications.services import queue_email

    from .models import User

    user = User.objects.filter(email=username).first() if username else None
    if user is None:
        return  # nothing to notify, and nothing to reveal
    since = timezone.now() - settings.LOGIN_LOCKOUT_DURATION + timedelta(seconds=1)
    already_told = Notification.objects.filter(
        recipient=user, template="account_locked", queued_at__gte=since
    ).exists()
    if already_told:
        return
    record_audit(
        None,
        "Account Locked",
        user,
        after={"failures": settings.LOGIN_FAILURE_LIMIT},
        request=request,
    )
    queue_email(
        user,
        "account_locked",
        {
            "name": user.name,
            "attempts": settings.LOGIN_FAILURE_LIMIT,
            "minutes": _lockout_minutes(),
        },
    )
