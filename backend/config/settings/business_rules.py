"""Business-rule constants (SRS Section 5.5, BR-1 to BR-16, and fixed values).

Every numeric threshold the code needs lives here, with the rule it comes
from, so a change to a rule is made in one place only (Maintainability-1).
Never introduce a threshold that the SRS does not state; if one is needed,
list it in docs/model-mapping.md under "Proposed - awaiting team approval".
"""

from datetime import timedelta
from decimal import Decimal

# BR-1: one confirmed booking per vehicle at any instant, plus a turnaround
# buffer between consecutive bookings for inspection and cleaning.
BOOKING_TURNAROUND_BUFFER = timedelta(minutes=60)

# BR-2: minimum age to rent.
MINIMUM_AGE_TWO_WHEELER = 18
MINIMUM_AGE_CAR = 21

# BR-3: refundable security deposit per rental, in CURRENCY.
SECURITY_DEPOSIT_TWO_WHEELER = Decimal("2000.00")
SECURITY_DEPOSIT_CAR = Decimal("5000.00")

# BR-5: rental period limits, extensions included.
RENTAL_PERIOD_MINIMUM = timedelta(hours=4)
RENTAL_PERIOD_MAXIMUM = timedelta(days=30)

# BR-6: periods over 24 hours are billed in whole days; shorter periods in
# whole hours, a part-hour billed as a full hour after a 15-minute grace.
DAILY_BILLING_THRESHOLD = timedelta(hours=24)
PART_HOUR_GRACE = timedelta(minutes=15)

# BR-6 / Pay.Invoice taxes. D14 (G2): PLACEHOLDER awaiting confirmation by
# the team; the SRS states no rate. Do not treat 18% as a confirmed rule.
TAX_RATE_PERCENT = Decimal("18.00")

# BR-7: helmets provided free with every two-wheeler rental, per rider.
FREE_HELMETS_PER_RIDER = 1

# BR-8: cancellation refund of the rental amount by notice before collection.
CANCELLATION_FULL_REFUND_NOTICE = timedelta(hours=48)
CANCELLATION_PARTIAL_REFUND_NOTICE = timedelta(hours=12)
CANCELLATION_REFUND_PERCENT_FULL = Decimal("100")
CANCELLATION_REFUND_PERCENT_PARTIAL = Decimal("75")
CANCELLATION_REFUND_PERCENT_LATE = Decimal("50")
NO_SHOW_RETAINED_PERCENT = Decimal("50")

# BR-10: late return.
LATE_RETURN_GRACE = timedelta(minutes=15)
LATE_RETURN_DAILY_CAP_PERIOD = timedelta(hours=24)
LATE_RETURN_FULL_DAY_AFTER = timedelta(hours=6)

# BR-12: fuel or charge shortfall service charge on top of the prevailing price.
FUEL_SHORTFALL_SERVICE_CHARGE_PERCENT = Decimal("20")

# BR-14: deposit balance refunded within this many working days of completion.
DEPOSIT_REFUND_WORKING_DAYS = 7

# BR-15: preventive service interval, whichever occurs first.
PREVENTIVE_SERVICE_INTERVAL_KM_CAR = 5000
PREVENTIVE_SERVICE_INTERVAL_MONTHS_CAR = 6
PREVENTIVE_SERVICE_INTERVAL_KM_TWO_WHEELER = 3000
PREVENTIVE_SERVICE_INTERVAL_MONTHS_TWO_WHEELER = 4

# Book.Hold / Book.Hold.Expire: temporary hold while the customer pays.
PAYMENT_HOLD_DURATION = timedelta(minutes=15)

# Book.Modify: modification cut-off before the pickup time.
MODIFICATION_CUTOFF = timedelta(hours=12)

# Appendix B: a booking becomes No-show this long after the pickup time.
NO_SHOW_AFTER = timedelta(hours=2)

# Book.Done.Store / Appendix A: booking reference and pickup code formats.
BOOKING_REFERENCE_PREFIX = "VRMS"
BOOKING_REFERENCE_REGEX = r"^VRMS-[0-9]{8}-[0-9]{4}$"
PICKUP_CODE_LENGTH = 6

# SE-7 one-time passwords. D15 (G3): lifetime and attempt limit per code.
OTP_LIFETIME = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
# Proposed (SRS silent; docs/decisions.md D20): code length and the minimum
# wait before another code can be requested.
OTP_CODE_LENGTH = 6
OTP_RESEND_COOLDOWN = timedelta(seconds=60)

# SE-8: account lockout (configured with django-axes in Phase 1B, D11).
LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCKOUT_DURATION = timedelta(minutes=15)

# Licence images (Appendix A front/back image; HI-1 camera images; D3).
# Proposed (SRS silent; docs/decisions.md D20): accepted types and size limit.
LICENCE_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png")
LICENCE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
