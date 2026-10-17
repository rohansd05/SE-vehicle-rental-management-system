"""SE-9: re-authentication before a payment or a refund."""

from rest_framework.exceptions import ValidationError

from apps.core.audit import record_audit


def require_password(request, password: str, *, entity_label: str, entity_id) -> None:
    """Refuse (400 on `password`) unless `password` is the caller's own; a failure is audited."""
    if request.user.check_password(password):
        return
    record_audit(
        request.user,
        "Payment Re-authentication Failed",
        entity_label=entity_label,
        entity_id=entity_id,
        request=request,
    )
    raise ValidationError({"password": ["That password is not correct."]})
