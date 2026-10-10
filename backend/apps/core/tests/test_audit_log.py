"""AuditLog: append-only and tamper-evident (Fleet.Audit, SE-10)."""

import pytest
from django.db import IntegrityError, connection, transaction

from apps.accounts.tests.factories import UserFactory
from apps.core.audit import snapshot
from apps.core.exceptions import ImmutableRecordError
from apps.core.models import AuditLog
from apps.core.tests.factories import AuditLogFactory

pytestmark = pytest.mark.django_db


def test_entries_chain_from_the_genesis_hash():
    first = AuditLogFactory()
    second = AuditLogFactory()
    assert first.prev_hash == AuditLog.GENESIS_HASH
    assert second.prev_hash == first.entry_hash
    assert len(second.entry_hash) == 64
    assert AuditLog.objects.verify_chain()


def test_record_helper_stores_actor_and_values():
    actor = UserFactory()
    entry = AuditLog.objects.record(
        actor=actor,
        action="Update",
        entity_type="fleet.Vehicle",
        entity_id=7,
        before={"status": "Available"},
        after={"status": "Unsafe"},
        ip_address="127.0.0.1",
    )
    entry.refresh_from_db()
    assert entry.actor == actor
    assert entry.entity_id == "7"
    assert entry.after == {"status": "Unsafe"}
    assert entry.entry_hash == entry.compute_hash()


def test_tampering_breaks_the_chain():
    AuditLogFactory()
    victim = AuditLogFactory()
    AuditLogFactory()
    with connection.cursor() as cursor:
        # Fire Django's deferred FK checks first; ALTER TABLE refuses to run
        # while trigger events are pending in the transaction.
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute("ALTER TABLE core_auditlog DISABLE TRIGGER core_auditlog_append_only")
        cursor.execute("UPDATE core_auditlog SET action = 'Forged' WHERE id = %s", [victim.pk])
        cursor.execute("ALTER TABLE core_auditlog ENABLE TRIGGER core_auditlog_append_only")
    assert not AuditLog.objects.verify_chain()


def test_snapshot_never_contains_the_password():
    user = UserFactory()
    data = snapshot(user)
    assert "password" not in data
    assert data["email"] == user.email


class TestAppendOnly:
    def test_orm_save_of_existing_entry_raises(self):
        entry = AuditLogFactory()
        entry.action = "Changed"
        with pytest.raises(ImmutableRecordError):
            entry.save()

    def test_orm_delete_raises(self):
        with pytest.raises(ImmutableRecordError):
            AuditLogFactory().delete()

    def test_queryset_update_and_delete_raise(self):
        AuditLogFactory()
        with pytest.raises(ImmutableRecordError):
            AuditLog.objects.update(action="Changed")
        with pytest.raises(ImmutableRecordError):
            AuditLog.objects.all().delete()

    def test_raw_sql_update_raises(self):
        entry = AuditLogFactory()
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_auditlog SET action = 'Changed' WHERE id = %s", [entry.pk]
                )

    def test_raw_sql_delete_raises(self):
        entry = AuditLogFactory()
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM core_auditlog WHERE id = %s", [entry.pk])
