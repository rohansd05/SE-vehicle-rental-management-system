"""Appendix B booking state machine: only the listed transitions are legal."""

import itertools

import pytest

from apps.bookings.models import Booking
from apps.bookings.states import (
    ALLOWED_TRANSITIONS,
    IllegalBookingTransition,
    check_transition,
    transition,
)
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog

S = Booking.Status
LEGAL = {
    (S.DRAFT, S.PENDING_PAYMENT),
    (S.PENDING_PAYMENT, S.CONFIRMED),
    (S.PENDING_PAYMENT, S.DRAFT),
    (S.CONFIRMED, S.CONFIRMED),
    (S.CONFIRMED, S.ACTIVE),
    (S.CONFIRMED, S.CANCELLED),
    (S.CONFIRMED, S.NO_SHOW),
    (S.ACTIVE, S.ACTIVE),
    (S.ACTIVE, S.COMPLETED),
}


def test_the_table_is_exactly_appendix_b():
    table = {(a, b) for a, targets in ALLOWED_TRANSITIONS.items() for b in targets}
    assert table == LEGAL
    assert set(ALLOWED_TRANSITIONS) == set(S.values)


@pytest.mark.parametrize(("current", "new"), list(itertools.product(S.values, S.values)))
def test_every_pair_is_allowed_or_refused(current, new):
    if (current, new) in LEGAL:
        check_transition(current, new)
    else:
        with pytest.raises(IllegalBookingTransition, match=f"from {current} to {new}"):
            check_transition(current, new)


@pytest.mark.django_db
def test_transition_saves_and_audits():
    booking = BookingFactory(status=S.CONFIRMED)
    transition(booking, S.CANCELLED, actor=None, reason="test")
    booking.refresh_from_db()
    assert booking.status == S.CANCELLED
    entry = AuditLog.objects.filter(action="Booking Status Changed").latest("id")
    assert entry.before == {"status": "Confirmed"}
    assert entry.after == {"status": "Cancelled", "reason": "test"}


@pytest.mark.django_db
def test_an_illegal_transition_changes_nothing():
    booking = BookingFactory(status=S.COMPLETED)
    with pytest.raises(IllegalBookingTransition):
        transition(booking, S.ACTIVE, actor=None, reason="test")
    booking.refresh_from_db()
    assert booking.status == S.COMPLETED
