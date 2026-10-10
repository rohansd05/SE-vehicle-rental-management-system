"""factory-boy factories for bookings."""

from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.tests.factories import CustomerFactory
from apps.bookings.models import Booking, BookingAddOn, Rating
from apps.fleet.tests.factories import CarFactory
from apps.pricing.tests.factories import AddOnFactory, TariffFactory


def _next_hour():
    return timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=2)


class BookingFactory(factory.django.DjangoModelFactory):
    """A Confirmed booking by default, with a reference and pickup code."""

    class Meta:
        model = Booking

    customer = factory.SubFactory(CustomerFactory)
    vehicle = factory.SubFactory(CarFactory)
    pickup_branch = factory.SelfAttribute("vehicle.home_branch")
    tariff = factory.SubFactory(
        TariffFactory, vehicle_category=factory.SelfAttribute("..vehicle.category")
    )
    pickup_datetime = factory.LazyFunction(_next_hour)
    return_datetime = factory.LazyAttribute(lambda o: o.pickup_datetime + timedelta(days=1))
    status = Booking.Status.CONFIRMED
    booking_reference = factory.Sequence(lambda n: f"VRMS-20261010-{n % 10000:04d}")
    pickup_code = factory.Sequence(lambda n: f"{n % 1000000:06d}")
    total_amount = Decimal("1800.00")
    security_deposit = Decimal("5000.00")
    confirmed_at = factory.LazyFunction(timezone.now)


class BookingAddOnFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BookingAddOn

    booking = factory.SubFactory(BookingFactory)
    add_on = factory.SubFactory(AddOnFactory)
    quantity = 1
    daily_rate = factory.SelfAttribute("add_on.daily_rate")


class RatingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Rating

    booking = factory.SubFactory(BookingFactory, status=Booking.Status.COMPLETED)
    vehicle_rating = 5
    service_rating = 4
    comment = "Clean car, quick handover."
