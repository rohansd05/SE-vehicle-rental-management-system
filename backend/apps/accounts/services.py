"""Accounts business logic: registration, OTPs, sign-in events, profile, password.

Every write here calls record_audit (Fleet.Audit, SE-10). Views stay thin.
"""

import secrets
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.core.audit import record_audit, snapshot
from apps.notifications.services import queue_email, queue_otp_sms

from .models import Customer, Licence, LicenceCategory, OneTimePassword, User


class OTPError(Exception):
    """A code was wrong, expired, used up or never issued. Shown generically."""


# ─── One-time passwords (SE-7, D15) ───────────────────────────────────────


def issue_otp(user: User, purpose: str, destination: str, request=None) -> OneTimePassword:
    """Invalidate the user's open codes for `purpose` and queue a new one by SMS.

    The row starts with an unusable hash; the Celery task generates the code
    and stores its hash (assign_otp_code), so the plain code is never stored.
    """
    now = timezone.now()
    OneTimePassword.objects.filter(
        user=user, purpose=purpose, consumed_at__isnull=True, expires_at__gt=now
    ).update(expires_at=now)
    otp = OneTimePassword.objects.create(
        user=user,
        purpose=purpose,
        destination=destination,
        code_hash=make_password(None),
        expires_at=now + settings.OTP_LIFETIME,
    )
    queue_otp_sms(otp)
    record_audit(user, "OTP Issued", otp, after={"purpose": purpose}, request=request)
    return otp


def assign_otp_code(otp_id: int) -> str:
    """Called by the send_otp task: create the code and keep only its hash."""
    length = settings.OTP_CODE_LENGTH
    code = f"{secrets.randbelow(10**length):0{length}d}"
    OneTimePassword.objects.filter(pk=otp_id).update(code_hash=make_password(code))
    return code


def verify_otp(user: User, purpose: str, code: str) -> OneTimePassword:
    """Consume the user's open code for `purpose`, or raise OTPError.

    A wrong code counts an attempt; after OTP_MAX_ATTEMPTS the code is dead
    and a new one must be requested (D15). The count is committed even when
    the attempt fails.
    """
    with transaction.atomic():
        otp = (
            OneTimePassword.objects.select_for_update()
            .filter(
                user=user,
                purpose=purpose,
                consumed_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )
        if otp is None or otp.attempt_count >= settings.OTP_MAX_ATTEMPTS:
            failure = True
        elif check_password(code, otp.code_hash):
            otp.consumed_at = timezone.now()
            otp.save(update_fields=["consumed_at"])
            failure = False
        else:
            otp.attempt_count += 1
            otp.save(update_fields=["attempt_count"])
            failure = True
    if failure:
        raise OTPError("The code is invalid or has expired.")
    return otp


# ─── Registration (SE-7) ──────────────────────────────────────────────────


@transaction.atomic
def register_customer(
    *,
    email: str,
    password: str,
    name: str,
    mobile_no: str,
    address: str,
    date_of_birth,
    emergency_contact_name: str,
    emergency_contact_mobile: str,
    request=None,
) -> Customer:
    """Create an inactive customer account and send the mobile OTP (SE-7).

    The account becomes active only when the OTP is verified.
    """
    user = User.objects.create_user(
        email=email.lower(),
        password=password,
        name=name,
        mobile_no=mobile_no,
        address=address,
        role=User.Role.CUSTOMER,
        is_active=False,
    )
    customer = Customer.objects.create(
        user=user,
        date_of_birth=date_of_birth,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_mobile=emergency_contact_mobile,
    )
    Licence.objects.create(customer=customer)  # status Not Submitted (Appendix A)
    record_audit(user, "Register", user, after=snapshot(user), request=request)
    record_audit(user, "Create", customer, after=snapshot(customer), request=request)
    issue_otp(user, OneTimePassword.Purpose.REGISTRATION, mobile_no, request)
    return customer


def find_unverified_user(email: str) -> User | None:
    """An inactive customer who has never completed registration.

    A customer an administrator disabled has a consumed registration OTP, so
    the registration flow can never re-activate them (Fleet.Users).
    """
    completed = OneTimePassword.objects.filter(
        user=OuterRef("pk"),
        purpose=OneTimePassword.Purpose.REGISTRATION,
        consumed_at__isnull=False,
    )
    return (
        User.objects.filter(email=email.lower(), is_active=False, role=User.Role.CUSTOMER)
        .exclude(Exists(completed))
        .first()
    )


def activate_account(email: str, code: str, request=None) -> User:
    """Verify the registration OTP and activate the account (SE-7).

    verify_otp runs in its own transaction first, so a wrong code's attempt
    count is kept even though this call then fails (D15).
    """
    user = find_unverified_user(email)
    if user is None:
        raise OTPError("The code is invalid or has expired.")
    verify_otp(user, OneTimePassword.Purpose.REGISTRATION, code)
    with transaction.atomic():
        before = snapshot(user)
        user.is_active = True
        user.save(update_fields=["is_active"])
        record_audit(user, "Account Verified", user, before, snapshot(user), request)
    return user


def resend_registration_otp(email: str, request=None) -> None:
    """Issue a fresh registration code if an unverified account exists.

    Silent otherwise, so the response never reveals whether an account exists.
    """
    user = find_unverified_user(email)
    if user is not None:
        with transaction.atomic():
            issue_otp(user, OneTimePassword.Purpose.REGISTRATION, user.mobile_no, request)


# ─── Sign-in events (SE-10) ───────────────────────────────────────────────


def record_login(user: User, request=None) -> None:
    record_audit(user, "Login", user, request=request)


def record_failed_login(email: str, request=None) -> None:
    user = User.objects.filter(email=email.lower()).first()
    record_audit(
        None,
        "Login Failed",
        user,
        after={"email": email.lower()},
        request=request,
        entity_label=None if user else "accounts.User",
        entity_id=None if user else "",
    )


def record_logout(user: User, request=None) -> None:
    record_audit(user, "Logout", user, request=request)


def blacklist_all_refresh_tokens(user: User) -> int:
    """End every session of `user` (password change, Fleet.Users disable)."""
    count = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        count += int(created)
    return count


# ─── Profile and password ─────────────────────────────────────────────────


@transaction.atomic
def update_profile(user: User, data: dict, request=None) -> bool:
    """Update name and address at once; a new mobile number waits for an OTP.

    SE-7: possession of the new number is proved before it replaces the old
    one. Returns True when a mobile change is pending.
    """
    before = snapshot(user)
    changed = [field for field in ("name", "address") if field in data]
    for field in changed:
        setattr(user, field, data[field])
    if changed:
        user.save(update_fields=changed)
        record_audit(user, "Update", user, before, snapshot(user), request)
    new_mobile = data.get("mobile_no")
    if new_mobile and new_mobile != user.mobile_no:
        issue_otp(user, OneTimePassword.Purpose.MOBILE_CHANGE, new_mobile, request)
        return True
    return False


def confirm_mobile_change(user: User, code: str, request=None) -> User:
    """SE-7: apply the new mobile number once its code is confirmed."""
    otp = verify_otp(user, OneTimePassword.Purpose.MOBILE_CHANGE, code)  # own transaction
    with transaction.atomic():
        before = snapshot(user)
        user.mobile_no = otp.destination
        user.save(update_fields=["mobile_no"])
        record_audit(user, "Mobile Changed", user, before, snapshot(user), request)
    return user


@transaction.atomic
def change_password(user: User, new_password: str, request=None) -> None:
    """Set a new password (validated by the caller) and end every session."""
    user.set_password(new_password)
    user.save(update_fields=["password"])
    ended = blacklist_all_refresh_tokens(user)
    record_audit(user, "Password Changed", user, after={"sessions_ended": ended}, request=request)


# ─── Driving licence (Book.Eligible.Licence, BR-2, BR-3; SE-10) ───────────


class LicenceError(Exception):
    """A licence submission or decision is not allowed; the message says why."""


def _store_as(upload, prefix: str):
    """Give an upload an unguessable object key (SI-3); keep its extension."""
    extension = upload.name.rsplit(".", 1)[-1].lower()
    upload.name = f"{prefix}-{uuid.uuid4().hex}.{extension}"
    return upload


@transaction.atomic
def submit_licence(customer: Customer, data: dict, request=None) -> Licence:
    """Submit or resubmit the customer's licence; it then awaits verification.

    BR-2: a licence must be valid, so one that has already expired is refused
    at submission. The images were validated by the serializer (D3).
    """
    today = timezone.localdate()
    if data["expiry_date"] < today:
        raise LicenceError("This licence has already expired.")
    if data["issue_date"] > today:
        raise LicenceError("The issue date cannot be in the future.")
    if data["issue_date"] >= data["expiry_date"]:
        raise LicenceError("The expiry date must be after the issue date.")
    number = data["licence_number"].strip().upper()
    taken = Licence.objects.filter(licence_number=number).exclude(customer=customer).exists()
    if taken:
        raise LicenceError("This licence number is already registered to another account.")

    licence, _ = Licence.objects.select_for_update().get_or_create(customer=customer)
    before = snapshot(licence)
    licence.licence_number = number
    licence.issuing_authority = data["issuing_authority"]
    licence.issue_date = data["issue_date"]
    licence.expiry_date = data["expiry_date"]
    licence.front_image = _store_as(data["front_image"], "front")
    licence.back_image = _store_as(data["back_image"], "back")
    licence.status = Licence.Status.PENDING_VERIFICATION
    licence.verified_by = None
    licence.verified_at = None
    licence.rejection_reason = ""
    licence.save()
    licence.categories.all().delete()
    LicenceCategory.objects.bulk_create(
        LicenceCategory(licence=licence, category=category) for category in data["categories"]
    )
    after = {**snapshot(licence), "categories": sorted(data["categories"])}
    record_audit(customer.user, "Licence Submitted", licence, before, after, request)
    return licence


def _decide(licence_id: int, actor: User, request, *, approve: bool, reason: str = ""):
    with transaction.atomic():
        licence = (
            Licence.objects.select_for_update().select_related("customer__user").get(pk=licence_id)
        )
        if licence.status != Licence.Status.PENDING_VERIFICATION:
            raise LicenceError("Only a licence pending verification can be approved or rejected.")
        before = snapshot(licence)
        licence.status = Licence.Status.VERIFIED if approve else Licence.Status.REJECTED
        licence.verified_by = actor
        licence.verified_at = timezone.now()
        licence.rejection_reason = "" if approve else reason
        licence.save(
            update_fields=["status", "verified_by", "verified_at", "rejection_reason", "updated_at"]
        )
        action = "Licence Verified" if approve else "Licence Rejected"
        record_audit(actor, action, licence, before, snapshot(licence), request)
        customer_user = licence.customer.user
        context = {"name": customer_user.name, "licence_number": licence.licence_number}
        if approve:
            queue_email(customer_user, "licence_approved", context)
        else:
            queue_email(customer_user, "licence_rejected", {**context, "reason": reason})
    return licence


def approve_licence(licence_id: int, actor: User, request=None) -> Licence:
    return _decide(licence_id, actor, request, approve=True)


def reject_licence(licence_id: int, actor: User, reason: str, request=None) -> Licence:
    reason = (reason or "").strip()
    if not reason:
        raise LicenceError("A reason is required to reject a licence.")
    return _decide(licence_id, actor, request, approve=False, reason=reason)
