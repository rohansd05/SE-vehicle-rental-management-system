"""SE-9: re-authentication before a payment or a refund."""

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import Throttled, ValidationError

from apps.core.audit import record_audit


def _failures_key(user) -> str:
    return f"payment-reauth-failures:{user.pk}"


def require_password(request, password: str, *, entity_label: str, entity_id) -> None:
    """Refuse (400 on `password`) unless `password` is the caller's own; a failure is audited.

    Proposed N4-P3: like a sign-in (SE-8), LOGIN_FAILURE_LIMIT wrong passwords in a row
    stop the re-check for LOGIN_LOCKOUT_DURATION (429, the password is not even checked),
    so a stolen session cannot be used to guess the password. A right one resets the count.
    """
    key = _failures_key(request.user)
    window = int(settings.LOGIN_LOCKOUT_DURATION.total_seconds())
    if cache.get(key, 0) >= settings.LOGIN_FAILURE_LIMIT:
        raise Throttled(wait=window, detail="Too many wrong passwords. Please try again later.")
    if request.user.check_password(password):
        cache.delete(key)
        return
    cache.add(key, 0, timeout=window)  # the window starts at the first wrong password
    cache.incr(key)
    record_audit(
        request.user,
        "Payment Re-authentication Failed",
        entity_label=entity_label,
        entity_id=entity_id,
        request=request,
    )
    raise ValidationError({"password": ["That password is not correct."]})
