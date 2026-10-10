"""OpenAPI schema and Swagger UI routes (CO-4) and their access rule (D12)."""

import importlib

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import clear_url_caches

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

DOC_URLS = ["/api/schema/", "/api/docs/"]


def _reload_urlconf() -> None:
    clear_url_caches()
    importlib.reload(importlib.import_module(settings.ROOT_URLCONF))


@pytest.fixture
def public_docs():
    """Rebuild the URLconf as development does (API_DOCS_PUBLIC = True)."""
    with override_settings(API_DOCS_PUBLIC=True):
        _reload_urlconf()
        yield
    _reload_urlconf()


@pytest.mark.parametrize("url", DOC_URLS)
def test_docs_are_closed_to_anonymous_users_by_default(api_client, url):
    assert settings.API_DOCS_PUBLIC is False
    assert api_client.get(url).status_code in (401, 403)


@pytest.mark.parametrize("url", DOC_URLS)
def test_docs_are_closed_to_non_admin_users(api_client, url):
    api_client.force_login(UserFactory(is_staff=False))
    assert api_client.get(url).status_code == 403


@pytest.mark.parametrize("url", DOC_URLS)
def test_docs_are_open_to_an_admin_session(api_client, url):
    api_client.force_login(UserFactory(is_staff=True))
    assert api_client.get(url).status_code == 200


def test_schema_lists_the_health_endpoint(api_client):
    api_client.force_login(UserFactory(is_staff=True))
    assert b"/api/v1/health/" in api_client.get("/api/schema/").content


@pytest.mark.parametrize("url", DOC_URLS)
def test_docs_are_public_in_development(api_client, public_docs, url):
    assert api_client.get(url).status_code == 200
