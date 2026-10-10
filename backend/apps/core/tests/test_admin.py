"""Django admin: every model registered, audited edits, read-only immutable data."""

import pytest
from django.apps import apps
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.core.models import AuditLog
from apps.fleet.models import Branch
from apps.pricing.admin import TariffAdmin
from apps.pricing.models import Tariff
from apps.pricing.tests.factories import TariffFactory
from apps.rentals.admin import ConditionReportAdmin
from apps.rentals.models import ConditionReport
from apps.rentals.tests.factories import ConditionReportFactory

pytestmark = pytest.mark.django_db

VRMS_APPS = [
    "accounts",
    "core",
    "fleet",
    "pricing",
    "bookings",
    "rentals",
    "payments",
    "maintenance",
    "notifications",
]
APPEND_ONLY = ["core.AuditLog", "payments.Invoice", "payments.InvoiceLine",
               "payments.InvoiceAdjustment", "payments.LedgerEntry"]  # fmt: skip


@pytest.fixture
def admin_client(client):
    client.force_login(UserFactory(is_staff=True, is_superuser=True))
    return client


@pytest.fixture
def admin_request():
    request = RequestFactory().get("/admin/")
    request.user = UserFactory(is_staff=True, is_superuser=True)
    return request


def test_every_vrms_model_is_registered():
    missing = [
        model._meta.label
        for label in VRMS_APPS
        for model in apps.get_app_config(label).get_models()
        if model not in admin.site._registry
    ]
    assert missing == []


@pytest.mark.parametrize("model", list(admin.site._registry), ids=lambda m: m._meta.label)
def test_every_changelist_loads(admin_client, model):
    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
    assert admin_client.get(url).status_code == 200


@pytest.mark.parametrize("label", APPEND_ONLY)
def test_append_only_tables_cannot_be_added_in_admin(admin_client, label):
    model = apps.get_model(label)
    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_add")
    assert admin_client.get(url).status_code == 403


def test_admin_create_and_delete_write_audit_entries(admin_client):
    response = admin_client.post(
        reverse("admin:fleet_branch_add"),
        {
            "branch_name": "Audit Test",
            "address": "1 Test Road",
            "serviceable_areas-TOTAL_FORMS": "1",
            "serviceable_areas-INITIAL_FORMS": "0",
            "serviceable_areas-0-pincode": "400001",
            "serviceable_areas-0-locality": "Fort",
        },
    )
    assert response.status_code == 302
    branch = Branch.objects.get(branch_name="Audit Test")
    created = AuditLog.objects.filter(action="Create").values_list("entity_type", flat=True)
    assert sorted(created) == ["fleet.Branch", "fleet.BranchServiceableArea"]

    branch.serviceable_areas.all().delete()
    response = admin_client.post(
        reverse("admin:fleet_branch_delete", args=[branch.pk]), {"post": "yes"}
    )
    assert response.status_code == 302
    deleted = AuditLog.objects.get(action="Delete")
    assert deleted.entity_id == str(branch.pk)
    assert deleted.before["branch_name"] == "Audit Test"
    assert AuditLog.objects.verify_chain()


def test_tariff_in_effect_is_view_only(admin_request):
    tariff = Tariff.objects.get(pk=TariffFactory().pk)
    model_admin = TariffAdmin(Tariff, admin.site)
    assert not model_admin.has_change_permission(admin_request, tariff)
    assert not model_admin.has_delete_permission(admin_request, tariff)


def test_signed_condition_report_is_view_only(admin_request):
    report = ConditionReport.objects.get(pk=ConditionReportFactory(signed=True).pk)
    model_admin = ConditionReportAdmin(ConditionReport, admin.site)
    assert not model_admin.has_change_permission(admin_request, report)
    assert not model_admin.has_delete_permission(admin_request, report)
