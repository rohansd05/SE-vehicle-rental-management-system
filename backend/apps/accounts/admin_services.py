"""Staff accounts and the customer blacklist (SRS 3.7 Fleet.Users, Fleet.Audit;
BR-4; Exp 2 use case 12 "Manage Users and Blacklist").

- Branch Staff, Maintenance Technician and Branch Manager accounts are
  created, edited, disabled and re-enabled by an Administrator. Disabling ends
  every session at once (blacklist_all_refresh_tokens(); an access token of an
  inactive user is refused on the next request) and refuses later sign-ins;
  nothing the user did before is changed.
- A customer is blacklisted with a reason (BR-4 then refuses new bookings).
  The reason is kept in the audit entry, which is append-only. Their Confirmed
  bookings are listed so the Administrator decides on each (UC 12 extension
  2a); a cancellation goes through R2's bookings.services.cancel_booking(),
  never a copy of it.

Every change is audited (Fleet.Audit). Module N3 (Nidhi), kept apart from the
sign-in and licence services (services.py, Rohan's).
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import CharField, OuterRef, QuerySet, Subquery
from django.db.models.fields.json import KT
from django.db.models.functions import Cast

from apps.core.audit import record_audit, snapshot
from apps.core.models import AuditLog

from .models import BranchManager, BranchStaff, Customer, MaintenanceTechnician, User
from .services import blacklist_all_refresh_tokens

Role = User.Role
STAFF_ROLES = (Role.BRANCH_STAFF, Role.MAINTENANCE_TECHNICIAN, Role.BRANCH_MANAGER)
USER_FIELDS = ("email", "name", "mobile_no", "address")

BLACKLISTED = "Customer Blacklisted"
BLACKLIST_LIFTED = "Blacklist Lifted"
CANCELLED_FOR_BLACKLIST_REASON = (
    "An Administrator cancelled the booking of a blacklisted customer (UC 12 extension 2a); "
    "refund per BR-8."
)


class UserAdminError(Exception):
    def __init__(self, message: str, *, field: str | None = None):
        self.field = field
        super().__init__(message)


def profile_of(user: User):
    """The Exp 3 profile of a staff account: BranchStaff, MaintenanceTechnician or BranchManager."""
    if user.role == Role.BRANCH_STAFF:
        return getattr(user, "branch_staff", None)
    if user.role == Role.MAINTENANCE_TECHNICIAN:
        return getattr(user, "maintenance_technician", None)
    administrator = getattr(user, "administrator", None)
    return getattr(administrator, "branchmanager", None) if administrator else None


def _check_email(email: str, exclude_pk=None) -> str:
    email = email.strip().lower()
    if User.objects.exclude(pk=exclude_pk).filter(email__iexact=email).exists():
        raise UserAdminError("An account with this e-mail address already exists.", field="email")
    return email


def _check_profile_fields(role: str, data: dict) -> None:
    if role == Role.MAINTENANCE_TECHNICIAN:
        if not data.get("workshop", "").strip():
            raise UserAdminError("Enter the technician's workshop.", field="workshop")
    elif data.get("branch") is None:
        raise UserAdminError("Assign the account to a branch (Fleet.Users).", field="branch")


@transaction.atomic
def create_staff_account(actor, data: dict, request=None) -> User:
    """Fleet.Users, UC 12 step 1: a Branch Staff, Maintenance Technician or Branch Manager
    account, assigned to a branch (a technician to a workshop). The Administrator sets
    the first password, which the user can change after signing in (Proposed N3-P8)."""
    role = data["role"]
    if role not in STAFF_ROLES:
        raise UserAdminError("Choose Branch Staff, Technician or Branch Manager.", field="role")
    _check_profile_fields(role, data)
    email = _check_email(data["email"])
    candidate = User(email=email, name=data["name"], mobile_no=data["mobile_no"])
    try:
        validate_password(data["password"], user=candidate)
    except DjangoValidationError as exc:
        raise UserAdminError(" ".join(exc.messages), field="password") from exc
    user = User.objects.create_user(
        email=email,
        password=data["password"],
        name=data["name"].strip(),
        mobile_no=data["mobile_no"],
        address=data.get("address", "").strip(),
        role=role,
    )
    if role == Role.BRANCH_STAFF:
        profile = BranchStaff.objects.create(user=user, branch=data["branch"])
    elif role == Role.BRANCH_MANAGER:
        profile = BranchManager.objects.create(user=user, branch=data["branch"])
    else:
        profile = MaintenanceTechnician.objects.create(user=user, workshop=data["workshop"].strip())
    record_audit(actor, "Create", user, after=snapshot(user), request=request)
    record_audit(actor, "Create", profile, after=snapshot(profile), request=request)
    return user


def _staff(user: User) -> User:
    if user.role not in STAFF_ROLES:
        raise UserAdminError("Only staff, technician and branch manager accounts are managed here.")
    return user


@transaction.atomic
def update_staff_account(user: User, actor, data: dict, request=None) -> User:
    """UC 12 step 1 "edits": name, e-mail, mobile, address, and the branch or workshop.
    The role does not change; disable the account and create another instead."""
    user = _staff(User.objects.select_for_update().get(pk=user.pk))
    before = snapshot(user)
    if "email" in data:
        data = {**data, "email": _check_email(data["email"], exclude_pk=user.pk)}
    for name in USER_FIELDS:
        if name in data:
            setattr(user, name, data[name].strip() if name != "email" else data[name])
    user.save()
    record_audit(actor, "Update", user, before, snapshot(user), request)

    profile = profile_of(user)
    field = "workshop" if user.role == Role.MAINTENANCE_TECHNICIAN else "branch"
    if profile is not None and field in data:
        if field == "workshop" and not data["workshop"].strip():
            raise UserAdminError("Enter the technician's workshop.", field="workshop")
        profile_before = snapshot(profile)
        setattr(profile, field, data[field].strip() if field == "workshop" else data[field])
        profile.save()
        record_audit(actor, "Update", profile, profile_before, snapshot(profile), request)
    return user


@transaction.atomic
def set_account_active(user: User, actor, *, active: bool, reason: str, request=None) -> User:
    """Fleet.Users: disable (sessions end at once, sign-in refused) or re-enable."""
    user = _staff(User.objects.select_for_update().get(pk=user.pk))
    if user.pk == getattr(actor, "pk", None):
        raise UserAdminError("You cannot disable your own account.")
    if not reason.strip():
        raise UserAdminError("Give the reason.", field="reason")
    if user.is_active == active:
        return user
    before = snapshot(user)
    user.is_active = active
    user.save(update_fields=["is_active"])
    ended = 0 if active else blacklist_all_refresh_tokens(user)
    record_audit(
        actor,
        "Account Enabled" if active else "Account Disabled",
        user,
        before,
        {**snapshot(user), "reason": reason.strip(), "sessions_ended": ended},
        request,
    )
    return user


# ─── Blacklist (BR-4, UC 12 step 2) ───────────────────────────────────────


def _latest_blacklisting() -> QuerySet:
    return AuditLog.objects.filter(
        action=BLACKLISTED,
        entity_type=Customer._meta.label,
        entity_id=Cast(OuterRef("pk"), output_field=CharField()),
    ).order_by("-id")


def customers_with_blacklist() -> QuerySet:
    """Customers, each with the reason, time and Administrator of the latest blacklisting."""
    latest = _latest_blacklisting()
    return (
        Customer.objects.select_related("user")
        .annotate(
            blacklist_reason=Subquery(latest.values(reason=KT("after__reason"))[:1]),
            blacklisted_at=Subquery(latest.values("timestamp")[:1]),
            blacklisted_by=Subquery(latest.values("actor__name")[:1]),
        )
        .order_by("user__name", "pk")
    )


def _set_blacklisted(customer: Customer, actor, blacklisted: bool, reason: str, request):
    reason = reason.strip()
    if not reason:
        raise UserAdminError("Give the reason.", field="reason")
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    if customer.is_blacklisted == blacklisted:
        state = "already blacklisted" if blacklisted else "not blacklisted"
        raise UserAdminError(f"This customer is {state}.")
    before = snapshot(customer)
    customer.is_blacklisted = blacklisted
    customer.save(update_fields=["is_blacklisted", "updated_at"])
    record_audit(
        actor,
        BLACKLISTED if blacklisted else BLACKLIST_LIFTED,
        customer,
        before,
        {**snapshot(customer), "reason": reason},
        request,
    )
    return customer


@transaction.atomic
def blacklist_customer(customer: Customer, actor, reason: str, request=None) -> Customer:
    """BR-4, UC 12 step 2: blacklisted with the reason; new bookings are then refused."""
    return _set_blacklisted(customer, actor, True, reason, request)


@transaction.atomic
def lift_blacklist(customer: Customer, actor, reason: str, request=None) -> Customer:
    return _set_blacklisted(customer, actor, False, reason, request)


def open_bookings(customer: Customer) -> QuerySet:
    """UC 12 extension 2a: Confirmed bookings (the Administrator decides on each) and
    Active ones (return pending, never cancelled here)."""
    from apps.bookings.models import Booking

    return (
        Booking.objects.filter(
            customer=customer, status__in=(Booking.Status.CONFIRMED, Booking.Status.ACTIVE)
        )
        .select_related("vehicle", "pickup_branch")
        .order_by("pickup_datetime")
    )


def cancel_for_blacklist(
    customer: Customer, booking_id: int, actor, *, expected_refund, request=None
):
    """UC 12 extension 2a: cancel one Confirmed booking of a blacklisted customer through
    R2's cancel_booking() (BR-8 refund, vehicle released, customer and branch told), with
    the Administrator recorded as the actor of every entry and the reason on the status
    change."""
    from apps.bookings import services as bookings

    if not Customer.objects.filter(pk=customer.pk, is_blacklisted=True).exists():
        raise UserAdminError(
            "Only a blacklisted customer's bookings are cancelled here (UC 12 extension 2a)."
        )
    return bookings.cancel_booking(
        customer,
        booking_id,
        expected_refund=expected_refund,
        actor=actor,
        reason=CANCELLED_FOR_BLACKLIST_REASON,
        request=request,
    )
