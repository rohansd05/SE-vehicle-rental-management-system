"""Module N4 (WBS 1.6.1, D1, CO-1, OE-4, SRS 5.3): the production settings and stack.

Checks config.settings.production, django-axes behind Caddy, the health check the
containers use, and the promises docker-compose.prod.yml and deploy/Caddyfile make:
Beat on the database scheduler, every backend process on the same settings, health
checks, Postgres with max_connections=200, and uploaded media never served as files.
"""

import importlib
import sys
from pathlib import Path

import pytest
import yaml
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.tests.factories import DEFAULT_PASSWORD, CustomerFactory

REPO = Path(settings.BASE_DIR).parent
HOST = "20-40-60-80.sslip.io"


@pytest.fixture
def production(monkeypatch):
    """config.settings.production as the VM's backend/.env would load it."""
    monkeypatch.setenv("ALLOWED_HOSTS", HOST)
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", f"https://{HOST}")
    sys.modules.pop("config.settings.production", None)
    yield importlib.import_module("config.settings.production")
    sys.modules.pop("config.settings.production", None)


def test_production_runs_without_debug_or_the_debug_toolbar(production):
    assert production.DEBUG is False
    assert production.API_DOCS_PUBLIC is False  # D12
    assert "debug_toolbar" not in production.INSTALLED_APPS
    assert not any("debug_toolbar" in m for m in production.MIDDLEWARE)


def test_production_hosts_and_csrf_origins_come_from_the_environment(production):
    assert production.ALLOWED_HOSTS == [HOST]
    assert production.CSRF_TRUSTED_ORIGINS == [f"https://{HOST}"]


def test_production_cookies_are_https_only_and_hsts_is_on(production):
    """SE-1, CO-1."""
    assert production.SESSION_COOKIE_SECURE and production.CSRF_COOKIE_SECURE
    assert production.AUTH_REFRESH_COOKIE_SECURE  # D21
    assert production.SECURE_HSTS_SECONDS >= 31536000
    assert production.SECURE_HSTS_INCLUDE_SUBDOMAINS
    assert production.SECURE_CONTENT_TYPE_NOSNIFF
    assert production.X_FRAME_OPTIONS == "DENY"
    assert production.SECURE_REFERRER_POLICY == "same-origin"


def test_production_trusts_caddys_forwarded_headers(production):
    assert production.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert production.USE_X_FORWARDED_HOST is True


def test_celery_beat_reads_the_schedules_the_migrations_register():
    assert settings.CELERY_BEAT_SCHEDULER == "django_celery_beat.schedulers:DatabaseScheduler"


# ─── django-axes behind Caddy (SE-8) ──────────────────────────────────────


def _fail_login(client, email, forwarded_for):
    return client.post(
        reverse("accounts:login"),
        {"email": email, "password": "wrong-password"},
        format="json",
        REMOTE_ADDR="172.18.0.9",  # Caddy's address on the compose network
        HTTP_X_FORWARDED_FOR=forwarded_for,
    )


@pytest.mark.django_db
def test_axes_records_the_address_caddy_saw_not_a_spoofed_one(api_client, settings):
    from axes.models import AccessAttempt

    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    user = CustomerFactory().user
    _fail_login(api_client, user.email, "6.6.6.6, 203.0.113.7")  # client-sent, then Caddy's
    assert AccessAttempt.objects.get(username=user.email).ip_address == "203.0.113.7"


@pytest.mark.django_db
def test_a_lockout_from_one_address_never_locks_other_users_there(api_client, settings):
    """Every user behind one NAT shares an address; the lock is per account (SE-8)."""
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    locked, other = CustomerFactory().user, CustomerFactory().user
    for _ in range(settings.LOGIN_FAILURE_LIMIT):
        _fail_login(api_client, locked.email, "203.0.113.7")
    response = api_client.post(
        reverse("accounts:login"),
        {"email": other.email, "password": DEFAULT_PASSWORD},
        format="json",
        REMOTE_ADDR="172.18.0.9",
        HTTP_X_FORWARDED_FOR="203.0.113.7",
    )
    assert response.status_code == 200


# ─── The containers' health check ─────────────────────────────────────────


@pytest.mark.django_db
def test_the_health_check_only_reads(api_client):
    with CaptureQueriesContext(connection) as queries:
        assert api_client.get(reverse("core:health")).status_code == 200
    assert queries.captured_queries
    assert all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries.captured_queries)


# ─── docker-compose.prod.yml and the Caddyfile ────────────────────────────


@pytest.fixture(scope="module")
def stack():
    return yaml.safe_load((REPO / "docker-compose.prod.yml").read_text(encoding="utf-8"))


def test_the_stack_has_every_d1_service(stack):
    assert set(stack["services"]) == {"postgres", "valkey", "django", "worker", "beat", "caddy"}


@pytest.mark.parametrize("name", ["django", "worker", "beat"])
def test_worker_and_beat_share_djangos_settings_and_wait_for_healthy_stores(stack, name):
    service = stack["services"][name]
    assert service["environment"]["DJANGO_SETTINGS_MODULE"] == "config.settings.production"
    assert service["env_file"] == ["backend/.env"]
    assert "media:/app/media" in service["volumes"]
    for store in ("postgres", "valkey"):
        assert service["depends_on"][store]["condition"] == "service_healthy"


def test_beat_uses_the_database_scheduler(stack):
    assert "django_celery_beat.schedulers:DatabaseScheduler" in stack["services"]["beat"]["command"]


@pytest.mark.parametrize("name", ["postgres", "valkey", "django"])
def test_postgres_valkey_and_django_have_health_checks(stack, name):
    assert stack["services"][name]["healthcheck"]["test"]


def test_django_health_check_calls_the_health_endpoint(stack):
    assert "/api/v1/health/" in " ".join(stack["services"]["django"]["healthcheck"]["test"])


@pytest.mark.parametrize("path", ["docker-compose.yml", "docker-compose.prod.yml"])
def test_postgres_allows_200_connections_for_the_concurrency_tests(path):
    """Reliability-1: R2's two 100-way tests need more than the default 100 connections."""
    compose = yaml.safe_load((REPO / path).read_text(encoding="utf-8"))
    assert "max_connections=200" in compose["services"]["postgres"]["command"]


def test_only_caddy_is_published_to_the_internet(stack):
    published = {name for name, service in stack["services"].items() if service.get("ports")}
    assert published == {"caddy"}


def test_caddy_never_serves_uploaded_media_as_files():
    """SI-3: photos, signatures and workshop invoices leave only through signed links."""
    caddyfile = (REPO / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    assert "handle /media/*" in caddyfile
    assert "respond 404" in caddyfile.split("handle /media/*", 1)[1].split("}", 1)[0]
    assert "/app/media" not in caddyfile
