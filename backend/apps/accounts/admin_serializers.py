"""Staff accounts and blacklist serializers (Module N3; Fleet.Users, BR-4, UC 12).

Passwords are write-only and never returned (SE-2). Kept apart from the
sign-in serializers (serializers.py, Rohan's).
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.fleet.models import Branch

from .admin_services import STAFF_ROLES, open_bookings, profile_of
from .models import Customer, User
from .serializers import mobile_validator

STAFF_ROLE_CHOICES = [(role, User.Role(role).label) for role in STAFF_ROLES]


class StaffAccountSerializer(serializers.ModelSerializer):
    """A staff account with its branch (or workshop) and, for a technician, BR-16."""

    branch = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    workshop = serializers.SerializerMethodField()
    technician_id = serializers.SerializerMethodField()
    authorised_to_clear_unsafe = serializers.SerializerMethodField(help_text="BR-16")

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "mobile_no",
            "address",
            "role",
            "is_active",
            "date_joined",
            "last_login",
            "branch",
            "branch_name",
            "workshop",
            "technician_id",
            "authorised_to_clear_unsafe",
        ]
        read_only_fields = fields

    def get_branch(self, user) -> int | None:
        return getattr(profile_of(user), "branch_id", None)

    def get_branch_name(self, user) -> str | None:
        branch = getattr(profile_of(user), "branch", None)
        return branch.branch_name if branch else None

    def get_workshop(self, user) -> str | None:
        return getattr(profile_of(user), "workshop", None)

    def get_technician_id(self, user) -> int | None:
        return getattr(profile_of(user), "technician_id", None)

    def get_authorised_to_clear_unsafe(self, user) -> bool:
        profile = profile_of(user)
        return user.role == User.Role.MAINTENANCE_TECHNICIAN and hasattr(
            profile, "unsafe_clearance_authorisation"
        )


class StaffCreateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=STAFF_ROLE_CHOICES)
    email = serializers.EmailField(max_length=254)
    name = serializers.CharField(max_length=150)
    mobile_no = serializers.CharField(max_length=15, validators=[mobile_validator])
    address = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True, default=None
    )
    workshop = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")


class StaffUpdateSerializer(serializers.Serializer):
    """Send only what changes. The role never changes."""

    email = serializers.EmailField(max_length=254, required=False)
    name = serializers.CharField(max_length=150, required=False)
    mobile_no = serializers.CharField(max_length=15, validators=[mobile_validator], required=False)
    address = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False)
    workshop = serializers.CharField(max_length=150, required=False, allow_blank=True)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class AdminCustomerSerializer(serializers.ModelSerializer):
    """A customer, with the latest blacklisting (BR-4) taken from the audit log."""

    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    mobile_no = serializers.CharField(source="user.mobile_no", read_only=True)
    blacklist_reason = serializers.SerializerMethodField()
    blacklisted_at = serializers.SerializerMethodField()
    blacklisted_by = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "customer_id",
            "name",
            "email",
            "mobile_no",
            "is_blacklisted",
            "outstanding_due",
            "blacklist_reason",
            "blacklisted_at",
            "blacklisted_by",
        ]
        read_only_fields = fields

    def _latest(self, customer, name):
        return getattr(customer, name, None) if customer.is_blacklisted else None

    def get_blacklist_reason(self, customer) -> str | None:
        return self._latest(customer, "blacklist_reason")

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_blacklisted_at(self, customer):
        value = self._latest(customer, "blacklisted_at")
        return serializers.DateTimeField().to_representation(value) if value else None

    def get_blacklisted_by(self, customer) -> str | None:
        return self._latest(customer, "blacklisted_by")


class OpenBookingSerializer(serializers.Serializer):
    """UC 12 extension 2a: a Confirmed booking to decide on, or an Active one (return pending)."""

    id = serializers.IntegerField()
    booking_reference = serializers.CharField()
    status = serializers.CharField()
    registration_no = serializers.CharField(source="vehicle.registration_no")
    vehicle = serializers.SerializerMethodField()
    pickup_branch = serializers.CharField(source="pickup_branch.branch_name")
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    return_pending = serializers.SerializerMethodField(
        help_text="Active: the vehicle is out; it is returned as usual, never cancelled here."
    )

    def get_vehicle(self, booking) -> str:
        return f"{booking.vehicle.brand} {booking.vehicle.model}"

    def get_return_pending(self, booking) -> bool:
        return booking.status == "Active"


class AdminCustomerDetailSerializer(AdminCustomerSerializer):
    open_bookings = serializers.SerializerMethodField()

    class Meta(AdminCustomerSerializer.Meta):
        fields = [*AdminCustomerSerializer.Meta.fields, "open_bookings"]
        read_only_fields = fields

    @extend_schema_field(OpenBookingSerializer(many=True))
    def get_open_bookings(self, customer) -> list[dict]:
        return OpenBookingSerializer(open_bookings(customer), many=True).data
