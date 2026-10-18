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
# Maint.Auto.Km / Maint.Auto.Time: the severity of a job the system raises.
# Proposed (N3-P3; the SRS names no severity for it).
PREVENTIVE_JOB_SEVERITY = "Medium"

# Fleet.Add: at least four photographs of every vehicle. Image types and size
# proposed (N3-P5): the licence image limits (D20).
VEHICLE_PHOTOS_MINIMUM = 4
VEHICLE_PHOTO_EXTENSIONS = ("jpg", "jpeg", "png")
VEHICLE_PHOTO_MAX_BYTES = 5 * 1024 * 1024

# Context diagram "document expiry alert" (SA-3): documents expiring within this
# window are listed in the daily alert to Administrators. Proposed (N3-P4).
DOCUMENT_EXPIRY_ALERT_WINDOW = timedelta(days=30)

# Maint.Record "permit the workshop invoice to be attached". Proposed (N3-P6):
# a PDF or a photo of it, at most 5 MB.
WORKSHOP_INVOICE_EXTENSIONS = ("pdf", "jpg", "jpeg", "png")
WORKSHOP_INVOICE_MAX_BYTES = 5 * 1024 * 1024

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

# Handover.Checklist: at least four photographs covering all sides of the vehicle,
# so one photo of each side is required.
HANDOVER_PHOTO_SIDES = ("Front", "Rear", "Left", "Right")
# Handover.Refuse, SA-3: statutory documents valid for the whole booked period.
HANDOVER_REQUIRED_DOCUMENTS = (
    "Insurance",
    "Pollution Certificate",
    "Fitness Certificate",
    "Road Tax",
)
# Condition photos and the signature image. Proposed (SRS silent): the licence
# image limits above (D20).
CONDITION_IMAGE_EXTENSIONS = LICENCE_IMAGE_EXTENSIONS
CONDITION_IMAGE_MAX_BYTES = LICENCE_IMAGE_MAX_BYTES

# Return.Odometer: a distance above this many km per started day of the rental
# needs a supervisor override with a recorded reason. Proposed (the SRS names
# "the configured plausibility limit" but gives no value; it amends D16).
ODOMETER_PLAUSIBILITY_KM_PER_DAY = 1000

# UC 13 Approve Refund: a refund above this amount waits for an Administrator.
# Proposed (the SRS names an "automatic approval threshold" but gives no value).
REFUND_AUTO_APPROVAL_LIMIT = Decimal("5000.00")
