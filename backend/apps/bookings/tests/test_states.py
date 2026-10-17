"""Appendix B booking state machine: only the listed transitions are legal."""

import itertools

import pytest

from apps.bookings.models import Booking
from apps.bookings.states import (
    ALLOWED_TRANSITIONS,
    IllegalBookingTransition,
    check_transition,
    mark_cancelled,
    mark_no_show,
    record_extension,
    record_modification,
    transition,
)
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog

S = Booking.Status
LEGAL = {
    (S.DRAFT, S.PENDING_PAYMENT),
    (S.PENDING_PAYMENT, S.CONFIRMED),
    (S.PENDING_PAYMENT, S.DRAFT),
    # R2-P1, not in Appendix B: an unpaid cash-at-collection booking only.
    (S.PENDING_PAYMENT, S.CANCELLED),
    (S.PENDING_PAYMENT, S.NO_SHOW),
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


# ─── Module R2 state functions (each accepts only its own source status) ──


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("function", "source", "target"),
    [
        (record_modification, S.CONFIRMED, S.CONFIRMED),
        (record_extension, S.ACTIVE, S.ACTIVE),
        (mark_cancelled, S.CONFIRMED, S.CANCELLED),
    ],
)
def test_each_r2_change_is_saved_and_audited(function, source, target):
    booking = BookingFactory(status=source)
    function(booking, None)
    booking.refresh_from_db()
    assert booking.status == target
    entry = AuditLog.objects.filter(action="Booking Status Changed").latest("id")
    assert entry.before == {"status": source}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("function", "source"),
    [
        (record_modification, S.PENDING_PAYMENT),  # would otherwise confirm it unpaid
        (record_modification, S.ACTIVE),
        (record_extension, S.CONFIRMED),  # would otherwise activate it
        (mark_cancelled, S.PENDING_PAYMENT),  # a card hold simply expires
        (mark_cancelled, S.ACTIVE),
        (mark_cancelled, S.COMPLETED),
    ],
)
def test_each_r2_change_refuses_other_statuses(function, source):
    booking = BookingFactory(status=source)
    with pytest.raises(IllegalBookingTransition):
        function(booking, None)
    booking.refresh_from_db()
    assert booking.status == source


@pytest.mark.django_db
@pytest.mark.parametrize("source", [S.CONFIRMED, S.PENDING_PAYMENT])
def test_a_cash_booking_may_be_cancelled_or_a_no_show_before_payment(source):
    cancelled = BookingFactory(status=source, cash_on_collection=True)
    mark_cancelled(cancelled, None)
    missed = BookingFactory(status=source, cash_on_collection=True)
    mark_no_show(missed)
    cancelled.refresh_from_db()
    missed.refresh_from_db()
    assert (cancelled.status, missed.status) == (S.CANCELLED, S.NO_SHOW)


@pytest.mark.django_db
@pytest.mark.parametrize("source", [S.PENDING_PAYMENT, S.ACTIVE, S.DRAFT])
def test_only_a_confirmed_card_booking_becomes_a_no_show(source):
    booking = BookingFactory(status=source)
    with pytest.raises(IllegalBookingTransition):
        mark_no_show(booking)
