"""BR-13 in the Django admin and on delete: a tariff is editable only until it takes effect.

Kept in the pricing app so its own tests reach the 100% target on pricing
(Maintainability-2).
"""

from datetime import timedelta

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.tests.factories import AdministratorFactory, UserFactory
from apps.pricing.admin import TariffAdmin
from apps.pricing.models import Tariff
from apps.pricing.tests.factories import TariffFactory

pytestmark = pytest.mark.django_db


def _request(user):
    request = RequestFactory().get("/admin/pricing/tariff/add/")
    request.user = user
    return request


@pytest.fixture
def model_admin():
    return TariffAdmin(Tariff, admin.site)


@pytest.fixture
def superuser():
    return UserFactory(is_staff=True, is_superuser=True)


def test_a_future_tariff_can_be_deleted():
    tariff = TariffFactory(effective_from=timezone.now() + timedelta(days=3))
    tariff.delete()
    assert not Tariff.objects.filter(pk=tariff.pk).exists()


def test_a_future_tariff_can_be_changed_and_deleted_in_the_admin(model_admin, superuser):
    tariff = Tariff.objects.get(
        pk=TariffFactory(effective_from=timezone.now() + timedelta(days=3)).pk
    )
    assert model_admin.has_change_permission(_request(superuser), tariff)
    assert model_admin.has_delete_permission(_request(superuser), tariff)


def test_a_tariff_in_effect_is_view_only_in_the_admin(model_admin, superuser):
    tariff = Tariff.objects.get(pk=TariffFactory().pk)
    assert not model_admin.has_change_permission(_request(superuser), tariff)
    assert not model_admin.has_delete_permission(_request(superuser), tariff)


def test_a_new_tariff_is_defined_by_the_signed_in_administrator(model_admin):
    administrator = AdministratorFactory()
    initial = model_admin.get_changeform_initial_data(_request(administrator.user))
    assert initial["defined_by"] == administrator.pk


def test_a_superuser_without_an_administrator_profile_chooses_one(model_admin, superuser):
    assert "defined_by" not in model_admin.get_changeform_initial_data(_request(superuser))
