"""Pricing models: tariffs, add-ons and fuel prices (BR-6, BR-7, BR-10 to BR-13).

Owner: Nidhi (WBS 1.4.2). Only the owner edits this file or its migrations.
"""

from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.choices import FuelType, VehicleType
from apps.core.exceptions import ImmutableRecordError
from apps.core.models import TimeStampedModel


def _money(**kwargs) -> models.DecimalField:
    return models.DecimalField(max_digits=12, decimal_places=2, **kwargs)


class Tariff(TimeStampedModel):
    """Exp 3 Tariff, per vehicle category (Fleet.Tariff).

    BR-13: only an Administrator defines a tariff (defined_by), and a tariff
    is never edited once it has taken effect; a change is a new row with a
    later effective_from. Bookings keep a reference to the row they were
    priced at (Fleet.Tariff.History).
    """

    vehicle_category = models.ForeignKey(
        "fleet.VehicleCategory", on_delete=models.PROTECT, related_name="tariffs"
    )
    hourly_rate = _money()
    daily_rate = _money()
    weekly_rate = _money()  # Fleet.Tariff
    security_deposit = _money()  # BR-3
    # Fleet.Tariff, Book.Quote.Terms, BR-11. Unit (km per rental day) is proposed.
    free_km_allowance = models.PositiveIntegerField(help_text="Kilometres per rental day.")
    excess_km_rate = _money()  # BR-11
    effective_from = models.DateTimeField()
    # Administrator–Tariff association (Exp 3); BR-13.
    defined_by = models.ForeignKey(
        "accounts.Administrator", on_delete=models.PROTECT, related_name="tariffs"
    )

    class Meta:
        ordering = ["vehicle_category", "-effective_from"]
        get_latest_by = "effective_from"
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle_category", "effective_from"], name="pricing_tariff_unique_start"
            ),
            models.CheckConstraint(
                condition=Q(hourly_rate__gte=0)
                & Q(daily_rate__gte=0)
                & Q(weekly_rate__gte=0)
                & Q(security_deposit__gte=0)
                & Q(excess_km_rate__gte=0),
                name="pricing_tariff_amounts_not_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.vehicle_category.name} from {self.effective_from:%Y-%m-%d}"

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._stored_effective_from = instance.__dict__.get("effective_from")
        return instance

    def save(self, *args, **kwargs):
        if not self._state.adding and self._has_taken_effect():
            raise ImmutableRecordError(
                "BR-13: a tariff in effect is never edited; create a new tariff instead."
            )
        super().save(*args, **kwargs)
        self._stored_effective_from = self.effective_from

    def delete(self, *args, **kwargs):
        if self._has_taken_effect():
            raise ImmutableRecordError("BR-13: tariff history is retained; it cannot be deleted.")
        return super().delete(*args, **kwargs)

    def _has_taken_effect(self) -> bool:
        stored = getattr(self, "_stored_effective_from", None) or self.effective_from
        return stored is not None and stored <= timezone.now()


class AddOn(TimeStampedModel):
    """Book.Addons: helmet, child seat, luggage carrier, named driver, delivery.

    BR-7: charged at the published daily rate. Changing a rate never alters a
    confirmed booking, because BookingAddOn keeps its own copy (BR-13).
    """

    name = models.CharField(max_length=64, unique=True)
    daily_rate = _money()
    # Proposed: restricts an add-on to one vehicle type (blank = any).
    vehicle_type = models.CharField(max_length=16, choices=VehicleType.choices, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "add-on"
        constraints = [
            models.CheckConstraint(
                condition=Q(daily_rate__gte=0), name="pricing_addon_rate_not_negative"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class FuelPrice(TimeStampedModel):
    """BR-12: the prevailing fuel or electricity price, with its history."""

    fuel_type = models.CharField(max_length=16, choices=FuelType.choices)
    price_per_unit = _money(help_text="Per litre, per kg (CNG) or per kWh (electric).")
    effective_from = models.DateTimeField()
    defined_by = models.ForeignKey(
        "accounts.Administrator", on_delete=models.PROTECT, related_name="fuel_prices"
    )

    class Meta:
        ordering = ["fuel_type", "-effective_from"]
        get_latest_by = "effective_from"
        constraints = [
            models.UniqueConstraint(
                fields=["fuel_type", "effective_from"], name="pricing_fuelprice_unique_start"
            ),
            models.CheckConstraint(
                condition=Q(price_per_unit__gte=0), name="pricing_fuelprice_not_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.fuel_type} {self.price_per_unit} from {self.effective_from:%Y-%m-%d}"


class DiscountCode(TimeStampedModel):
    """D17 (G5): an admin-managed discount for BR-6 ("less any discount").

    The code is unique regardless of case; a Percent value lies in (0, 100].
    """

    class DiscountType(models.TextChoices):
        PERCENT = "Percent", "Percent"
        FIXED = "Fixed", "Fixed"

    code = models.CharField(max_length=32)
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices)
    value = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Percent (0-100) or a fixed amount."
    )
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(
        null=True, blank=True, help_text="Empty for unlimited use."
    )
    times_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(Lower("code"), name="pricing_discountcode_code_ci_unique"),
            models.CheckConstraint(
                condition=Q(value__gt=0), name="pricing_discountcode_value_positive"
            ),
            models.CheckConstraint(
                condition=~Q(discount_type="Percent") | Q(value__lte=100),
                name="pricing_discountcode_percent_max_100",
            ),
            models.CheckConstraint(
                condition=Q(valid_to__gt=F("valid_from")),
                name="pricing_discountcode_valid_window",
            ),
            models.CheckConstraint(
                condition=Q(usage_limit__isnull=True) | Q(times_used__lte=F("usage_limit")),
                name="pricing_discountcode_within_usage_limit",
            ),
        ]

    def __str__(self) -> str:
        return self.code
