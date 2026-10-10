"""record_audit: valid entries and a sound chain under concurrent writes (SE-10)."""

import threading

import pytest
from django.db import connection
from rest_framework.test import APIRequestFactory

from apps.accounts.tests.factories import UserFactory
from apps.core.audit import client_ip, record_audit, snapshot
from apps.core.models import AuditLog
from apps.fleet.tests.factories import BranchFactory


@pytest.mark.django_db
def test_entry_records_actor_entity_values_and_ip():
    actor = UserFactory()
    branch = BranchFactory()
    request = APIRequestFactory().post("/", REMOTE_ADDR="10.1.2.3")
    entry = record_audit(actor, "Update", branch, {"a": 1}, snapshot(branch), request)
    entry.refresh_from_db()
    assert entry.actor == actor
    assert (entry.entity_type, entry.entity_id) == ("fleet.Branch", str(branch.pk))
    assert entry.ip_address == "10.1.2.3"
    assert entry.before == {"a": 1}
    assert entry.entry_hash == entry.compute_hash()


@pytest.mark.django_db
def test_anonymous_actor_and_entity_label():
    from django.contrib.auth.models import AnonymousUser

    entry = record_audit(
        AnonymousUser(), "Login Failed", entity_label="accounts.User", entity_id=""
    )
    assert entry.actor is None
    assert entry.entity_type == "accounts.User"


def test_client_ip_honours_num_proxies(settings):
    # Behind Caddy: REMOTE_ADDR is the proxy, X-Forwarded-For carries the client.
    request = APIRequestFactory().get(
        "/", REMOTE_ADDR="172.18.0.5", HTTP_X_FORWARDED_FOR="203.0.113.9"
    )
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}
    assert client_ip(request) == "172.18.0.5"  # header not trusted without a proxy
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    assert client_ip(request) == "203.0.113.9"
    assert client_ip(None) is None


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_chain_stays_valid_under_a_concurrent_burst():
    """Many threads, each with its own database connection, append at once."""
    workers, per_worker = 12, 5
    barrier = threading.Barrier(workers)
    errors: list[BaseException] = []

    def write(index: int) -> None:
        try:
            barrier.wait()
            for n in range(per_worker):
                record_audit(None, "Burst", entity_label="test.Burst", entity_id=f"{index}-{n}")
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=write, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert AuditLog.objects.filter(action="Burst").count() == workers * per_worker
    assert AuditLog.objects.verify_chain()
    assert len(set(AuditLog.objects.values_list("prev_hash", flat=True))) == workers * per_worker
