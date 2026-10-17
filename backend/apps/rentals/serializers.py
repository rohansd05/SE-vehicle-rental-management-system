"""Rentals API serializers (Handover Vehicle, SRS 3.3; Exp 2 use case 7)."""

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Licence
from apps.bookings.models import Booking
from apps.bookings.serializers import BookingVehicleSerializer
from apps.core.files import signed_file_url
from apps.core.validators import validate_image_upload
from apps.pricing.serializers import QuoteTermsSerializer
from apps.pricing.services import quote_terms

from . import services
from .models import ConditionReport

# ─── Output ───────────────────────────────────────────────────────────────


class BranchBookingSerializer(serializers.ModelSerializer):
    """One collection in the branch list (Book.Done.Store: staff never see the pickup code)."""

    vehicle = BookingVehicleSerializer(read_only=True)
    customer_name = serializers.CharField(source="customer.user.name", read_only=True)
    customer_mobile = serializers.CharField(source="customer.user.mobile_no", read_only=True)
    pickup_branch = serializers.CharField(source="pickup_branch.branch_name", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "booking_reference",
            "status",
            "pickup_datetime",
            "return_datetime",
            "pickup_branch",
            "customer_name",
            "customer_mobile",
            "vehicle",
        ]
        read_only_fields = fields


class RefusalSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()


class AccessorySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class DamageMarkSerializer(serializers.Serializer):
    """A mark on the vehicle diagram: x and y in percent of its width and height."""

    x = serializers.IntegerField(min_value=0, max_value=100)
    y = serializers.IntegerField(min_value=0, max_value=100)
    note = serializers.CharField(max_length=200, allow_blank=True, required=False, default="")


class HandoverLicenceSerializer(serializers.ModelSerializer):
    categories = serializers.SerializerMethodField()

    class Meta:
        model = Licence
        fields = ["licence_number", "status", "expiry_date", "categories"]
        read_only_fields = fields

    def get_categories(self, licence) -> list[str]:
        return sorted(category.category for category in licence.categories.all())


class HandoverVehicleSerializer(BookingVehicleSerializer):
    class Meta(BookingVehicleSerializer.Meta):
        fields = [*BookingVehicleSerializer.Meta.fields, "status", "odometer"]
        read_only_fields = fields


class ConditionPhotoOutSerializer(serializers.Serializer):
    caption = serializers.CharField()
    url = serializers.SerializerMethodField()

    def get_url(self, photo) -> str | None:
        return signed_file_url(photo.image, self.context.get("request"))


class ConditionReportSerializer(serializers.ModelSerializer):
    """The signed report (Handover.Sign), with signed, expiring links (SI-3)."""

    accessories = AccessorySerializer(many=True, read_only=True)
    damage_marks = DamageMarkSerializer(many=True, read_only=True)
    photos = ConditionPhotoOutSerializer(many=True, read_only=True)
    signature_url = serializers.SerializerMethodField()
    recorded_by = serializers.CharField(source="recorded_by.user.name", read_only=True)

    class Meta:
        model = ConditionReport
        fields = [
            "report_type",
            "odometer_reading",
            "fuel_level",
            "accessories",
            "damage_marks",
            "photos",
            "signature_url",
            "signed_at",
            "recorded_by",
            "recorded_at",
        ]
        read_only_fields = fields

    def get_signature_url(self, report) -> str | None:
        return signed_file_url(report.signature, self.context.get("request"))


class HandoverDetailSerializer(BranchBookingSerializer):
    """UC 7 steps 1 and 2: the booking, the verified licence and the handover checklist."""

    vehicle = HandoverVehicleSerializer(read_only=True)
    licence = serializers.SerializerMethodField()
    refusals = serializers.SerializerMethodField()
    can_hand_over = serializers.SerializerMethodField()
    accessories = serializers.SerializerMethodField()
    photo_sides = serializers.SerializerMethodField()
    terms = serializers.SerializerMethodField()
    report = serializers.SerializerMethodField()

    class Meta(BranchBookingSerializer.Meta):
        fields = [
            *BranchBookingSerializer.Meta.fields,
            "handed_over_at",
            "licence",
            "refusals",
            "can_hand_over",
            "accessories",
            "photo_sides",
            "terms",
            "report",
        ]
        read_only_fields = fields

    def _refusals(self, booking) -> list:
        if not hasattr(self, "_cached_refusals"):
            self._cached_refusals = services.handover_refusals(booking)
        return self._cached_refusals

    @extend_schema_field(HandoverLicenceSerializer(allow_null=True))
    def get_licence(self, booking):
        licence = Licence.objects.filter(customer_id=booking.customer_id).first()
        return HandoverLicenceSerializer(licence).data if licence else None

    @extend_schema_field(RefusalSerializer(many=True))
    def get_refusals(self, booking):
        return [{"code": r.code, "message": r.message} for r in self._refusals(booking)]

    def get_can_hand_over(self, booking) -> bool:
        return not self._refusals(booking)

    @extend_schema_field(AccessorySerializer(many=True))
    def get_accessories(self, booking):
        return services.expected_accessories(booking)

    def get_photo_sides(self, booking) -> list[str]:
        return list(settings.HANDOVER_PHOTO_SIDES)

    @extend_schema_field(QuoteTermsSerializer)
    def get_terms(self, booking):
        """Handover.Sign: the rental agreement presented with the report."""
        return QuoteTermsSerializer(quote_terms(booking.tariff)).data

    @extend_schema_field(ConditionReportSerializer(allow_null=True))
    def get_report(self, booking):
        report = (
            booking.condition_reports.filter(report_type=ConditionReport.ReportType.HANDOVER)
            .select_related("recorded_by__user")
            .prefetch_related("photos")
            .first()
        )
        return ConditionReportSerializer(report, context=self.context).data if report else None


class HandoverRefusedSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()
    refusals = RefusalSerializer(many=True)


# ─── Input ────────────────────────────────────────────────────────────────


def _image(upload):
    try:
        validate_image_upload(
            upload,
            extensions=settings.CONDITION_IMAGE_EXTENSIONS,
            max_bytes=settings.CONDITION_IMAGE_MAX_BYTES,
        )
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages) from exc
    return upload


class HandoverSerializer(serializers.Serializer):
    """Handover.Checklist and Handover.Sign, sent as multipart/form-data.

    `accessories` and `damage_marks` are JSON arrays in their form fields.
    One photo of each side is required (photo_front, photo_rear, photo_left,
    photo_right: the four sides of HANDOVER_PHOTO_SIDES); extra_photos are
    optional. `signature` is the customer's signature drawn on the branch
    device, as a PNG.
    """

    odometer_reading = serializers.IntegerField(min_value=0)
    fuel_level = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100
    )
    accessories = serializers.JSONField(required=False, default=list)
    damage_marks = serializers.JSONField(required=False, default=list)
    photo_front = serializers.FileField(validators=[_image])
    photo_rear = serializers.FileField(validators=[_image])
    photo_left = serializers.FileField(validators=[_image])
    photo_right = serializers.FileField(validators=[_image])
    extra_photos = serializers.ListField(
        child=serializers.FileField(validators=[_image]), required=False, default=list
    )
    signature = serializers.FileField(validators=[_image])

    def _list(self, value, item_serializer, limit: int):
        if not isinstance(value, list):
            raise serializers.ValidationError("Send a JSON list.")
        if len(value) > limit:
            raise serializers.ValidationError(f"Send at most {limit} items.")
        items = item_serializer(data=value, many=True)
        items.is_valid(raise_exception=True)
        return [dict(item) for item in items.validated_data]

    def validate_accessories(self, value):
        return self._list(value, AccessorySerializer, 30)

    def validate_damage_marks(self, value):
        return self._list(value, DamageMarkSerializer, 50)

    def validate_extra_photos(self, value):
        if len(value) > 12:
            raise serializers.ValidationError("Send at most 12 extra photos.")
        return value

    def to_checklist(self) -> dict:
        """The keyword arguments of services.capture_report()."""
        data = self.validated_data
        sides = [(side, data[f"photo_{side.lower()}"]) for side in settings.HANDOVER_PHOTO_SIDES]
        extras = [("Extra", photo) for photo in data["extra_photos"]]
        return {
            "odometer_reading": data["odometer_reading"],
            "fuel_level": data["fuel_level"],
            "accessories": data["accessories"],
            "damage_marks": data["damage_marks"],
            "photos": sides + extras,
            "signature": data["signature"],
        }
