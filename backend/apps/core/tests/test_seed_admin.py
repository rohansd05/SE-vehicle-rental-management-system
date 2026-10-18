"""Blacklist demo data (core/seed_admin.py, Module N3; Exp 2 UC 12 extension 2a)."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import Customer
from apps.bookings.models import Booking
from apps.core.seed_admin import ACTIVE_CAR, CONFIRMED_CAR, CUSTOMER_EMAIL
from apps.rentals import services as rentals

pytestmark = pytest.mark.django_db


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def _bookings():
    return Booking.objects.filter(customer__user__email=CUSTOMER_EMAIL).select_related("vehicle")


def test_the_customer_has_a_paid_confirmed_booking_and_an_active_rental():
    _seed()
    customer = Customer.objects.get(user__email=CUSTOMER_EMAIL)
    assert not customer.is_blacklisted  # the Administrator blacklists them in the demo
    assert customer.user.check_password("Demo@1234")
    by_car = {b.vehicle.registration_no: b for b in _bookings()}
    confirmed, active = by_car[CONFIRMED_CAR], by_car[ACTIVE_CAR]
    assert confirmed.status == Booking.Status.CONFIRMED
    assert confirmed.payments.filter(status="Succeeded").count() == 2  # rental and deposit
    assert active.status == Booking.Status.ACTIVE
    assert active.vehicle.status == "On Rent"
    assert rentals.return_refusals(active) == []  # it can be returned as usual


def test_seeding_again_adds_nothing_and_reset_reloads():
    _seed()
    _seed()
    assert _bookings().count() == 2
    _seed("--reset")
    assert _bookings().count() == 2
