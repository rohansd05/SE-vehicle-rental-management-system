"""Rentals API serializers (SRS 3.3: Handover Vehicle, Exp 2 use case 7; Return Vehicle, 8)."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Licence
from apps.bookings.models import Booking
from apps.bookings.serializers import BookingVehicleSerializer
from apps.core.files import signed_file_url
from apps.core.validators import validate_image_upload
from apps.maintenance.models import MaintenanceJob
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


def _json_list(value, item_serializer, limit: int) -> list[dict]:
    """A JSON list in a form field (or a JSON body), each item checked by `item_serializer`."""
    if not isinstance(value, list):
        raise serializers.ValidationError("Send a JSON list.")
    if len(value) > limit:
        raise serializers.ValidationError(f"Send at most {limit} items.")
    items = item_serializer(data=value, many=True)
    items.is_valid(raise_exception=True)
    return [dict(item) for item in items.validated_data]


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

    def validate_accessories(self, value):
        return _json_list(value, AccessorySerializer, 30)

    def validate_damage_marks(self, value):
        return _json_list(value, DamageMarkSerializer, 50)

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


# ═══ Module N2: Return Vehicle (SRS 3.3 Return.*; Exp 2 use case 8) ═════

MONEY = {"max_digits": 12, "decimal_places": 2}


class ReturnChargeSerializer(serializers.Serializer):
    """Return.Charges: one separate item of the settlement."""

    kind = serializers.ChoiceField(
        choices=["late_return", "excess_km", "fuel_shortfall", "accessory", "damage", "tax"]
    )
    description = serializers.CharField()
    amount = serializers.DecimalField(**MONEY)
    justification = serializers.CharField(allow_blank=True)


class PaidChargeSerializer(serializers.Serializer):
    """A rental charge paid before the return (Pay.Ledger), e.g. an extension (Book.Extend)."""

    description = serializers.CharField(source="note")
    amount = serializers.DecimalField(**MONEY)


class SettlementFiguresSerializer(serializers.Serializer):
    """Return.Settle: the charges against the deposit, its refund (BR-14) and any due."""

    lines = ReturnChargeSerializer(many=True)
    total = serializers.DecimalField(**MONEY)
    deposit = serializers.DecimalField(**MONEY)
    deposit_used = serializers.DecimalField(**MONEY)
    refund = serializers.DecimalField(**MONEY)
    due = serializers.DecimalField(**MONEY)


class ReturnQuoteSerializer(SettlementFiguresSerializer):
    """UC 8 step 3: the itemised settlement for the customer to acknowledge."""

    distance = serializers.IntegerField()
    free_km = serializers.IntegerField()
    accessories_returned = AccessorySerializer(many=True)
    override_required = serializers.BooleanField()  # Return.Odometer
    plausibility_limit_km = serializers.IntegerField()

    @classmethod
    def of(cls, quote: services.ReturnQuote) -> dict:
        settlement = quote.settlement
        return cls(
            {
                "lines": [vars(line) for line in settlement.lines],
                "total": settlement.total,
                "deposit": settlement.deposit,
                "deposit_used": settlement.deposit_used,
                "refund": settlement.refund,
                "due": settlement.due,
                "distance": settlement.distance,
                "free_km": settlement.free_km,
                "accessories_returned": quote.accessories_returned,
                "override_required": quote.override_required,
                "plausibility_limit_km": quote.plausibility_limit,
            }
        ).data


class SettlementRecordSerializer(SettlementFiguresSerializer):
    """Return.Complete: the signed settlement and where its money went."""

    refund_status = serializers.CharField(allow_blank=True)  # RefundRequest.Status (UC 13)
    refund_paid_out_by = serializers.CharField(allow_blank=True)  # a cash refund (Pay.Refund)
    maintenance_job = serializers.IntegerField(allow_null=True)  # Return.Flag


class ReturnVehicleSerializer(HandoverVehicleSerializer):
    class Meta(HandoverVehicleSerializer.Meta):
        fields = [*HandoverVehicleSerializer.Meta.fields, "fuel_type", "fuel_capacity"]
        read_only_fields = fields


class ReturnDetailSerializer(BranchBookingSerializer):
    """UC 8 step 1: the booking, its handover report (Return.Checklist: the photos are shown
    side by side), what is already paid and, once returned, the signed settlement."""

    vehicle = ReturnVehicleSerializer(read_only=True)
    refusals = serializers.SerializerMethodField()
    can_return = serializers.SerializerMethodField()
    photo_sides = serializers.SerializerMethodField()
    terms = serializers.SerializerMethodField()
    handover_report = serializers.SerializerMethodField()
    return_report = serializers.SerializerMethodField()
    rental_paid = serializers.SerializerMethodField()
    deposit_method = serializers.SerializerMethodField()
    settlement = serializers.SerializerMethodField()

    class Meta(BranchBookingSerializer.Meta):
        fields = [
            *BranchBookingSerializer.Meta.fields,
            "handed_over_at",
            "returned_at",
            "distance_travelled",
            "total_amount",
            "security_deposit",
            "refusals",
            "can_return",
            "photo_sides",
            "terms",
            "handover_report",
            "return_report",
            "rental_paid",
            "deposit_method",
            "settlement",
        ]
        read_only_fields = fields

    def _report(self, booking, report_type):
        if getattr(self, "_reports_of", None) != booking.pk:
            self._reports_of = booking.pk
            reports = booking.condition_reports.select_related("recorded_by__user")
            self._reports = {r.report_type: r for r in reports.prefetch_related("photos")}
        return self._reports.get(report_type)

    @extend_schema_field(RefusalSerializer(many=True))
    def get_refusals(self, booking):
        return [{"code": r.code, "message": r.message} for r in services.return_refusals(booking)]

    def get_can_return(self, booking) -> bool:
        return not services.return_refusals(booking)

    def get_photo_sides(self, booking) -> list[str]:
        return list(settings.HANDOVER_PHOTO_SIDES)

    @extend_schema_field(QuoteTermsSerializer)
    def get_terms(self, booking):
        """BR-10 to BR-12 as the customer accepted them (Book.Quote.Terms)."""
        return QuoteTermsSerializer(quote_terms(booking.tariff)).data

    @extend_schema_field(ConditionReportSerializer(allow_null=True))
    def get_handover_report(self, booking):
        report = self._report(booking, ConditionReport.ReportType.HANDOVER)
        return ConditionReportSerializer(report, context=self.context).data if report else None

    @extend_schema_field(ConditionReportSerializer(allow_null=True))
    def get_return_report(self, booking):
        report = self._report(booking, ConditionReport.ReportType.RETURN)
        return ConditionReportSerializer(report, context=self.context).data if report else None

    @extend_schema_field(PaidChargeSerializer(many=True))
    def get_rental_paid(self, booking):
        return PaidChargeSerializer(services.rental_paid(booking), many=True).data

    def get_deposit_method(self, booking) -> str | None:
        """Pay.Refund: a cash deposit is refunded in cash by the staff member who settles."""
        deposit = services.deposit_payment(booking)
        return deposit.method if deposit else None

    @extend_schema_field(SettlementRecordSerializer(allow_null=True))
    def get_settlement(self, booking):
        report = self._report(booking, ConditionReport.ReportType.RETURN)
        if report is None:
            return None
        return SettlementRecordSerializer(services.settlement_record(booking, report)).data


class ReturnRefusedSerializer(HandoverRefusedSerializer):
    pass


class MissingAccessorySerializer(AccessorySerializer):
    """An accessory issued at handover and not returned, at the cost the staff enter."""

    cost = serializers.DecimalField(**MONEY, min_value=Decimal("0.00"))


class DamageChargeSerializer(serializers.Serializer):
    """Return.Charges: "any damage charge entered by the staff member with a justification"."""

    description = serializers.CharField(max_length=150)
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    justification = serializers.CharField(max_length=500)


class ReturnReadingsSerializer(serializers.Serializer):
    """Return.Checklist readings and the staff's charges: a JSON body for a quote, form
    fields (the lists as JSON) when the return is completed."""

    odometer_reading = serializers.IntegerField(min_value=0)
    fuel_level = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100
    )
    returned_at = serializers.DateTimeField()  # "the actual return time"
    missing_accessories = serializers.JSONField(required=False, default=list)
    damage_charges = serializers.JSONField(required=False, default=list)

    def validate_missing_accessories(self, value):
        return _json_list(value, MissingAccessorySerializer, 30)

    def validate_damage_charges(self, value):
        return _json_list(value, DamageChargeSerializer, 20)

    def to_readings(self) -> services.ReturnReadings:
        data = self.validated_data
        return services.ReturnReadings(
            odometer_reading=data["odometer_reading"],
            fuel_level=data["fuel_level"],
            returned_at=data["returned_at"],
            missing_accessories=data["missing_accessories"],
            damage_charges=data["damage_charges"],
        )


class ReturnSerializer(ReturnReadingsSerializer, HandoverSerializer):
    """Return.Checklist, Return.Settle, Return.Flag and Return.Odometer, as multipart/form-data.

    The readings and charges as for a quote; one photo of each side (photo_front,
    photo_rear, photo_left, photo_right) and optional extra_photos; damage_marks
    (new damage, a JSON list); `signature`, the customer's acknowledgement of the
    settlement (Exp 5); `expected_total`, the total they acknowledged. To flag the
    vehicle (Return.Flag): flag_problem, flag_severity and flag_unfit. Above the
    plausibility limit (Return.Odometer): override_email and override_password of a
    Branch Manager of the branch or an Administrator, and override_reason.
    """

    accessories = None  # derived: those issued at handover less missing_accessories
    expected_total = serializers.DecimalField(**MONEY)
    flag_problem = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, default=""
    )
    flag_severity = serializers.ChoiceField(choices=MaintenanceJob.Severity.choices, required=False)
    flag_unfit = serializers.BooleanField(required=False)
    override_email = serializers.EmailField(required=False, allow_blank=True, default="")
    override_password = serializers.CharField(
        required=False, allow_blank=True, default="", write_only=True, trim_whitespace=False
    )
    override_reason = serializers.CharField(
        required=False, allow_blank=True, max_length=500, default=""
    )

    def validate(self, data):
        if data["flag_problem"].strip():
            errors = {}
            if not data.get("flag_severity"):
                errors["flag_severity"] = ["Choose the severity of the problem."]
            if "flag_unfit" not in self.initial_data:
                errors["flag_unfit"] = ["Say whether the vehicle is fit for use."]
            if errors:
                raise serializers.ValidationError(errors)
        return data

    def to_return(self) -> dict:
        """The keyword arguments of services.return_vehicle()."""
        data = self.validated_data
        sides = [(side, data[f"photo_{side.lower()}"]) for side in settings.HANDOVER_PHOTO_SIDES]
        flag = None
        if data["flag_problem"].strip():
            flag = services.Flag(data["flag_problem"], data["flag_severity"], data["flag_unfit"])
        return {
            "readings": self.to_readings(),
            "expected_total": data["expected_total"],
            "damage_marks": data["damage_marks"],
            "photos": sides + [("Extra", photo) for photo in data["extra_photos"]],
            "signature": data["signature"],
            "flag": flag,
            "override": {
                "email": data["override_email"],
                "password": data["override_password"],
                "reason": data["override_reason"],
            },
        }
