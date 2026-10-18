"""Tariff, add-on and discount code administration API (Module N3): SRS 3.7
Fleet.Tariff, Fleet.Tariff.History, BR-13, BR-3, D17; Exp 2 use case 11 step 2
and extension 2a. Administrator only (SE-6)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking, BookingAddOn
from apps.bookings.tests.factories import BookingFactory
from apps.core.choices import VehicleType
from apps.core.models import AuditLog
from apps.fleet.tests.factories import VehicleCategoryFactory
from apps.pricing.models import DiscountCode, Tariff
from apps.pricing.services import current_tariff
from apps.pricing.tests.factories import AddOnFactory, DiscountCodeFactory, TariffFactory

pytestmark = pytest.mark.django_db

D = Decimal
TARIFFS = reverse("pricing:admin-tariffs")


@pytest.fixture
def admin():
    return AdministratorFactory().user


@pytest.fixture
def client(admin):
    return authenticated_client(admin)


def _rates(category, **overrides) -> dict:
    data = {
        "vehicle_category": category.pk,
        "hourly_rate": "175.00",
        "daily_rate": "2000.00",
        "weekly_rate": "12000.00",
        "free_km_allowance": 250,
        "excess_km_rate": "11.00",
    }
    data.update(overrides)
    return data


def _states(client, category) -> list[tuple[str, str]]:
    rows = client.get(TARIFFS, {"vehicle_category": category.pk}).json()
    return [(row["daily_rate"], row["state"]) for row in rows]


# ─── Fleet.Tariff, BR-13, UC 11 extension 2a ──────────────────────────────


def test_a_new_tariff_takes_effect_and_the_old_one_stays(client, admin):
    old = TariffFactory()
    category = old.vehicle_category

    response = client.post(TARIFFS, _rates(category), format="json")

    assert response.status_code == 201, response.content
    data = response.json()
    assert (data["state"], data["defined_by"]) == ("In force", admin.name)
    assert _states(client, category) == [("2000.00", "In force"), ("1800.00", "Superseded")]
    assert Tariff.objects.filter(vehicle_category=category).count() == 2  # history kept
    assert current_tariff(category).pk == data["id"]  # new bookings use it
    entry = AuditLog.objects.get(entity_type="pricing.Tariff", actor=admin)
    assert entry.action == "Create" and entry.after["daily_rate"] == "2000.00"


def test_a_confirmed_booking_keeps_the_tariff_it_was_priced_at(client):
    """UC 11 extension 2a: nothing confirmed or invoiced is repriced."""
    booking = BookingFactory()
    priced_at, total = booking.tariff_id, booking.total_amount

    client.post(TARIFFS, _rates(booking.vehicle.category, daily_rate="9999.00"), format="json")

    booking = Booking.objects.get(pk=booking.pk)
    assert (booking.tariff_id, booking.total_amount) == (priced_at, total)
    row = next(r for r in client.get(TARIFFS).json() if r["id"] == priced_at)
    assert (row["state"], row["booking_count"]) == ("Superseded", 1)


def test_a_future_tariff_is_scheduled_and_can_be_withdrawn_before_it_starts(client):
    old = TariffFactory()
    starts = (timezone.now() + timedelta(days=7)).isoformat()
    response = client.post(
        TARIFFS, _rates(old.vehicle_category, effective_from=starts), format="json"
    )
    assert response.json()["state"] == "Scheduled"
    assert current_tariff(old.vehicle_category).pk == old.pk  # still in force today

    scheduled = reverse("pricing:admin-tariff", args=[response.json()["id"]])
    assert client.delete(scheduled).status_code == 204
    assert AuditLog.objects.filter(action="Delete", entity_type="pricing.Tariff").count() == 1
    in_force = reverse("pricing:admin-tariff", args=[old.pk])
    assert client.delete(in_force).status_code == 400  # history is never deleted
    assert Tariff.objects.filter(pk=old.pk).exists()


def test_a_past_effective_date_or_a_second_tariff_at_the_same_moment_is_refused(client):
    category = VehicleCategoryFactory()
    past = (timezone.now() - timedelta(minutes=5)).isoformat()
    response = client.post(TARIFFS, _rates(category, effective_from=past), format="json")
    assert "effective_from" in response.json()

    starts = (timezone.now() + timedelta(days=3)).replace(microsecond=0).isoformat()
    first = client.post(TARIFFS, _rates(category, effective_from=starts), format="json")
    assert first.status_code == 201
    again = client.post(TARIFFS, _rates(category, effective_from=starts), format="json")
    assert "already has a tariff" in again.json()["effective_from"][0]


@pytest.mark.parametrize(
    ("vehicle_type", "deposit"),
    [(VehicleType.CAR, "5000.00"), (VehicleType.TWO_WHEELER, "2000.00")],
)
def test_the_security_deposit_is_br3s_never_an_input(client, vehicle_type, deposit):
    category = VehicleCategoryFactory(vehicle_type=vehicle_type)
    response = client.post(TARIFFS, _rates(category, security_deposit="1.00"), format="json")
    assert response.json()["security_deposit"] == deposit


def test_negative_rates_are_refused(client):
    response = client.post(
        TARIFFS, _rates(VehicleCategoryFactory(), daily_rate="-1"), format="json"
    )
    assert response.status_code == 400 and "daily_rate" in response.json()


# ─── Add-ons (Book.Addons, BR-7) ──────────────────────────────────────────


def test_add_ons_are_created_and_changed_without_repricing_bookings(client, admin):
    url = reverse("pricing:admin-add-ons")
    created = client.post(url, {"name": "GPS unit", "daily_rate": "120.00"}, format="json")
    assert created.status_code == 201 and created.json()["is_active"] is True
    assert "name" in client.post(url, {"name": "gps UNIT", "daily_rate": "1"}, format="json").json()

    seat = AddOnFactory(name="Child seat", daily_rate=D("150.00"))
    line = BookingAddOn.objects.create(
        booking=BookingFactory(), add_on=seat, daily_rate=seat.daily_rate
    )
    detail = reverse("pricing:admin-add-on", args=[seat.pk])
    changed = client.patch(detail, {"daily_rate": "200.00", "is_active": False}, format="json")
    assert changed.json()["daily_rate"] == "200.00" and changed.json()["is_active"] is False
    line.refresh_from_db()
    assert line.daily_rate == D("150.00")  # the booking keeps its copy (BR-13)
    assert set(AuditLog.objects.filter(actor=admin).values_list("action", flat=True)) == {
        "Create",
        "Update",
    }
    assert [a["name"] for a in client.get(url).json()] == ["Child seat", "GPS unit"]


# ─── Discount codes (D17) ─────────────────────────────────────────────────


def _code(**overrides) -> dict:
    now = timezone.now()
    data = {
        "code": "monsoon15",
        "discount_type": "Percent",
        "value": "15.00",
        "valid_from": now.isoformat(),
        "valid_to": (now + timedelta(days=30)).isoformat(),
    }
    data.update(overrides)
    return data


def test_a_discount_code_is_created_once_whatever_the_case(client):
    url = reverse("pricing:admin-discount-codes")
    response = client.post(url, _code(), format="json")
    assert response.status_code == 201, response.content
    assert response.json()["code"] == "MONSOON15"
    assert "code" in client.post(url, _code(code="Monsoon15"), format="json").json()


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"value": "101.00"}, "value"),
        ({"value": "0"}, "value"),
        ({"valid_to": (timezone.now() - timedelta(days=1)).isoformat()}, "valid_to"),
    ],
)
def test_an_invalid_discount_is_refused(client, overrides, field):
    response = client.post(
        reverse("pricing:admin-discount-codes"), _code(**overrides), format="json"
    )
    assert response.status_code == 400 and field in response.json()


def test_a_discount_code_changes_but_its_text_and_use_count_do_not(client):
    code = DiscountCodeFactory(code="SAVE10", times_used=3)
    url = reverse("pricing:admin-discount-code", args=[code.pk])
    assert "usage_limit" in client.patch(url, {"usage_limit": 2}, format="json").json()
    changed = client.patch(
        url,
        {"code": "OTHER", "is_active": False, "times_used": 0, "usage_limit": 10},
        format="json",
    ).json()
    assert (changed["code"], changed["times_used"], changed["is_active"]) == ("SAVE10", 3, False)
    assert DiscountCode.objects.get(pk=code.pk).usage_limit == 10


# ─── SE-4, BR-13: Administrator only ──────────────────────────────────────

ROLES = ["anonymous", "customer", "staff", "technician", "admin", "manager"]


def _user(role):
    return {
        "customer": lambda: CustomerFactory().user,
        "staff": lambda: BranchStaffFactory().user,
        "technician": lambda: MaintenanceTechnicianFactory().user,
        "admin": lambda: AdministratorFactory().user,
        "manager": lambda: BranchManagerFactory().user,
        "anonymous": lambda: None,
    }[role]()


ENDPOINTS = [
    ("admin-tariffs-get", "get", lambda: TARIFFS),
    ("admin-tariffs-post", "post", lambda: TARIFFS),
    ("admin-tariff", "delete", lambda: reverse("pricing:admin-tariff", args=[TariffFactory().pk])),
    ("admin-add-ons-get", "get", lambda: reverse("pricing:admin-add-ons")),
    ("admin-add-ons-post", "post", lambda: reverse("pricing:admin-add-ons")),
    ("admin-add-on", "patch", lambda: reverse("pricing:admin-add-on", args=[AddOnFactory().pk])),
    ("admin-discount-codes-get", "get", lambda: reverse("pricing:admin-discount-codes")),
    ("admin-discount-codes-post", "post", lambda: reverse("pricing:admin-discount-codes")),
    (
        "admin-discount-code",
        "patch",
        lambda: reverse("pricing:admin-discount-code", args=[DiscountCodeFactory().pk]),
    ),
]


@pytest.mark.parametrize(
    ("method", "url", "role"),
    [
        pytest.param(method, url, role, id=f"{name}-{role}")
        for name, method, url in ENDPOINTS
        for role in ROLES
    ],
)
def test_endpoint_permission(api_client, method, url, role):
    user = _user(role)
    client = authenticated_client(user) if user else api_client
    response = getattr(client, method)(url(), {}, format="json")
    if role == "admin":
        assert response.status_code not in (401, 403), response.content
    else:
        assert response.status_code == (401 if role == "anonymous" else 403), response.content


def test_a_branch_manager_cannot_define_a_tariff_even_in_the_service():
    """BR-13: a Branch Manager is a restricted Administrator, not the Administrator."""
    from apps.pricing import admin_services

    with pytest.raises(admin_services.PricingAdminError):
        admin_services.define_tariff(
            BranchManagerFactory().user,
            {
                "vehicle_category": VehicleCategoryFactory(),
                **{k: D("1") for k in admin_services.RATE_FIELDS},
            },
        )


def test_every_pricing_admin_route_is_in_the_matrix():
    from apps.pricing.urls import urlpatterns

    named = {p.name for p in urlpatterns if p.name.startswith("admin-")}
    covered = {name.removesuffix("-get").removesuffix("-post") for name, *_ in ENDPOINTS}
    assert named == covered
