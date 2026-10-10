"""Core models: shared abstract bases and the tamper-evident audit log.

Owner: Rohan (WBS 1.4.5).
"""

import hashlib
import json

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, models, transaction
from django.utils import timezone

from .exceptions import ImmutableRecordError

# Arbitrary constant key for pg_advisory_xact_lock, serialising audit inserts
# so that each entry chains onto exactly one predecessor.
AUDIT_CHAIN_LOCK_KEY = 4_242_001


class TimeStampedModel(models.Model):
    """created_at / updated_at, stored in UTC (CO-6)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AppendOnlyQuerySet(models.QuerySet):
    """Bulk changes are refused before they reach the database trigger."""

    def update(self, **kwargs):
        raise ImmutableRecordError(f"{self.model.__name__} is append-only; it cannot be updated.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ImmutableRecordError(f"{self.model.__name__} is append-only; it cannot be updated.")

    def delete(self):
        raise ImmutableRecordError(f"{self.model.__name__} is append-only; it cannot be deleted.")


class AppendOnlyModel(models.Model):
    """A row may be inserted once and never changed or deleted.

    The model-level guard gives a clear error; a PostgreSQL trigger on each
    concrete table (installed by its migration) enforces the same rule for
    raw SQL and any code path that bypasses the ORM.
    """

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableRecordError(
                f"{type(self).__name__} is append-only; record a correction instead."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableRecordError(f"{type(self).__name__} is append-only; it cannot be deleted.")


class AuditLogQuerySet(AppendOnlyQuerySet):
    def verify_chain(self) -> bool:
        """True if every entry links to its predecessor and its hash is intact."""
        expected_prev = AuditLog.GENESIS_HASH
        for entry in self.order_by("id").iterator():
            if entry.prev_hash != expected_prev or entry.entry_hash != entry.compute_hash():
                return False
            expected_prev = entry.entry_hash
        return True


class AuditLogManager(models.Manager.from_queryset(AuditLogQuerySet)):
    def record(
        self,
        *,
        actor,
        action: str,
        entity_type: str,
        entity_id,
        before: dict | None = None,
        after: dict | None = None,
        ip_address: str | None = None,
    ) -> "AuditLog":
        entry = self.model(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            before=before,
            after=after,
            ip_address=ip_address,
        )
        entry.save()
        return entry


class AuditLog(AppendOnlyModel):
    """Fleet.Audit, SE-10: who changed what, when, with previous and new values.

    Tamper evidence (SE-10): each entry stores the hash of its predecessor
    (prev_hash) and a SHA-256 over its own content plus prev_hash
    (entry_hash). Editing or removing any entry breaks the chain, which
    AuditLog.objects.verify_chain() detects. prev_hash is unique, so the
    chain can never fork.
    """

    GENESIS_HASH = "0" * 64

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_entries",
        help_text="Empty for actions taken by the system itself.",
    )
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    after = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    prev_hash = models.CharField(max_length=64, unique=True, editable=False)
    entry_hash = models.CharField(max_length=64, unique=True, editable=False)

    objects = AuditLogManager()

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

    def __str__(self) -> str:
        when = f"{self.timestamp:%Y-%m-%d %H:%M:%S}"
        return f"{when} {self.action} {self.entity_type}#{self.entity_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableRecordError("AuditLog is append-only; record a correction instead.")
        # Store JSON exactly as it will be read back, so the hash is reproducible.
        self.before = _json_roundtrip(self.before)
        self.after = _json_roundtrip(self.after)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [AUDIT_CHAIN_LOCK_KEY])
            last_hash = (
                AuditLog.objects.order_by("-id").values_list("entry_hash", flat=True).first()
            )
            self.prev_hash = last_hash or self.GENESIS_HASH
            self.entry_hash = self.compute_hash()
            super().save(*args, **kwargs)

    def compute_hash(self) -> str:
        payload = json.dumps(
            {
                "actor": self.actor_id,
                "action": self.action,
                "entity_type": self.entity_type,
                "entity_id": self.entity_id,
                "before": self.before,
                "after": self.after,
                "ip_address": self.ip_address,
                "timestamp": self.timestamp.isoformat(),
            },
            cls=DjangoJSONEncoder,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256((self.prev_hash + payload).encode()).hexdigest()


def _json_roundtrip(value):
    if value is None:
        return None
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))
