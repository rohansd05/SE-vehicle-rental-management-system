"""Experiment 10: unit tests for the Booking module (Rohan Dhumal).

Three units are tested in isolation, without a database:

- refund_percent()   (bookings/services.py)  BR-8 cancellation refund slabs
- check_transition() (bookings/states.py)    the booking state machine
- age_on()           (bookings/eligibility.py) BR-2 minimum-age check

The tests use Django's SimpleTestCase, an xUnit framework like JUnit:
one class per unit, one method per test case, assertEqual/assertRaises.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from apps.bookings.eligibility import age_on
from apps.bookings.models import Booking
from apps.bookings.services import refund_percent
from apps.bookings.states import IllegalBookingTransition, check_transition

Status = Booking.Status


class RefundPercentTest(SimpleTestCase):
    """Unit 1: refund_percent(notice) returns the BR-8 share of the rental refunded."""

    def test_tc_b1_exactly_48_hours_notice_gives_full_refund(self):
        """TC-B1: 48 h notice is the lower boundary of the 100% slab."""
        self.assertEqual(refund_percent(timedelta(hours=48)), Decimal("100"))

    def test_tc_b2_exactly_12_hours_notice_gives_75_percent(self):
        """TC-B2: 12 h notice is the lower boundary of the 75% slab."""
        self.assertEqual(refund_percent(timedelta(hours=12)), Decimal("75"))

    def test_tc_b3_11_hours_59_minutes_notice_gives_50_percent(self):
        """TC-B3: one minute under 12 h falls into the 50% slab."""
        self.assertEqual(refund_percent(timedelta(hours=11, minutes=59)), Decimal("50"))


class BookingStateMachineTest(SimpleTestCase):
    """Unit 2: check_transition(current, new) allows only the Appendix B transitions."""

    def test_tc_b4_completed_booking_cannot_become_active_again(self):
        """TC-B4: Completed is a final state, so Completed -> Active is refused."""
        with self.assertRaises(IllegalBookingTransition):
            check_transition(Status.COMPLETED, Status.ACTIVE)


class AgeOnTest(SimpleTestCase):
    """Unit 3: age_on(birth, day) returns the age in whole years on a given day (BR-2)."""

    def test_tc_b5_one_day_before_21st_birthday_is_still_20(self):
        """TC-B5: born 25 Oct 2005, on 24 Oct 2026 the customer is 20, too young for a car."""
        self.assertEqual(age_on(date(2005, 10, 25), date(2026, 10, 24)), 20)
