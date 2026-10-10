"""GET /api/v1/health/."""

import pytest
from django.urls import reverse

from apps.core import views

pytestmark = pytest.mark.django_db


def test_health_is_public_and_reports_database_agency_and_currency(api_client, settings):
    settings.AGENCY_NAME = "Test Agency"
    settings.CURRENCY = "INR"

    response = api_client.get(reverse("core:health"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "agency_name": "Test Agency",
        "currency": "INR",
    }


def test_health_ignores_a_bad_bearer_token(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    response = api_client.get(reverse("core:health"))
    assert response.status_code == 200


def test_health_reports_unreachable_database_with_503(api_client, monkeypatch):
    monkeypatch.setattr(views, "database_reachable", lambda: False)

    response = api_client.get(reverse("core:health"))

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unreachable"


def test_health_url_path():
    assert reverse("core:health") == "/api/v1/health/"
