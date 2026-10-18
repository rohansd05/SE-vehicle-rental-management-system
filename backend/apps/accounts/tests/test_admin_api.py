"""Staff accounts and the blacklist (Module N3): SRS 3.7 Fleet.Users, Fleet.Audit, BR-4;
Exp 2 use case 12 with extension 2a. Accounts made here work in the other modules:
Branch Staff on handover, return, the cash desk and branch bookings of their own
branch only, and a Branch Manager approves N2's odometer override."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Customer, User
from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings import lifecycle
from apps.bookings.eligibility import NotEligibleError
from apps.bookings.models import Booking
from apps.bookings.tests.conftest import eligible_customer, next_pickup
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog
from apps.fleet.tests.factories import BranchFactory, CarFactory
from apps.payments.models import RefundRequest
from apps.pricing.tests.factories import TariffFactory
from apps.rentals import services as rentals
from apps.rentals.tests.factories import (
    active_booking,
    checklist,
    readings,
    ready_booking,
    return_kwargs,
)

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd"
USERS = reverse("accounts:admin-users")
CUSTOMERS = reverse("accounts:admin-customers")


@pytest.fixture(autouse=True)
def _media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def admin():
    return AdministratorFactory().user


@pytest.fixture
def client(admin):
    return authenticated_client(admin)


def _account(role, branch=None, **overrides) -> dict:
    data = {
        "role": role,
        "email": f"new.{role.lower()}@vrms.test",
        "name": "Neha Kulkarni",
        "mobile_no": "+919811122233",
        "address": "7 Station Road, Thane",
        "password": PASSWORD,
    }
    if branch is not None:
        data["branch"] = branch.pk
    if role == "MAINTENANCE_TECHNICIAN":
        data["workshop"] = "Agency workshop, Thane"
    data.update(overrides)
    return data


def _create(client, role, branch=None, **overrides) -> User:
    response = client.post(USERS, _account(role, branch, **overrides), format="json")
    assert response.status_code == 201, response.content
    return User.objects.get(pk=response.json()["id"])


# ─── Fleet.Users: create, edit, disable, re-enable ────────────────────────


@pytest.mark.parametrize(
    ("role", "profile"),
    [
        ("BRANCH_STAFF", "branch_staff"),
        ("BRANCH_MANAGER", "administrator"),
        ("MAINTENANCE_TECHNICIAN", "maintenance_technician"),
    ],
)
def test_an_administrator_creates_each_staff_account_with_its_profile(client, admin, role, profile):
    branch = BranchFactory(branch_name="Thane")
    user = _create(client, role, branch)

    assert user.role == role and user.is_active and user.check_password(PASSWORD)
    assert hasattr(user, profile)
    data = client.get(reverse("accounts:admin-user", args=[user.pk])).json()
    if role == "MAINTENANCE_TECHNICIAN":
        assert (data["workshop"], data["branch"]) == ("Agency workshop, Thane", None)
        assert data["authorised_to_clear_unsafe"] is False
    else:
        assert (data["branch"], data["branch_name"]) == (branch.pk, "Thane")
    assert "password" not in data  # SE-2
    created = AuditLog.objects.filter(action="Create", actor=admin)
    assert created.count() == 2  # the user and the profile (Fleet.Audit)
    assert all("password" not in (entry.after or {}) for entry in created)


def test_the_new_account_signs_in(client, api_client):
    _create(client, "BRANCH_STAFF", BranchFactory())
    response = api_client.post(
        reverse("accounts:login"),
        {"email": "new.branch_staff@vrms.test", "password": PASSWORD},
        format="json",
    )
    assert response.status_code == 200 and response.json()["user"]["role"] == "BRANCH_STAFF"


@pytest.mark.parametrize(
    ("role", "overrides", "field"),
    [
        ("BRANCH_STAFF", {}, "branch"),
        ("BRANCH_MANAGER", {}, "branch"),
        ("MAINTENANCE_TECHNICIAN", {"workshop": " "}, "workshop"),
        ("BRANCH_STAFF", {"password": "password"}, "password"),
        ("CUSTOMER", {}, "role"),
        ("ADMINISTRATOR", {}, "role"),
        ("BRANCH_STAFF", {"mobile_no": "12"}, "mobile_no"),
    ],
)
def test_an_incomplete_account_is_refused(client, role, overrides, field):
    branch = None if field == "branch" else BranchFactory()
    response = client.post(USERS, _account(role, branch, **overrides), format="json")
    assert response.status_code == 400 and field in response.json(), response.content
    assert not User.objects.filter(email__startswith="new.").exists()


def test_an_e_mail_already_used_is_refused_whatever_the_case(client):
    BranchStaffFactory(user__email="taken@vrms.test")
    response = client.post(
        USERS, _account("BRANCH_STAFF", BranchFactory(), email="TAKEN@vrms.test"), format="json"
    )
    assert "already exists" in response.json()["email"][0]


def test_an_account_is_edited_and_moved_to_another_branch(client, admin):
    user = _create(client, "BRANCH_STAFF", BranchFactory())
    other = BranchFactory(branch_name="Vashi")
    url = reverse("accounts:admin-user", args=[user.pk])
    response = client.patch(url, {"name": "Neha K.", "branch": other.pk}, format="json")
    assert (response.json()["name"], response.json()["branch_name"]) == ("Neha K.", "Vashi")
    updates = AuditLog.objects.filter(action="Update", actor=admin)
    assert set(updates.values_list("entity_type", flat=True)) == {
        "accounts.User",
        "accounts.BranchStaff",
    }
    assert client.patch(url, {"role": "ADMINISTRATOR"}, format="json").json()["role"] == (
        "BRANCH_STAFF"
    )  # the role never changes


def test_disabling_ends_every_session_at_once_and_re_enabling_restores_sign_in(client, admin):
    user = _create(client, "BRANCH_STAFF", BranchFactory())
    refresh = RefreshToken.for_user(user)
    session = authenticated_client(user)
    assert session.get(reverse("rentals:branch-bookings")).status_code == 200

    disable = reverse("accounts:admin-user-disable", args=[user.pk])
    assert client.post(disable, {}, format="json").status_code == 400  # a reason is required
    response = client.post(disable, {"reason": "Left the agency."}, format="json")

    assert response.json()["is_active"] is False
    assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()  # Fleet.Users
    assert session.get(reverse("rentals:branch-bookings")).status_code == 401
    entry = AuditLog.objects.get(action="Account Disabled")
    assert entry.actor == admin and entry.after["reason"] == "Left the agency."

    enable = reverse("accounts:admin-user-enable", args=[user.pk])
    assert client.post(enable, {"reason": "Rejoined."}, format="json").json()["is_active"]
    assert AuditLog.objects.filter(action="Account Enabled").count() == 1


def test_only_staff_accounts_are_managed_here(client, admin):
    for user in (admin, CustomerFactory().user):
        url = reverse("accounts:admin-user-disable", args=[user.pk])
        assert client.post(url, {"reason": "x"}, format="json").status_code == 404
    listed = {row["role"] for row in client.get(USERS).json()["results"]}
    assert "ADMINISTRATOR" not in listed and "CUSTOMER" not in listed


def test_the_staff_list_filters_by_role_status_and_text(client):
    BranchStaffFactory(user__name="Asha Staff")
    MaintenanceTechnicianFactory(user__name="Tara Tech", user__is_active=False)
    names = lambda **q: [r["name"] for r in client.get(USERS, q).json()["results"]]  # noqa: E731
    assert names(role="MAINTENANCE_TECHNICIAN") == ["Tara Tech"]
    assert names(is_active="true") == ["Asha Staff"]
    assert names(q="tara") == ["Tara Tech"]


# ─── Accounts made here work in the other modules, own branch only ────────


def test_new_branch_staff_work_on_their_own_branch_only(client):
    own, other = BranchFactory(), BranchFactory()
    staff = _create(client, "BRANCH_STAFF", own)
    session = authenticated_client(staff)
    now = timezone.now()

    # Branch bookings (UC 7 step 1): today's collections.
    mine = BookingFactory(vehicle=CarFactory(home_branch=own), pickup_datetime=now)
    BookingFactory(vehicle=CarFactory(home_branch=other), pickup_datetime=now)
    listed = session.get(reverse("rentals:branch-bookings")).json()["results"]
    assert [b["id"] for b in listed] == [mine.pk]

    # Handover (N1): their branch's booking, refused elsewhere.
    ready = ready_booking(vehicle=CarFactory(home_branch=own))
    theirs = ready_booking(vehicle=CarFactory(home_branch=other))
    assert session.get(reverse("rentals:handover-detail", args=[theirs.pk])).status_code == 404
    rentals.handover_vehicle(ready.pk, staff, **checklist())
    assert Booking.objects.get(pk=ready.pk).status == Booking.Status.ACTIVE

    # Return (N2): the rentals due back at their branch.
    out = active_booking(vehicle=CarFactory(home_branch=own))
    active_booking(vehicle=CarFactory(home_branch=other))
    returns = {b["id"] for b in session.get(reverse("rentals:returns")).json()["results"]}
    assert returns == {out.pk}  # due back today, at their branch

    # Cash desk (R1, BR-9): their branch's cash collections.
    hold = {"status": "Pending Payment", "cash_on_collection": True}
    expires = now + timedelta(minutes=10)
    cash = BookingFactory(vehicle=CarFactory(home_branch=own), hold_expires_at=expires, **hold)
    BookingFactory(vehicle=CarFactory(home_branch=other), hold_expires_at=expires, **hold)
    desk = session.get(reverse("bookings:booking-awaiting-cash")).json()["results"]
    assert [b["id"] for b in desk] == [cash.pk]


def test_a_new_branch_manager_approves_the_odometer_override(client):
    booking = active_booking()
    manager = _create(client, "BRANCH_MANAGER", booking.pickup_branch)
    staff = BranchStaffFactory(branch=booking.pickup_branch).user
    far = readings(odometer_reading=13500)  # above Return.Odometer's plausibility limit
    total = rentals.return_quote(booking, staff, far).settlement.total
    report = rentals.return_vehicle(
        booking.pk,
        staff,
        request=RequestFactory().post("/api/v1/rentals/returns/"),
        **return_kwargs(
            readings=far,
            expected_total=total,
            override={"email": manager.email, "password": PASSWORD, "reason": "Outstation trip"},
        ),
    )
    assert report.odometer_override_by == manager
    assert report.odometer_override_reason == "Outstation trip"


def test_a_new_branch_manager_of_another_branch_cannot_approve(client):
    booking = active_booking()
    manager = _create(client, "BRANCH_MANAGER", BranchFactory())
    staff = BranchStaffFactory(branch=booking.pickup_branch).user
    far = readings(odometer_reading=13500)
    total = rentals.return_quote(booking, staff, far).settlement.total
    with pytest.raises(rentals.ReturnError) as raised:
        rentals.return_vehicle(
            booking.pk,
            staff,
            request=RequestFactory().post("/api/v1/rentals/returns/"),
            **return_kwargs(
                readings=far,
                expected_total=total,
                override={"email": manager.email, "password": PASSWORD, "reason": "Trip"},
            ),
        )
    assert raised.value.code == "override_refused"


def test_a_new_technician_is_authorised_on_the_users_screen(client):
    technician = _create(client, "MAINTENANCE_TECHNICIAN")
    url = reverse(
        "maintenance:technician-authorisation", args=[technician.maintenance_technician.pk]
    )
    assert client.put(url).status_code == 200
    data = client.get(reverse("accounts:admin-user", args=[technician.pk])).json()
    assert data["authorised_to_clear_unsafe"] is True


# ─── Blacklist (BR-4, UC 12 step 2 and extension 2a) ──────────────────────


def _paid_booking(customer) -> Booking:
    """A Confirmed booking paid by card through Book.Done (R1's real services)."""
    car = CarFactory(available_from=date(2026, 1, 1))
    TariffFactory(vehicle_category=car.category)
    pickup = next_pickup()
    booking = lifecycle.create_booking(
        customer,
        vehicle=car,
        pickup=pickup,
        return_=pickup + timedelta(days=1),
        terms_accepted=True,
    )
    return lifecycle.pay_booking(
        customer, booking.pk, payment_token="tok_visa", idempotency_key=f"n3-{booking.pk}"
    )


def test_blacklisting_records_the_reason_and_lists_confirmed_and_active_bookings(client, admin):
    customer = eligible_customer()
    confirmed = _paid_booking(customer)
    out = active_booking(customer=customer)
    url = reverse("accounts:admin-customer-blacklist", args=[customer.pk])

    assert client.post(url, {"reason": " "}, format="json").status_code == 400
    data = client.post(url, {"reason": "Returned a car with false plates."}, format="json").json()

    assert data["is_blacklisted"] is True
    assert data["blacklist_reason"] == "Returned a car with false plates."
    assert data["blacklisted_by"] == admin.name and data["blacklisted_at"]
    bookings = {b["id"]: b for b in data["open_bookings"]}
    assert (bookings[confirmed.pk]["status"], bookings[confirmed.pk]["return_pending"]) == (
        "Confirmed",
        False,
    )
    assert (bookings[out.pk]["status"], bookings[out.pk]["return_pending"]) == ("Active", True)
    entry = AuditLog.objects.get(action="Customer Blacklisted")
    assert (entry.actor, entry.before["is_blacklisted"], entry.after["is_blacklisted"]) == (
        admin,
        False,
        True,
    )
    assert client.post(url, {"reason": "Again"}, format="json").status_code == 400
    listed = client.get(CUSTOMERS, {"blacklisted": "true"}).json()["results"]
    assert [(c["customer_id"], c["blacklist_reason"]) for c in listed] == [
        (customer.pk, "Returned a car with false plates.")
    ]


def test_a_blacklisted_customer_cannot_book(client):
    """BR-4, enforced by the booking service as before."""
    customer = eligible_customer()
    client.post(
        reverse("accounts:admin-customer-blacklist", args=[customer.pk]),
        {"reason": "Fraud"},
        format="json",
    )
    car = CarFactory(available_from=date(2026, 1, 1))
    TariffFactory(vehicle_category=car.category)
    pickup = next_pickup()
    with pytest.raises(NotEligibleError) as refused:
        lifecycle.create_booking(
            Customer.objects.get(pk=customer.pk),
            vehicle=car,
            pickup=pickup,
            return_=pickup + timedelta(days=1),
            terms_accepted=True,
        )
    assert refused.value.code == "customer_blacklisted"


def test_a_confirmed_booking_is_cancelled_through_r2_and_audited_twice(client, admin):
    customer = eligible_customer()
    booking = _paid_booking(customer)
    client.post(
        reverse("accounts:admin-customer-blacklist", args=[customer.pk]),
        {"reason": "Fraud"},
        format="json",
    )
    url = reverse("accounts:admin-customer-booking-cancel", args=[customer.pk, booking.pk])
    quote = client.get(url).json()
    assert Decimal(quote["deposit_refund"]) == booking.security_deposit  # BR-8, R2's quote

    wrong = client.post(
        url, {"expected_refund": quote["total_refund"], "password": "nope"}, format="json"
    )
    assert wrong.status_code == 400 and "password" in wrong.json()  # SE-9
    response = client.post(
        url,
        {"expected_refund": quote["total_refund"], "password": "Test@12345"},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["status"] == "Cancelled"
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert RefundRequest.objects.filter(original_payment__booking=booking).exists()
    assert AuditLog.objects.filter(
        action="Booking Cancelled For Blacklist", actor=admin, entity_id=str(booking.pk)
    ).exists()
    assert AuditLog.objects.filter(
        action="Booking Status Changed", entity_id=str(booking.pk), after__status="Cancelled"
    ).exists()  # R2's own entry
    again = client.post(
        url, {"expected_refund": quote["total_refund"], "password": "Test@12345"}, format="json"
    )
    assert again.status_code == 404  # no longer open


def test_a_changed_refund_must_be_seen_again(client):
    customer = eligible_customer()
    booking = _paid_booking(customer)
    Customer.objects.filter(pk=customer.pk).update(is_blacklisted=True)
    url = reverse("accounts:admin-customer-booking-cancel", args=[customer.pk, booking.pk])
    response = client.post(
        url, {"expected_refund": "1.00", "password": "Test@12345"}, format="json"
    )
    assert response.status_code == 409 and response.json()["code"] == "refund_changed"
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.CONFIRMED


def test_an_active_booking_is_never_cancelled_here(client):
    customer = eligible_customer()
    out = active_booking(customer=customer)
    Customer.objects.filter(pk=customer.pk).update(is_blacklisted=True)
    url = reverse("accounts:admin-customer-booking-cancel", args=[customer.pk, out.pk])
    response = client.post(
        url, {"expected_refund": "0.00", "password": "Test@12345"}, format="json"
    )
    assert response.status_code == 409 and response.json()["code"] == "invalid_state"
    assert Booking.objects.get(pk=out.pk).status == Booking.Status.ACTIVE


def test_only_a_blacklisted_customers_booking_is_cancelled_here(client):
    customer = eligible_customer()
    booking = _paid_booking(customer)
    url = reverse("accounts:admin-customer-booking-cancel", args=[customer.pk, booking.pk])
    response = client.post(
        url, {"expected_refund": "7124.00", "password": "Test@12345"}, format="json"
    )
    assert response.status_code == 400 and "blacklisted" in response.json()["detail"][0]


def test_lifting_the_blacklist_is_audited_with_its_reason(client, admin):
    customer = CustomerFactory(is_blacklisted=True)
    url = reverse("accounts:admin-customer-lift-blacklist", args=[customer.pk])
    data = client.post(url, {"reason": "Cleared by the police."}, format="json").json()
    assert data["is_blacklisted"] is False and data["blacklist_reason"] is None
    entry = AuditLog.objects.get(action="Blacklist Lifted")
    assert entry.actor == admin and entry.after["reason"] == "Cleared by the police."


def test_customers_are_found_by_name_e_mail_or_mobile(client):
    CustomerFactory(user__name="Asha Rao", user__email="asha@example.com")
    CustomerFactory(user__name="Ravi Shah")
    found = lambda q: [c["name"] for c in client.get(CUSTOMERS, {"q": q}).json()["results"]]  # noqa: E731
    assert found("asha@") == ["Asha Rao"] and found("shah") == ["Ravi Shah"]


# ─── SE-4: Administrator only, every endpoint, every role ─────────────────

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


def _staff_url(name):
    return lambda: reverse(f"accounts:{name}", args=[BranchStaffFactory().user_id])


def _customer_url(name):
    return lambda: reverse(f"accounts:{name}", args=[CustomerFactory().pk])


def _cancel_url():
    booking = BookingFactory()
    return reverse("accounts:admin-customer-booking-cancel", args=[booking.customer_id, booking.pk])


ENDPOINTS = [
    ("admin-users-get", "get", lambda: USERS),
    ("admin-users-post", "post", lambda: USERS),
    ("admin-user-get", "get", _staff_url("admin-user")),
    ("admin-user-patch", "patch", _staff_url("admin-user")),
    ("admin-user-disable", "post", _staff_url("admin-user-disable")),
    ("admin-user-enable", "post", _staff_url("admin-user-enable")),
    ("admin-customers", "get", lambda: CUSTOMERS),
    ("admin-customer", "get", _customer_url("admin-customer")),
    ("admin-customer-blacklist", "post", _customer_url("admin-customer-blacklist")),
    ("admin-customer-lift-blacklist", "post", _customer_url("admin-customer-lift-blacklist")),
    ("admin-customer-booking-cancel-get", "get", _cancel_url),
    ("admin-customer-booking-cancel-post", "post", _cancel_url),
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


def test_every_users_admin_route_is_in_the_matrix():
    from apps.accounts.urls import urlpatterns

    named = {p.name for p in urlpatterns if p.name.startswith("admin-")}
    covered = {name.rsplit("-", 1)[0] if name.endswith(("-get", "-post", "-patch")) else name
               for name, *_ in ENDPOINTS}  # fmt: skip
    assert named == covered
