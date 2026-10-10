"""Book.Concurrent, Book.NoDouble, Reliability-1: simultaneous bookings of one vehicle.

Each attempt runs in its own thread with its own database connection and
transaction, released together by a barrier, against committed data
(transaction=True). Exactly one booking may hold the vehicle; every other
customer is told it is no longer available and is never charged.
"""

import threading
from datetime import timedelta

import pytest
from django.db import connection

from apps.bookings import lifecycle
from apps.bookings.models import Booking
from apps.bookings.tests.conftest import eligible_customer
from apps.payments.models import Payment

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.concurrency]


def race(attempts):
    """Run every callable at the same moment; return (results, errors)."""
    barrier = threading.Barrier(len(attempts))
    results, errors = [], []
    lock = threading.Lock()

    def run(attempt):
        try:
            barrier.wait(timeout=30)
            outcome = attempt()
            with lock:
                results.append(outcome)
        except Exception as exc:  # collected and asserted on below
            with lock:
                errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(attempt,)) for attempt in attempts]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return results, errors


def _book_and_pay(customer, car, pickup, return_, n):
    def attempt():
        booking = lifecycle.create_booking(
            customer, vehicle=car, pickup=pickup, return_=return_, terms_accepted=True
        )
        return lifecycle.pay_booking(
            customer, booking.pk, payment_token="tok_visa", idempotency_key=f"race-key-{n:04d}"
        )

    return attempt


@pytest.mark.parametrize("contenders", [2, 20])
def test_exactly_one_of_simultaneous_bookings_succeeds(car, pickup, return_, contenders):
    customers = [eligible_customer() for _ in range(contenders)]
    results, errors = race(
        [_book_and_pay(customer, car, pickup, return_, n) for n, customer in enumerate(customers)]
    )

    assert len(results) == 1, errors
    assert len(errors) == contenders - 1
    assert all(isinstance(error, lifecycle.VehicleUnavailableError) for error in errors), errors
    winner = results[0]
    assert winner.status == Booking.Status.CONFIRMED
    assert Booking.objects.filter(vehicle=car).count() == 1
    # Book.Concurrent: "without charging that customer".
    assert set(Payment.objects.values_list("booking", flat=True)) == {winner.pk}


def test_overlapping_but_different_periods_also_race_safely(car, pickup):
    a, b = eligible_customer(), eligible_customer()
    results, errors = race(
        [
            _book_and_pay(a, car, pickup, pickup + timedelta(days=2), 1),
            _book_and_pay(b, car, pickup + timedelta(days=1), pickup + timedelta(days=3), 2),
        ]
    )
    assert len(results) == 1
    assert [type(error) for error in errors] == [lifecycle.VehicleUnavailableError]


def test_without_the_vehicle_lock_the_constraint_still_lets_only_one_through(
    car, pickup, return_, monkeypatch
):
    """Remove the application checks: the exclusion constraint alone decides (Book.NoDouble)."""
    monkeypatch.setattr(lifecycle, "is_available", lambda *args: True)
    customers = [eligible_customer() for _ in range(5)]
    results, errors = race(
        [_book_and_pay(customer, car, pickup, return_, n) for n, customer in enumerate(customers)]
    )
    assert len(results) == 1
    assert all(isinstance(error, lifecycle.VehicleUnavailableError) for error in errors), errors


def test_different_vehicles_book_in_parallel(car, scooter, pickup, return_):
    a, b = eligible_customer(), eligible_customer()

    def scooter_attempt():
        booking = lifecycle.create_booking(
            b,
            vehicle=scooter,
            pickup=pickup,
            return_=return_,
            terms_accepted=True,
            safety_notice_acknowledged=True,
        )
        return lifecycle.pay_booking(
            b, booking.pk, payment_token="tok_visa", idempotency_key="race-key-b"
        )

    results, errors = race([_book_and_pay(a, car, pickup, return_, 1), scooter_attempt])
    assert errors == []
    assert {booking.status for booking in results} == {Booking.Status.CONFIRMED}
