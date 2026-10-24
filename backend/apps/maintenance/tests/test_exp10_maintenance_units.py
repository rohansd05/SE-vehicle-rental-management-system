"""Experiment 10: unit tests for the Maintenance module (Nidhi Rajkamal Dhyani).

Three units of the BR-15 preventive-service rule are tested in isolation,
without a database (the vehicles are unsaved model instances):

- service_interval()  the (km, months) interval for the vehicle's type
- next_service_due()  the odometer and date of the next preventive service
- service_due()       whether the vehicle has reached that point by km or by date

The tests use Django's SimpleTestCase, an xUnit framework like JUnit:
one class per unit, one method per test case, assertEqual/assertIsNone.
"""

from datetime import date

from django.test import SimpleTestCase

from apps.core.choices import VehicleType
from apps.fleet.models import Vehicle, VehicleCategory
from apps.maintenance.services import next_service_due, service_due, service_interval


def make_vehicle(vehicle_type, *, odometer, last_km, last_date):
    """An unsaved vehicle: enough for the BR-15 functions, which never touch the database."""
    return Vehicle(
        category=VehicleCategory(name="Test", vehicle_type=vehicle_type),
        odometer=odometer,
        last_service_odometer=last_km,
        last_service_date=last_date,
    )


class ServiceIntervalTest(SimpleTestCase):
    """Unit 1: service_interval(vehicle) returns the BR-15 interval for its type."""

    def test_tc_m1_two_wheeler_interval_is_3000_km_or_4_months(self):
        """TC-M1: BR-15 gives a two-wheeler 3,000 km or 4 months."""
        scooter = make_vehicle(
            VehicleType.TWO_WHEELER, odometer=1000, last_km=0, last_date=date(2026, 6, 1)
        )
        self.assertEqual(service_interval(scooter), (3000, 4))


class NextServiceDueTest(SimpleTestCase):
    """Unit 2: next_service_due(vehicle) adds the interval to the last service."""

    def test_tc_m2_car_next_service_is_5000_km_or_6_months_after_last(self):
        """TC-M2: last serviced at 10,000 km on 15 Jan 2026, due at 15,000 km or 15 Jul 2026."""
        car = make_vehicle(
            VehicleType.CAR, odometer=12000, last_km=10000, last_date=date(2026, 1, 15)
        )
        due = next_service_due(car)
        self.assertEqual((due.odometer, due.date), (15000, date(2026, 7, 15)))

    def test_tc_m3_month_end_service_date_is_clamped_to_last_day_of_february(self):
        """TC-M3: 31 Aug 2026 + 6 months has no 31st, so it is due on 28 Feb 2027."""
        car = make_vehicle(
            VehicleType.CAR, odometer=10000, last_km=10000, last_date=date(2026, 8, 31)
        )
        self.assertEqual(next_service_due(car).date, date(2027, 2, 28))


class ServiceDueTest(SimpleTestCase):
    """Unit 3: service_due(vehicle, on) is the due point once reached, else None."""

    def test_tc_m4_car_at_exactly_the_due_odometer_is_due(self):
        """TC-M4: odometer 15,000 km equals the due reading, so the service is due."""
        car = make_vehicle(
            VehicleType.CAR, odometer=15000, last_km=10000, last_date=date(2026, 1, 15)
        )
        due = service_due(car, on=date(2026, 3, 1))
        self.assertIsNotNone(due)
        self.assertEqual(due.odometer, 15000)

    def test_tc_m5_car_below_due_km_and_before_due_date_is_not_due(self):
        """TC-M5: 14,999 km on 14 Jul 2026 reaches neither limit, so nothing is due."""
        car = make_vehicle(
            VehicleType.CAR, odometer=14999, last_km=10000, last_date=date(2026, 1, 15)
        )
        self.assertIsNone(service_due(car, on=date(2026, 7, 14)))
