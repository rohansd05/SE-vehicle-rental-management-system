"""Booking eligibility: Exp 3 Licence.is_valid() and the customer rules (BR-2, BR-3, BR-4).

Book.Eligible.Licence: the licence is verified, authorises the vehicle's
type (D18: licence categories are the vehicle types) and does not expire
before the return date. BR-2: the minimum age on the pickup date (BK4).
BR-4: no blacklisted customer and no outstanding due.

Each refusal carries a stable `code` so the client can offer the right next
step (Book.Eligible.No: submit a licence now, keep browsing, or exit).
"""

from datetime import date, datetime

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Customer, Licence
from apps.core.choices import VehicleType


class NotEligibleError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def age_on(birth: date, day: date) -> int:
    return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


def _type_label(vehicle_type: str) -> str:
    return "two-wheeler" if vehicle_type == VehicleType.TWO_WHEELER else "car"


def licence_is_valid(licence: Licence | None, vehicle_type: str, return_: datetime) -> None:
    """Exp 3 Licence.is_valid() (Book.Eligible.Licence, BR-2, BR-3). Raises NotEligibleError."""
    if licence is None or licence.status not in (Licence.Status.VERIFIED, Licence.Status.EXPIRED):
        raise NotEligibleError(
            "licence_not_verified",
            "Your driving licence has not been verified yet. Submit it, or wait for our staff "
            "to check it, before you book.",
        )
    today = timezone.localdate()
    if licence.status == Licence.Status.EXPIRED or (
        licence.expiry_date is not None and licence.expiry_date < today
    ):
        raise NotEligibleError(
            "licence_expired", "Your driving licence has expired. Submit your renewed licence."
        )
    if licence.expiry_date is None or licence.expiry_date < timezone.localdate(return_):
        raise NotEligibleError(
            "licence_expires_before_return",
            "Your driving licence expires before the return date (BR-2). Choose an earlier "
            "return, or submit your renewed licence.",
        )
    endorsed = set(licence.categories.values_list("category", flat=True))
    if vehicle_type not in endorsed:
        raise NotEligibleError(
            "licence_category",
            f"Your driving licence does not cover a {_type_label(vehicle_type)} (BR-3).",
        )


def check_eligibility(
    customer: Customer, vehicle_type: str, pickup: datetime, return_: datetime
) -> None:
    """Book.Eligible.*: raise NotEligibleError for the first rule the customer fails."""
    if customer.is_blacklisted:
        raise NotEligibleError(
            "customer_blacklisted", "Your account cannot make bookings. Please contact us."
        )
    if customer.outstanding_due > 0:
        raise NotEligibleError(
            "outstanding_due",
            f"You have an outstanding due of {settings.CURRENCY} {customer.outstanding_due}. "
            "Clear it before you book (BR-4).",
        )
    licence = Licence.objects.filter(customer=customer).first()
    licence_is_valid(licence, vehicle_type, return_)
    minimum = (
        settings.MINIMUM_AGE_TWO_WHEELER
        if vehicle_type == VehicleType.TWO_WHEELER
        else settings.MINIMUM_AGE_CAR
    )
    if age_on(customer.date_of_birth, timezone.localdate(pickup)) < minimum:
        raise NotEligibleError(
            "under_age",
            f"You must be at least {minimum} on the pickup date to rent a "
            f"{_type_label(vehicle_type)} (BR-2).",
        )
