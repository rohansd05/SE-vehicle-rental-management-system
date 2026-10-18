"""DEMO data for Rate Vehicle (Module R4, Exp 2 UC 6), loaded by `seed_demo --reports`.

Fictitious. Behind --reports because the bookings it needs carry invoices and
ledger entries, which are append-only (so plain `seed_demo --reset` keeps
working):

- reports@vrms.test (R3) rates five of its past Completed bookings, so the
  catalogue shows averages and counts and the rating sort and filter have
  something to sort. Its booking returned four days ago stays unrated, so it
  is invited to rate.
- rating@vrms.test has one Completed booking returned three days ago (inside
  the 14-day window, not rated yet) and one returned 23 days ago, to show the
  refusal.

Bookings go through R3's _seed_booking() (state machine, calculate_price(),
invoice, ledger). Ratings are written as the rating service would, with an
audit entry; created now, so each is editable for 24 hours after loading.
Idempotent on the same day, like the reports demo.
"""

from collections.abc import Callable

from apps.accounts.models import Customer
from apps.core.audit import record_audit, snapshot

from .models import Booking, Rating

RATER_EMAIL = "rating@vrms.test"
RATER_NAME = "Demo Customer (rating)"
RATER_MOBILE = "+919800000014"
RATER_LICENCE = "MH02 20180066778"

# reports@ bookings by (days before today of the pickup, vehicle): vehicle and service
# scores, comment. See apps/reports/seed.py BOOKINGS.
REPORTS_RATINGS = [
    (84, "MH02DB2001", 5, 5, "Spotless car and a quick handover."),
    (66, "MH02DB2002", 4, 5, ""),
    (20, "MH02DB2002", 5, 4, "Smooth drive; the pickup took a little while."),
    (75, 1, 3, 4, "Fine for the city, a bit noisy on the highway."),
    (12, 6, 4, 4, ""),
]

# rating@ bookings, in R3's spec form: (days ago, rental days, vehicle, add-on, code,
# method, outcome). Demo vehicles 0 (Swift) and 5 (Dzire), both at Andheri.
RATER_BOOKINGS = [
    (5, 2, 0, "", "", "Card", "returned"),  # returned 3 days ago: may be rated
    (25, 2, 5, "", "", "Card", "returned"),  # returned 23 days ago: too late (UC 6)
]


def seed_demo_rating_data(count: Callable[[str, bool], None]) -> None:
    """Called by `seed_demo --reports` after the reports data."""
    from apps.reports import seed as reports

    customer = Customer.objects.get(user__email=reports.CUSTOMER_EMAIL)
    for days_ago, key, vehicle_rating, service_rating, comment in REPORTS_RATINGS:
        booking = Booking.objects.filter(
            customer=customer,
            vehicle=reports._vehicle(key),
            pickup_datetime=reports._at(days_ago),
            status=Booking.Status.COMPLETED,
        ).first()
        if booking is None:  # loaded on an earlier day; its dates have moved
            continue
        rating, created = Rating.objects.get_or_create(
            booking=booking,
            defaults={
                "vehicle_rating": vehicle_rating,
                "service_rating": service_rating,
                "comment": comment,
            },
        )
        count("ratings", created)
        if created:
            record_audit(None, "Create", rating, after=snapshot(rating))

    rater = reports._seed_customer(
        count,
        email=RATER_EMAIL,
        name=RATER_NAME,
        mobile_no=RATER_MOBILE,
        licence_number=RATER_LICENCE,
    )
    for spec in RATER_BOOKINGS:
        reports._seed_booking(count, rater, spec)
