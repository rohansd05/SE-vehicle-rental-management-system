"""Project-wide pytest fixtures."""

import re

import pytest
from django.core.cache import cache
from django.db import transaction
from rest_framework.test import APIClient

from integrations.notification import get_notification_service


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters and OTP cooldowns must not leak between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def outbox():
    """The shared mock notification service's outbox, emptied for each test."""
    service = get_notification_service()
    service.clear()
    yield service.outbox
    service.clear()


@pytest.fixture(autouse=True)
def _run_on_commit_immediately(monkeypatch):
    """Tests run inside a transaction that never commits, so on_commit hooks
    (which enqueue Celery tasks) would never fire. Run them at once; Celery
    itself runs eagerly in test settings."""
    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())


@pytest.fixture
def latest_code(outbox):
    """Read the most recent OTP sent by SMS to `destination` from the mock."""

    def _read(destination: str) -> str:
        for message in reversed(outbox):
            if message.channel == "sms" and message.recipient == destination:
                return re.search(r"\b(\d{6})\b", message.body).group(1)
        raise AssertionError(f"No SMS was sent to {destination}")

    return _read
