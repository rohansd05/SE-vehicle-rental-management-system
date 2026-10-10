"""Vehicle status service (Fleet.Status, Appendix B Figure 4, BR-16, Fleet.Retire, SE-10).

Owner: Nidhi (fleet/services/status.py).
"""

from datetime import timedelta
from itertools import product

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog
from apps.fleet.models import Vehicle
from apps.fleet.services.status import (
    ALLOWED_TRANSITIONS,
    ActorNotPermittedError,
    FutureBookingsExistError,
    IllegalTransitionError,
    VehicleStatusError,
    update_status,
)
from apps.fleet.tests.factories import CarFactory, TwoWheelerFactory

pytestmark = pytest.mark.django_db

S = Vehicle.Status

LEGAL = [
    (S.AVAILABLE, S.ON_RENT),
    (S.AVAILABLE, S.UNDER_MAINTENANCE),
    (S.AVAILABLE, S.UNSAFE),
    (S.AVAILABLE, S.RETIRED),
    (S.ON_RENT, S.AVAILABLE),
    (S.ON_RENT, S.UNDER_MAINTENANCE),
    (S.ON_RENT, S.UNSAFE),
    (S.ON_RENT, S.RETIRED),
    (S.UNDER_MAINTENANCE, S.AVAILABLE),
    (S.UNDER_MAINTENANCE, S.UNSAFE),
    (S.UNDER_MAINTENANCE, S.RETIRED),
    (S.UNSAFE, S.AVAILABLE),
    (S.UNSAFE, S.RETIRED),
]
ILLEGAL = [(a, b) for a, b in product(S.values, S.values) if a != b and (a, b) not in set(LEGAL)]


@pytest.fixture
def admin():
    return AdministratorFactory().user


@pytest.fixture
def staff():
    return BranchStaffFactory().user


def _entries(vehicle):
    return AuditLog.objects.filter(entity_type="fleet.Vehicle", entity_id=str(vehicle.pk))


def test_transition_table_matches_appendix_b():
    assert {(a, b) for a, targets in ALLOWED_TRANSITIONS.items() for b in targets} == set(LEGAL)
    assert len(ILLEGAL) == 7


@pytest.mark.parametrize(("current", "new"), LEGAL)
def test_every_legal_transition_is_saved_and_audited(current, new, admin):
    vehicle = CarFactory(status=current)
    result = update_status(vehicle, new, actor=admin, reason="test")

    vehicle.refresh_from_db()
    assert vehicle.status == result.status == new
    entry = _entries(vehicle).get()
    assert entry.actor == admin  # BR-16: the actor is recorded
    assert entry.action == "Vehicle Status Changed"
    assert entry.before == {"status": current}
    assert entry.after == {"status": new, "reason": "test"}


@pytest.mark.parametrize(("current", "new"), ILLEGAL)
def test_every_illegal_transition_is_refused(current, new, admin):
    vehicle = CarFactory(status=current)
    with pytest.raises(IllegalTransitionError) as caught:
        update_status(vehicle, new, actor=admin, reason="test")

    assert (caught.value.current, caught.value.new) == (current, new)
    vehicle.refresh_from_db()
    assert vehicle.status == current
    assert not _entries(vehicle).exists()


def test_unknown_status_is_refused(admin):
    vehicle = CarFactory()
    with pytest.raises(IllegalTransitionError):
        update_status(vehicle, "Stolen", actor=admin, reason="test")


def test_same_status_is_a_no_op_without_audit(staff):
    vehicle = CarFactory(status=S.UNSAFE)
    update_status(vehicle, S.UNSAFE, actor=staff, reason="flagged twice")
    vehicle.refresh_from_db()
    assert vehicle.status == S.UNSAFE
    assert not _entries(vehicle).exists()


def test_errors_share_a_base_class():
    assert issubclass(IllegalTransitionError, VehicleStatusError)
    assert issubclass(ActorNotPermittedError, VehicleStatusError)
    assert issubclass(FutureBookingsExistError, VehicleStatusError)


# ─── BR-16: only an Administrator clears an Unsafe flag ───────────────────


@pytest.mark.parametrize(
    "make_actor",
    [
        lambda: BranchStaffFactory().user,
        lambda: MaintenanceTechnicianFactory().user,
        lambda: BranchManagerFactory().user,
        lambda: CustomerFactory().user,
        lambda: AnonymousUser(),
        lambda: None,
    ],
    ids=["staff", "technician", "branch-manager", "customer", "anonymous", "system"],
)
def test_br16_non_administrator_cannot_clear_unsafe(make_actor):
    vehicle = CarFactory(status=S.UNSAFE)
    with pytest.raises(ActorNotPermittedError, match="BR-16"):
        update_status(vehicle, S.AVAILABLE, actor=make_actor(), reason="repaired")
    vehicle.refresh_from_db()
    assert vehicle.status == S.UNSAFE
    assert not _entries(vehicle).exists()


def test_br16_disabled_administrator_cannot_clear_unsafe():
    admin = AdministratorFactory(user__is_active=False).user
    vehicle = CarFactory(status=S.UNSAFE)
    with pytest.raises(ActorNotPermittedError):
        update_status(vehicle, S.AVAILABLE, actor=admin, reason="repaired")


def test_br16_administrator_clears_unsafe_and_is_recorded(admin):
    vehicle = TwoWheelerFactory(status=S.UNSAFE)
    update_status(vehicle, S.AVAILABLE, actor=admin, reason="brakes replaced")
    vehicle.refresh_from_db()
    assert vehicle.status == S.AVAILABLE
    assert _entries(vehicle).get().actor == admin


@pytest.mark.parametrize("current", [S.AVAILABLE, S.ON_RENT, S.UNDER_MAINTENANCE])
def test_any_authenticated_caller_may_flag_unsafe(current, staff):
    """Maint.Unsafe: "an authorised user"; who that is, is the calling endpoint's check."""
    vehicle = CarFactory(status=current)
    update_status(vehicle, S.UNSAFE, actor=staff, reason="brake failure")
    vehicle.refresh_from_db()
    assert vehicle.status == S.UNSAFE


def test_other_transitions_do_not_need_an_administrator(staff):
    vehicle = CarFactory(status=S.UNDER_MAINTENANCE)
    update_status(vehicle, S.AVAILABLE, actor=staff, reason="job completed")
    vehicle.refresh_from_db()
    assert vehicle.status == S.AVAILABLE


# ─── Fleet.Retire ─────────────────────────────────────────────────────────


def test_only_an_administrator_retires(staff):
    vehicle = CarFactory()
    with pytest.raises(ActorNotPermittedError):
        update_status(vehicle, S.RETIRED, actor=staff, reason="old")


@pytest.mark.parametrize(
    "booking_status", [Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED]
)
def test_cannot_retire_with_a_future_booking(booking_status, admin):
    booking = BookingFactory(status=booking_status)
    with pytest.raises(FutureBookingsExistError):
        update_status(booking.vehicle, S.RETIRED, actor=admin, reason="old")


def test_cannot_retire_during_an_active_rental_even_if_overdue(admin):
    start = timezone.now() - timedelta(days=3)
    booking = BookingFactory(
        status=Booking.Status.ACTIVE,
        pickup_datetime=start,
        return_datetime=start + timedelta(days=1),
    )
    with pytest.raises(FutureBookingsExistError):
        update_status(booking.vehicle, S.RETIRED, actor=admin, reason="old")


def test_finished_bookings_do_not_block_retirement(admin):
    vehicle = CarFactory()
    start = timezone.now() - timedelta(days=10)
    for status in (Booking.Status.COMPLETED, Booking.Status.CANCELLED):
        BookingFactory(
            vehicle=vehicle,
            status=status,
            pickup_datetime=start,
            return_datetime=start + timedelta(days=1),
            booking_reference="",
        )
        start += timedelta(days=2)
    update_status(vehicle, S.RETIRED, actor=admin, reason="end of life")
    vehicle.refresh_from_db()
    assert vehicle.status == S.RETIRED


# ─── Locking and the model method ─────────────────────────────────────────


def test_transition_is_checked_against_the_database_not_a_stale_instance(staff):
    vehicle = CarFactory(status=S.AVAILABLE)
    Vehicle.objects.filter(pk=vehicle.pk).update(status=S.UNSAFE)  # changed elsewhere
    with pytest.raises(ActorNotPermittedError):
        update_status(vehicle, S.AVAILABLE, actor=staff, reason="stale")
    with pytest.raises(IllegalTransitionError):
        update_status(vehicle, S.ON_RENT, actor=staff, reason="stale")


def test_row_is_locked_for_update(admin, monkeypatch):
    vehicle = CarFactory()
    seen = []
    original = Vehicle.objects.select_for_update

    def spy(*args, **kwargs):
        seen.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(Vehicle.objects, "select_for_update", spy)
    update_status(vehicle, S.ON_RENT, actor=admin, reason="handover")
    assert seen


def test_model_method_delegates_to_the_service(admin):
    """Exp 3 Vehicle.update_status() keeps its class-diagram name."""
    car = CarFactory(status=S.UNSAFE)
    car.update_status(S.AVAILABLE, actor=admin, reason="cleared")
    assert car.status == S.AVAILABLE
    car.refresh_from_db()
    assert car.status == S.AVAILABLE
    assert _entries(car).get().actor == admin
