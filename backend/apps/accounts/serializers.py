"""Accounts serializers: input validation only. Business rules live in services.py."""

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from rest_framework import serializers

from apps.core.choices import VehicleType
from apps.core.files import signed_file_url
from apps.core.validators import validate_image_upload

from .models import Licence, User

# Proposed (docs/decisions.md D20): 10-15 digits with an optional leading +.
mobile_validator = RegexValidator(
    r"^\+?[0-9]{10,15}$", "Enter a mobile number of 10 to 15 digits, optionally starting with +."
)


def otp_code_field() -> serializers.CharField:
    length = settings.OTP_CODE_LENGTH
    return serializers.RegexField(
        rf"^[0-9]{{{length}}}$",
        max_length=length,
        error_messages={"invalid": f"Enter the {length}-digit code."},
    )


def _check_password_rules(password: str, user: User) -> None:
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)}) from exc


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, style={"input_type": "password"}
    )
    name = serializers.CharField(max_length=150)
    mobile_no = serializers.CharField(max_length=15, validators=[mobile_validator])
    address = serializers.CharField()
    date_of_birth = serializers.DateField()
    emergency_contact_name = serializers.CharField(max_length=150)  # SA-4
    emergency_contact_mobile = serializers.CharField(max_length=15, validators=[mobile_validator])

    def validate_email(self, value: str) -> str:
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this e-mail address already exists.")
        return value

    def validate_date_of_birth(self, value):
        if value >= timezone.localdate():
            raise serializers.ValidationError("Enter a date of birth in the past.")
        return value

    def validate(self, attrs):
        candidate = User(email=attrs["email"], name=attrs["name"], mobile_no=attrs["mobile_no"])
        _check_password_rules(attrs["password"], candidate)
        return attrs


class RegisterResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    detail = serializers.CharField()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = otp_code_field()


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, style={"input_type": "password"}
    )


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "role"]


class AccessTokenSerializer(serializers.Serializer):
    """Sign-in and refresh response (D21): the refresh token is in the cookie only."""

    access = serializers.CharField()
    user = UserSummarySerializer()


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "mobile_no", "address", "role"]
        read_only_fields = fields


class ProfileUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    mobile_no = serializers.CharField(max_length=15, required=False, validators=[mobile_validator])
    address = serializers.CharField(required=False, allow_blank=True)


class ProfileUpdateResponseSerializer(ProfileSerializer):
    mobile_change_pending = serializers.BooleanField()

    class Meta(ProfileSerializer.Meta):
        fields = [*ProfileSerializer.Meta.fields, "mobile_change_pending"]
        read_only_fields = fields


class OTPCodeSerializer(serializers.Serializer):
    code = otp_code_field()


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value: str) -> str:
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("The current password is incorrect.")
        return value

    def validate(self, attrs):
        _check_password_rules(attrs["new_password"], self.context["request"].user)
        return attrs


# ─── Driving licence ──────────────────────────────────────────────────────


def _licence_image_field() -> serializers.FileField:
    return serializers.FileField(
        write_only=True,
        help_text="JPG or PNG image, at most 5 MB (Appendix A front/back image).",
    )


class LicenceSubmitSerializer(serializers.Serializer):
    """Appendix A licence: number, authority, 1:m category, dates, both images."""

    licence_number = serializers.CharField(max_length=32)
    issuing_authority = serializers.CharField(max_length=150)
    issue_date = serializers.DateField()
    expiry_date = serializers.DateField()
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=VehicleType.choices), min_length=1, max_length=2
    )
    front_image = _licence_image_field()
    back_image = _licence_image_field()

    def validate_categories(self, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise serializers.ValidationError("List each category once.")
        return value

    def _validate_image(self, value):
        try:
            validate_image_upload(
                value,
                extensions=settings.LICENCE_IMAGE_EXTENSIONS,
                max_bytes=settings.LICENCE_IMAGE_MAX_BYTES,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate_front_image(self, value):
        return self._validate_image(value)

    def validate_back_image(self, value):
        return self._validate_image(value)


class LicenceSerializer(serializers.ModelSerializer):
    """A licence as its owner, branch staff and administrators see it."""

    categories = serializers.SerializerMethodField()
    front_image_url = serializers.SerializerMethodField()
    back_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Licence
        fields = [
            "id",
            "licence_number",
            "issuing_authority",
            "issue_date",
            "expiry_date",
            "categories",
            "status",
            "rejection_reason",
            "verified_at",
            "front_image_url",
            "back_image_url",
            "updated_at",
        ]
        read_only_fields = fields

    def get_categories(self, licence) -> list[str]:
        return sorted(category.category for category in licence.categories.all())

    def get_front_image_url(self, licence) -> str | None:
        return signed_file_url(licence.front_image, self.context.get("request"))

    def get_back_image_url(self, licence) -> str | None:
        return signed_file_url(licence.back_image, self.context.get("request"))


class LicenceCustomerSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(source="pk")
    name = serializers.CharField(source="user.name")
    email = serializers.EmailField(source="user.email")
    mobile_no = serializers.CharField(source="user.mobile_no")
    date_of_birth = serializers.DateField()


class LicenceReviewSerializer(LicenceSerializer):
    """For verification: the licence plus the customer it belongs to (BR-2)."""

    customer = LicenceCustomerSerializer(read_only=True)

    class Meta(LicenceSerializer.Meta):
        fields = [*LicenceSerializer.Meta.fields, "customer"]
        read_only_fields = fields


class LicenceRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False, max_length=1000)
