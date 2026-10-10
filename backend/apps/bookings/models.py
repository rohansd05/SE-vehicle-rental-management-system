"""Booking models (SRS 3.1; Appendix A booking; Appendix B states).

Owner: Rohan (WBS 1.4.3). Only the owner edits this file or its migrations.
"""

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import F, Q

from apps.core.models import TimeStampedModel


def _money(**kwargs) -> models.DecimalField:
    return models.DecimalField(max_digits=12, decimal_places=2, **kwargs)


class Booking(TimeStampedModel):
    """Exp 3 Booking.

    Book.NoDouble / Book.Concurrent / Reliability-1: the database refuses two
    blocking bookings of one vehicle whose blocked periods overlap
    (ExclusionConstraint below). blocked_period is
    [pickup_datetime, return_datetime + BOOKING_TURNAROUND_BUFFER) (BR-1,
    Book.Done.Block) and is set in save(). Pending Payment blocks too,
    because the 15-minute hold must keep the vehicle from other customers
    (Book.Hold).
    """

    class Status(models.TextChoices):
        DRAFT = "Draft", "Draft"
        PENDING_PAYMENT = "Pending Payment", "Pending Payment"
        CONFIRMED = "Confirmed", "Confirmed"
        ACTIVE = "Active", "Active"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"
        NO_SHOW = "No-show", "No-show"

    # Statuses that hold the vehicle (Book.Hold, Book.NoDouble).
    BLOCKING_STATUSES = (Status.PENDING_PAYMENT, Status.CONFIRMED, Status.ACTIVE)

    # Book.Done.Store: assigned at confirmation, so blank while Draft.
    booking_reference = models.CharField(max_length=18, blank=True)
    pickup_datetime = models.DateTimeField()
    return_datetime = models.DateTimeField()
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    # Book.Done.Store: six digits, kept as text so leading zeros survive.
    pickup_code = models.CharField(
        max_length=6, blank=True, validators=[RegexValidator(r"^[0-9]{6}$")]
    )
    total_amount = _money(default=0)  # Appendix A "quoted amount"
    # Associations (Exp 3) and Appendix A booking attributes:
    customer = models.ForeignKey(
        "accounts.Customer", on_delete=models.PROTECT, related_name="bookings"
    )
    vehicle = models.ForeignKey("fleet.Vehicle", on_delete=models.PROTECT, related_name="bookings")
    pickup_branch = models.ForeignKey(
        "fleet.Branch", on_delete=models.PROTECT, related_name="bookings"
    )
    # Fleet.Tariff.History / BR-13: the tariff the booking was priced at.
    tariff = models.ForeignKey("pricing.Tariff", on_delete=models.PROTECT, related_name="bookings")
    security_deposit = _money(default=0)  # Appendix A; Pay.Deposit
    # Book.Deliver.Location: doorstep delivery inside the branch's serviceable area.
    delivery_address = models.TextField(blank=True)
    delivery_pincode = models.CharField(max_length=6, blank=True)
    hold_expires_at = models.DateTimeField(null=True, blank=True)  # Book.Hold
    confirmed_at = models.DateTimeField(null=True, blank=True)  # Book.Done.Store, BR-13
    terms_accepted_at = models.DateTimeField(null=True, blank=True)  # Book.Quote.Terms
    safety_notice_acknowledged_at = models.DateTimeField(null=True, blank=True)  # SA-1
    handed_over_at = models.DateTimeField(null=True, blank=True)  # Handover.Activate
    returned_at = models.DateTimeField(null=True, blank=True)  # Return.Checklist
    distance_travelled = models.PositiveIntegerField(null=True, blank=True)  # Return.Complete
    # BR-6 "less any discount"; D17.
    discount_code = models.ForeignKey(
        "pricing.DiscountCode",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
    )
    discount_amount = _money(default=0)
    blocked_period = DateTimeRangeField(editable=False)

    class Meta:
        ordering = ["-pickup_datetime"]
        indexes = [
            models.Index(fields=["customer", "-pickup_datetime"]),  # History.View
            models.Index(fields=["pickup_branch", "pickup_datetime"]),  # Book.Done.Branch
        ]
        constraints = [
            ExclusionConstraint(
                name="bookings_no_overlapping_vehicle_blocks",
                expressions=[
                    ("vehicle", RangeOperators.EQUAL),
                    ("blocked_period", RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=["Pending Payment", "Confirmed", "Active"]),
            ),
            models.CheckConstraint(
                condition=Q(return_datetime__gt=F("pickup_datetime")),
                name="bookings_return_after_pickup",
            ),
            models.UniqueConstraint(
                fields=["booking_reference"],
                condition=~Q(booking_reference=""),
                name="bookings_reference_unique",
            ),
            models.CheckConstraint(
                condition=Q(booking_reference="")
                | Q(booking_reference__regex=r"^VRMS-[0-9]{8}-[0-9]{4}$"),
                name="bookings_reference_format",
            ),
            models.CheckConstraint(
                condition=Q(pickup_code="") | Q(pickup_code__regex=r"^[0-9]{6}$"),
                name="bookings_pickup_code_format",
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0) & Q(security_deposit__gte=0),
                name="bookings_amounts_not_negative",
            ),
            models.CheckConstraint(
                condition=Q(discount_amount__gte=0), name="bookings_discount_not_negative"
            ),
        ]

    def __str__(self) -> str:
        return self.booking_reference or f"Booking {self.pk} ({self.status})"

    def save(self, *args, **kwargs):
        self.blocked_period = self.compute_blocked_period()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and {"pickup_datetime", "return_datetime"} & set(
            update_fields
        ):
            kwargs["update_fields"] = {*update_fields, "blocked_period"}
        super().save(*args, **kwargs)

    def compute_blocked_period(self) -> DateTimeTZRange:
        """[pickup, return + turnaround buffer) — BR-1, Book.Done.Block."""
        return DateTimeTZRange(
            self.pickup_datetime,
            self.return_datetime + settings.BOOKING_TURNAROUND_BUFFER,
            "[)",
        )


class BookingAddOn(models.Model):
    """An add-on on a booking (Book.Addons; Appendix A 0:m add-on).

    daily_rate is copied from the AddOn when it is added, so a later change
    to the published rate never alters the booking (BR-13).
    """

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="add_ons")
    add_on = models.ForeignKey(
        "pricing.AddOn", on_delete=models.PROTECT, related_name="booking_lines"
    )
    quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    daily_rate = _money()
    # e.g. the name of an additional named driver (Book.Addons).
    detail = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "booking add-on"
        constraints = [
            models.UniqueConstraint(fields=["booking", "add_on"], name="bookings_addon_once"),
            models.CheckConstraint(
                condition=Q(quantity__gte=1) & Q(daily_rate__gte=0),
                name="bookings_addon_quantity_and_rate",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.add_on} x{self.quantity} on {self.booking}"


class Rating(models.Model):
    """D13 (G1): a customer's rating of a completed booking.

    Feeds the average rating shown and filtered on in search (Search.Detail,
    Search.Filter); the average is computed, never stored. Only a Completed
    booking may be rated; the rating service enforces that.
    """

    booking = models.OneToOneField(Booking, on_delete=models.PROTECT, related_name="rating")
    vehicle_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    service_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(vehicle_rating__gte=1) & Q(vehicle_rating__lte=5),
                name="bookings_rating_vehicle_1_to_5",
            ),
            models.CheckConstraint(
                condition=Q(service_rating__gte=1) & Q(service_rating__lte=5),
                name="bookings_rating_service_1_to_5",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.booking}: vehicle {self.vehicle_rating}/5, service {self.service_rating}/5"
