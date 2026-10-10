"""Accounts models.

The Exp 3 «interface» User is accounts.User (name, address, mobile_no,
email, password). Each implementing class (Customer, BranchStaff,
MaintenanceTechnician, Administrator) is a profile with a OneToOneField to
User; BranchManager extends Administrator (multi-table inheritance). Field
mappings and SRS additions are listed in docs/model-mapping.md.

Owner: Rohan (WBS 1.4.1). Only the owner edits this file or its migrations.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.choices import VehicleType
from apps.core.models import TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields) -> "User":
        if not email:
            raise ValueError("An e-mail address is required.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("role", User.Role.ADMINISTRATOR)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """A person who signs in to VRMS. Guests are never persisted."""

    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        BRANCH_STAFF = "BRANCH_STAFF", "Branch Staff"
        MAINTENANCE_TECHNICIAN = "MAINTENANCE_TECHNICIAN", "Maintenance Technician"
        ADMINISTRATOR = "ADMINISTRATOR", "Administrator"
        BRANCH_MANAGER = "BRANCH_MANAGER", "Branch Manager"

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    mobile_no = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.CUSTOMER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name", "mobile_no"]

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email


# ─── Profiles (Exp 3: classes implementing «interface» User) ──────────────


class Customer(TimeStampedModel):
    """Exp 3 Customer. A member of the public who books vehicles (SRS 2.2)."""

    customer_id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer"
    )
    date_of_birth = models.DateField()  # BR-2 minimum age
    is_blacklisted = models.BooleanField(default=False)  # BR-4
    # BR-4, Pay.Dues: amount not recovered from the deposit; blocks new bookings.
    outstanding_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # SA-4: an emergency contact is recorded for every customer.
    emergency_contact_name = models.CharField(max_length=150)
    emergency_contact_mobile = models.CharField(max_length=15)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(outstanding_due__gte=0), name="accounts_customer_due_not_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"Customer {self.customer_id}: {self.user}"


class MaintenanceTechnician(TimeStampedModel):
    """Exp 3 MaintenanceTechnician. Agency or contracted workshop (SRS 2.2)."""

    technician_id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="maintenance_technician"
    )
    workshop = models.CharField(max_length=150)

    def __str__(self) -> str:
        return f"Technician {self.technician_id}: {self.user}"


class Administrator(TimeStampedModel):
    """Exp 3 Administrator. admin_pass maps to User.password (one bcrypt hash, SE-2)."""

    admin_id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="administrator"
    )

    def __str__(self) -> str:
        return f"Administrator {self.admin_id}: {self.user}"


class BranchStaff(TimeStampedModel):
    """Exp 3 BranchStaff. branch_id maps to the branch foreign key."""

    staff_id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="branch_staff"
    )
    # Branch ◇ BranchStaff (Exp 3 aggregation): staff exist independently.
    branch = models.ForeignKey("fleet.Branch", on_delete=models.PROTECT, related_name="staff")

    class Meta:
        verbose_name_plural = "branch staff"

    def __str__(self) -> str:
        return f"Staff {self.staff_id}: {self.user}"


class BranchManager(Administrator):
    """Exp 3 BranchManager extends Administrator: limited to one branch (SRS 2.2)."""

    branch = models.ForeignKey("fleet.Branch", on_delete=models.PROTECT, related_name="managers")

    def __str__(self) -> str:
        return f"Branch manager {self.admin_id}: {self.user} ({self.branch})"


# ─── Licence (Customer ◆ Licence) ─────────────────────────────────────────


class Licence(TimeStampedModel):
    """Exp 3 Licence; Appendix A licence. Composition: owned by one Customer."""

    class Status(models.TextChoices):
        NOT_SUBMITTED = "Not Submitted", "Not Submitted"
        PENDING_VERIFICATION = "Pending Verification", "Pending Verification"
        VERIFIED = "Verified", "Verified"
        REJECTED = "Rejected", "Rejected"
        EXPIRED = "Expired", "Expired"

    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="licence")
    licence_number = models.CharField(max_length=32, blank=True)
    # Exp 3 Licence.category -> LicenceCategory rows (Appendix A: 1:m licence category).
    expiry_date = models.DateField(null=True, blank=True)  # BR-2: valid for the whole rental
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NOT_SUBMITTED)
    issuing_authority = models.CharField(max_length=150, blank=True)  # Appendix A
    issue_date = models.DateField(null=True, blank=True)  # Appendix A
    # Appendix A front/back image; SI-3: only the object key is stored.
    front_image = models.FileField(upload_to="licences/", blank=True)
    back_image = models.FileField(upload_to="licences/", blank=True)
    # Licence.verify(); SE-10 audits licence verification decisions. For a
    # rejection these record who rejected it and when.
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="licences_verified",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    # SE-10 licence verification decision: a rejection always states why.
    rejection_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["licence_number"],
                condition=~Q(licence_number=""),
                name="accounts_licence_number_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.licence_number or f"Licence of {self.customer}"


class LicenceCategory(models.Model):
    """One endorsed category of a licence (Appendix A: 1:m licence category; BR-3)."""

    licence = models.ForeignKey(Licence, on_delete=models.CASCADE, related_name="categories")
    category = models.CharField(max_length=16, choices=VehicleType.choices)

    class Meta:
        verbose_name_plural = "licence categories"
        constraints = [
            models.UniqueConstraint(
                fields=["licence", "category"], name="accounts_licencecategory_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.licence}: {self.category}"


# ─── One-time passwords (SE-7) ────────────────────────────────────────────


class OneTimePassword(models.Model):
    """SE-7: proves possession of a mobile number or e-mail address.

    Only a hash of the code is stored, never the code itself.
    """

    class Purpose(models.TextChoices):
        REGISTRATION = "Registration", "Registration"
        MOBILE_CHANGE = "Mobile Change", "Mobile Change"
        EMAIL_CHANGE = "Email Change", "Email Change"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="one_time_passwords"
    )
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    destination = models.CharField(max_length=254, help_text="Mobile number or e-mail address.")
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempt_count = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "-created_at"])]

    def __str__(self) -> str:
        return f"OTP {self.purpose} for {self.user} (expires {self.expires_at:%Y-%m-%d %H:%M})"
