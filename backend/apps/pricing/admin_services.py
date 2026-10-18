"""Tariff, add-on and discount code administration (SRS 3.7 Fleet.Tariff,
Fleet.Tariff.History; BR-13; D17; Exp 2 use case 11 step 2; Exp 3
Administrator.define_tariff()).

A tariff is never edited once in effect: a change is a new tariff with its
own effective date, and the old one stays (pricing/models.py). Bookings keep
the tariff they were priced at, so a new tariff reaches only new bookings and
R2's modifications (UC 11 extension 2a); this module changes no pricing code.
Every write is audited (Fleet.Audit).

Module N3 (Nidhi), kept apart from the pricing services (Rohan's).
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.audit import record_audit, snapshot
from apps.core.exceptions import ImmutableRecordError

from .models import AddOn, DiscountCode, Tariff
from .services import security_deposit_for

RATE_FIELDS = (
    "hourly_rate",
    "daily_rate",
    "weekly_rate",
    "free_km_allowance",
    "excess_km_rate",
)


class PricingAdminError(Exception):
    def __init__(self, message: str, *, field: str | None = None):
        self.field = field
        super().__init__(message)


def tariff_state(tariff: Tariff, in_force: dict[int, Tariff], now=None) -> str:
    """Fleet.Tariff.History: In force, Scheduled (a later effective date) or Superseded."""
    now = now or timezone.now()
    if tariff.effective_from > now:
        return "Scheduled"
    held = in_force.get(tariff.vehicle_category_id)
    return "In force" if held is not None and held.pk == tariff.pk else "Superseded"


@transaction.atomic
def define_tariff(actor, data: dict, request=None) -> Tariff:
    """BR-13: only an Administrator defines a tariff, from its effective date (now if
    none is given; never in the past). The security deposit is BR-3's for the type."""
    administrator = getattr(actor, "administrator", None)
    if actor.role != User.Role.ADMINISTRATOR or administrator is None:
        raise PricingAdminError("Only an Administrator may create or change a tariff (BR-13).")
    category = data["vehicle_category"]
    effective_from = data.get("effective_from") or timezone.now()
    if effective_from < timezone.now():
        raise PricingAdminError(
            "The effective date cannot be in the past; leave it empty to start now.",
            field="effective_from",
        )
    if Tariff.objects.filter(vehicle_category=category, effective_from=effective_from).exists():
        raise PricingAdminError(
            "This category already has a tariff from that moment.", field="effective_from"
        )
    tariff = Tariff.objects.create(
        vehicle_category=category,
        effective_from=effective_from,
        security_deposit=security_deposit_for(category.vehicle_type),
        defined_by=administrator,
        **{name: data[name] for name in RATE_FIELDS},
    )
    record_audit(actor, "Create", tariff, after=snapshot(tariff), request=request)
    return tariff


@transaction.atomic
def withdraw_tariff(tariff: Tariff, actor, request=None) -> None:
    """A scheduled tariff may be withdrawn before it takes effect; history never is."""
    before, pk = snapshot(tariff), tariff.pk
    try:
        tariff.delete()
    except ImmutableRecordError as exc:
        raise PricingAdminError("A tariff in effect is kept; define a new one instead.") from exc
    tariff.pk = pk
    record_audit(actor, "Delete", tariff, before=before, request=request)


def _check_add_on_name(name: str, exclude_pk=None) -> str:
    name = name.strip()
    if AddOn.objects.exclude(pk=exclude_pk).filter(name__iexact=name).exists():
        raise PricingAdminError("An add-on with this name already exists.", field="name")
    return name


@transaction.atomic
def save_add_on(actor, data: dict, add_on: AddOn | None = None, request=None) -> AddOn:
    """Book.Addons, BR-7: a published daily rate. A booking keeps its own copy of the
    rate (BookingAddOn), so a change never alters a confirmed booking."""
    before = snapshot(add_on) if add_on else None
    add_on = add_on or AddOn()
    if "name" in data:
        data = {**data, "name": _check_add_on_name(data["name"], add_on.pk)}
    for name, value in data.items():
        setattr(add_on, name, value)
    add_on.save()
    record_audit(actor, "Update" if before else "Create", add_on, before, snapshot(add_on), request)
    return add_on


def _check_discount(code: DiscountCode) -> None:
    if code.discount_type == DiscountCode.DiscountType.PERCENT and code.value > 100:
        raise PricingAdminError("A percentage cannot be above 100.", field="value")
    if code.valid_to <= code.valid_from:
        raise PricingAdminError("The code must end after it starts.", field="valid_to")
    if code.usage_limit is not None and code.usage_limit < code.times_used:
        raise PricingAdminError(
            f"The code has been used {code.times_used} times already.", field="usage_limit"
        )


@transaction.atomic
def save_discount_code(
    actor, data: dict, code: DiscountCode | None = None, request=None
) -> DiscountCode:
    """D17: an admin-managed discount code (unique whatever the case). The code itself
    never changes once created; bookings record the code and the amount applied."""
    before = snapshot(code) if code else None
    if code is None:
        text = data["code"].strip().upper()
        if DiscountCode.objects.filter(code__iexact=text).exists():
            raise PricingAdminError("This code already exists.", field="code")
        code = DiscountCode(code=text)
    for name, value in data.items():
        if name != "code":
            setattr(code, name, value)
    _check_discount(code)
    code.save()
    record_audit(actor, "Update" if before else "Create", code, before, snapshot(code), request)
    return code
