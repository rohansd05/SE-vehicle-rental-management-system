"""SE-5, SE-11 (OWASP broken access control), Module N4: an IDOR sweep.

Every detail endpoint called with another user's id answers 404, never 403 or
200, so it does not even confirm that the record exists: a customer with
another customer's booking (R1, R2, R4 rating), branch staff or a branch
manager with another branch's booking, payment, refund, handover, return or
job (N1, N2, N3), and a technician with a job assigned to someone else.
The body is empty on purpose: each view looks the record up in the caller's
scope before it reads the body.

`test_every_id_endpoint_is_swept` fails when a new <int:pk> endpoint is added
without a line here.
"""

from decimal import Decimal

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.accounts.tests.factories import (
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.fleet.tests.factories import BranchFactory
from apps.maintenance.tests.factories import MaintenanceJobFactory
from apps.payments.models import RefundRequest
from apps.payments.tests.factories import PaymentFactory

pytestmark = pytest.mark.django_db

CUSTOMER_ENDPOINTS = [
    ("bookings:booking-detail", "get"),
    ("bookings:booking-hold", "post"),
    ("bookings:booking-pay", "post"),
    ("bookings:booking-invoice", "get"),
    ("bookings:booking-cancel", "get"),
    ("bookings:booking-cancel", "post"),
    ("bookings:booking-modify-quote", "post"),
    ("bookings:booking-modify", "post"),
    ("bookings:booking-extend-quote", "post"),
    ("bookings:booking-extend", "post"),
    ("bookings:booking-rating", "post"),
    ("bookings:booking-rating", "patch"),
]

# (url name, method, what the id points to, roles that call it)
BRANCH_ENDPOINTS = [
    ("bookings:booking-detail", "get", "booking", ("staff", "manager")),
    ("bookings:booking-invoice", "get", "booking", ("staff", "manager")),
    ("bookings:booking-cash", "post", "booking", ("staff",)),
    ("rentals:handover-detail", "get", "booking", ("staff", "manager")),
    ("rentals:handover-complete", "post", "booking", ("staff",)),
    ("rentals:return-detail", "get", "booking", ("staff", "manager")),
    ("rentals:return-quote", "post", "booking", ("staff",)),
    ("rentals:return-complete", "post", "booking", ("staff",)),
    ("payments:booking-capture", "post", "booking", ("staff",)),
    ("payments:payment-refund", "post", "payment", ("staff",)),
    ("payments:refund-pay-out", "post", "refund", ("staff",)),
    ("maintenance:job-detail", "get", "job", ("staff", "manager")),
    ("maintenance:job-schedule", "post", "job", ("staff", "manager")),
    ("maintenance:job-cancel", "post", "job", ("staff", "manager")),
    ("maintenance:vehicle-history", "get", "vehicle", ("staff", "manager")),
]

TECHNICIAN_ENDPOINTS = [
    ("maintenance:job-detail", "get"),
    ("maintenance:job-start", "post"),
    ("maintenance:job-record", "put"),
    ("maintenance:job-complete", "post"),
    ("maintenance:job-invoice", "put"),
]

# Ids no role-scoping applies to, with the reason.
NOT_OWNED = {
    # Administrators only; an Administrator sees every record (SE-4, scope_queryset).
    "accounts:admin-user",
    "accounts:admin-user-disable",
    "accounts:admin-user-enable",
    "accounts:admin-customer",
    "accounts:admin-customer-blacklist",
    "accounts:admin-customer-lift-blacklist",
    "fleet:admin-vehicle",
    "fleet:admin-vehicle-retire",
    "fleet:admin-vehicle-documents",
    "fleet:admin-vehicle-document",
    "fleet:admin-vehicle-photos",
    "fleet:admin-vehicle-photo",
    "fleet:admin-branch",
    "fleet:admin-branch-areas",
    "fleet:admin-branch-area",
    "pricing:admin-tariff",
    "pricing:admin-add-on",
    "pricing:admin-discount-code",
    "payments:refund-approve",
    "payments:refund-reject",
    "maintenance:job-approve-clearance",
    "maintenance:technician-authorisation",
    # Licence decisions: any Branch Staff or Administrator verifies any pending licence.
    "accounts:licence-approve",
    "accounts:licence-reject",
    # Search.Detail: the public catalogue (Search.Browse).
    "fleet:vehicle-detail",
}


def _swept() -> set[str]:
    return (
        {name for name, _ in CUSTOMER_ENDPOINTS}
        | {name for name, *_ in BRANCH_ENDPOINTS}
        | {name for name, _ in TECHNICIAN_ENDPOINTS}
        | {"accounts:admin-customer-booking-cancel"}
    )


def _id_patterns(resolver, namespace=""):
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            inner = f"{namespace}{pattern.namespace}:" if pattern.namespace else namespace
            yield from _id_patterns(pattern, inner)
        elif isinstance(pattern, URLPattern) and "<int:pk>" in str(pattern.pattern):
            yield f"{namespace}{pattern.name}"


def test_every_id_endpoint_is_swept():
    names = set(_id_patterns(get_resolver()))
    assert names, "no <int:pk> endpoints found"
    missing = names - _swept() - NOT_OWNED
    assert not missing, f"add these to the IDOR sweep or NOT_OWNED: {sorted(missing)}"
    assert not (_swept() | NOT_OWNED) - names, "a swept name no longer exists"


@pytest.mark.parametrize(("name", "method"), CUSTOMER_ENDPOINTS)
def test_a_customer_gets_404_for_another_customers_booking(name, method):
    theirs = BookingFactory(status=Booking.Status.COMPLETED)
    me = authenticated_client(CustomerFactory().user)
    response = getattr(me, method)(reverse(name, args=[theirs.pk]), {}, format="json")
    assert response.status_code == 404


@pytest.fixture
def other_branch_records():
    """One record of each kind, all at a branch the caller does not work at."""
    booking = BookingFactory()
    payment = PaymentFactory(booking=booking, amount=Decimal("1800.00"))
    refund = RefundRequest.objects.create(
        original_payment=payment,
        amount=Decimal("100.00"),
        reason="Sweep",
        status=RefundRequest.Status.APPROVED,
        requested_by=booking.customer.user,
        idempotency_key="idor-sweep-refund",
    )
    job = MaintenanceJobFactory(vehicle=booking.vehicle)
    return {
        "booking": booking.pk,
        "payment": payment.pk,
        "refund": refund.pk,
        "job": job.pk,
        "vehicle": booking.vehicle.pk,
    }


def _branch_user(role):
    branch = BranchFactory()
    if role == "staff":
        return BranchStaffFactory(branch=branch).user
    return BranchManagerFactory(branch=branch).user


@pytest.mark.parametrize(
    ("name", "method", "kind", "role"),
    [(n, m, k, r) for n, m, k, roles in BRANCH_ENDPOINTS for r in roles],
)
def test_branch_users_get_404_for_another_branchs_records(
    name, method, kind, role, other_branch_records
):
    client = authenticated_client(_branch_user(role))
    url = reverse(name, args=[other_branch_records[kind]])
    response = getattr(client, method)(url, {}, format="json")
    assert response.status_code == 404


@pytest.mark.parametrize(("name", "method"), TECHNICIAN_ENDPOINTS)
def test_a_technician_gets_404_for_a_job_assigned_to_someone_else(name, method):
    job = MaintenanceJobFactory()
    me = authenticated_client(MaintenanceTechnicianFactory().user)
    response = getattr(me, method)(reverse(name, args=[job.pk]), {}, format="json")
    assert response.status_code == 404


@pytest.mark.parametrize("method", ["get", "post"])
def test_an_administrator_gets_404_for_a_booking_under_the_wrong_customer(method):
    """UC 12 2a: the booking id must belong to the customer in the path."""
    from apps.accounts.tests.factories import AdministratorFactory

    booking = BookingFactory()
    other_customer = CustomerFactory()
    url = reverse("accounts:admin-customer-booking-cancel", args=[other_customer.pk, booking.pk])
    response = getattr(authenticated_client(AdministratorFactory().user), method)(
        url, {}, format="json"
    )
    assert response.status_code == 404
