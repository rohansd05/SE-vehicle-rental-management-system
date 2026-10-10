"""Audit service (Fleet.Audit, SE-10).

Every write service calls record_audit(). Entries are appended to the
AuditLog hash chain; AuditLog.save() takes a PostgreSQL advisory lock for
the whole append, so concurrent requests each chain onto exactly one
predecessor (and the unique prev_hash makes a fork impossible).
"""

import ipaddress

from django.db import models
from rest_framework.throttling import BaseThrottle

from .models import AuditLog

# Never copied into an audit entry (SE-2, CO-2, SE-7).
SECRET_FIELDS = frozenset({"password", "code_hash", "card_token"})


def snapshot(instance: models.Model) -> dict:
    """The concrete field values of `instance`, ready for AuditLog.before/after."""
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in SECRET_FIELDS:
            continue
        value = getattr(instance, field.attname)
        if isinstance(field, models.FileField):
            value = value.name if value else ""
        data[field.attname] = value
    return data


def entity_type(instance: models.Model) -> str:
    return instance._meta.label


def client_ip(request) -> str | None:
    """The client address, honouring REST_FRAMEWORK NUM_PROXIES (Caddy in production)."""
    if request is None:
        return None
    ident = BaseThrottle().get_ident(request)
    try:
        return str(ipaddress.ip_address(ident.strip()))
    except (ValueError, AttributeError):
        return None


def record_audit(
    actor,
    action: str,
    entity: models.Model | None = None,
    before: dict | None = None,
    after: dict | None = None,
    request=None,
    *,
    entity_label: str | None = None,
    entity_id=None,
) -> AuditLog:
    """Append one audit entry.

    `actor` may be None (system action) or an anonymous user. `entity` is the
    record acted on; for events with no record (for example a failed login
    for an unknown account) pass `entity_label` and `entity_id` instead.
    """
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    label = entity_label or (entity_type(entity) if entity is not None else "")
    if entity_id is None:
        entity_id = entity.pk if entity is not None else ""
    return AuditLog.objects.record(
        actor=actor,
        action=action,
        entity_type=label,
        entity_id=entity_id,
        before=before,
        after=after,
        ip_address=client_ip(request),
    )
