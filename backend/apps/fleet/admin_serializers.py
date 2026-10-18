"""Fleet administration serializers (Module N3; SRS 3.7 Fleet.Add, Fleet.Retire).

Decimals travel as strings (CO-6); stored files only as signed links (SI-3).
Kept apart from the catalogue serializers (serializers.py, Rohan's).
"""

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.choices import FuelType
from apps.core.files import signed_file_url
from apps.core.validators import validate_image_upload

from .models import (
    Branch,
    BranchServiceableArea,
    Car,
    Vehicle,
    VehicleCategory,
    VehicleDocument,
    VehiclePhoto,
)
from .services.admin import concrete

# ─── Outputs ──────────────────────────────────────────────────────────────


def document_state(document: VehicleDocument, today=None) -> str:
    """Expired, Expiring (within DOCUMENT_EXPIRY_ALERT_WINDOW) or Valid."""
    today = today or timezone.localdate()
    if document.expiry_date < today:
        return "Expired"
    if document.expiry_date <= today + settings.DOCUMENT_EXPIRY_ALERT_WINDOW:
        return "Expiring"
    return "Valid"


def _current_documents(vehicle: Vehicle) -> dict[str, VehicleDocument]:
    """The latest document of each type (a renewal is a newer row)."""
    current: dict[str, VehicleDocument] = {}
    for document in vehicle.documents.all():
        held = current.get(document.document_type)
        if held is None or document.expiry_date > held.expiry_date:
            current[document.document_type] = document
    return current


class DocumentAlertSerializer(serializers.Serializer):
    document_type = serializers.CharField()
    state = serializers.ChoiceField(choices=["Missing", "Expired", "Expiring"])
    expiry_date = serializers.DateField(allow_null=True)


class AdminVehicleSerializer(serializers.ModelSerializer):
    """One row of the fleet display (Fleet.Status: every vehicle's current status)."""

    vehicle_type = serializers.CharField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    home_branch_name = serializers.CharField(source="home_branch.branch_name", read_only=True)
    transmission = serializers.SerializerMethodField()
    seating_capacity = serializers.SerializerMethodField()
    engine_cc = serializers.SerializerMethodField()
    photo_count = serializers.SerializerMethodField()
    document_alerts = serializers.SerializerMethodField(
        help_text="SA-3: statutory documents missing, expired or expiring soon."
    )

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "registration_no",
            "vehicle_type",
            "category",
            "category_name",
            "brand",
            "model",
            "year",
            "colour",
            "fuel_type",
            "transmission",
            "seating_capacity",
            "engine_cc",
            "chassis_number",
            "home_branch",
            "home_branch_name",
            "odometer",
            "fuel_capacity",
            "available_from",
            "status",
            "photo_count",
            "document_alerts",
        ]
        read_only_fields = fields

    def get_transmission(self, vehicle) -> str | None:
        return getattr(concrete(vehicle), "transmission", None)

    def get_seating_capacity(self, vehicle) -> int | None:
        return getattr(concrete(vehicle), "seating_capacity", None)

    def get_engine_cc(self, vehicle) -> int | None:
        return getattr(concrete(vehicle), "engine_cc", None)

    def get_photo_count(self, vehicle) -> int:
        return len(vehicle.photos.all())

    @extend_schema_field(DocumentAlertSerializer(many=True))
    def get_document_alerts(self, vehicle) -> list[dict]:
        current = _current_documents(vehicle)
        alerts = []
        for document_type in settings.HANDOVER_REQUIRED_DOCUMENTS:
            document = current.get(document_type)
            state = document_state(document) if document else "Missing"
            if state != "Valid":
                expiry = document.expiry_date if document else None
                alerts.append(
                    {"document_type": document_type, "state": state, "expiry_date": expiry}
                )
        return alerts


class AdminPhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = VehiclePhoto
        fields = ["id", "position", "url"]
        read_only_fields = fields

    def get_url(self, photo) -> str | None:
        return signed_file_url(photo.image, self.context.get("request"))


class AdminDocumentSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    current = serializers.SerializerMethodField(
        help_text="The latest document of its type; older rows are history."
    )
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = VehicleDocument
        fields = [
            "id",
            "document_type",
            "document_number",
            "valid_from",
            "expiry_date",
            "state",
            "current",
            "file_url",
        ]
        read_only_fields = fields

    def get_state(self, document) -> str:
        return document_state(document)

    def get_current(self, document) -> bool:
        current = self.context.get("current_documents", {})
        return current.get(document.document_type) == document

    def get_file_url(self, document) -> str | None:
        return signed_file_url(document.file, self.context.get("request"))


class AdminVehicleDetailSerializer(AdminVehicleSerializer):
    photos = AdminPhotoSerializer(many=True, read_only=True)
    documents = serializers.SerializerMethodField()

    class Meta(AdminVehicleSerializer.Meta):
        fields = [
            *AdminVehicleSerializer.Meta.fields,
            "last_service_date",
            "last_service_odometer",
            "photos",
            "documents",
        ]
        read_only_fields = fields

    @extend_schema_field(AdminDocumentSerializer(many=True))
    def get_documents(self, vehicle) -> list[dict]:
        documents = sorted(
            vehicle.documents.all(), key=lambda d: (d.document_type, -d.expiry_date.toordinal())
        )
        context = {**self.context, "current_documents": _current_documents(vehicle)}
        return AdminDocumentSerializer(documents, many=True, context=context).data


class AdminAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchServiceableArea
        fields = ["id", "pincode", "locality"]
        read_only_fields = ["id"]


class AdminBranchSerializer(serializers.ModelSerializer):
    serviceable_areas = AdminAreaSerializer(many=True, read_only=True)
    vehicle_count = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = ["branch_id", "branch_name", "address", "serviceable_areas", "vehicle_count"]
        read_only_fields = ["branch_id", "serviceable_areas", "vehicle_count"]

    def get_vehicle_count(self, branch) -> int:
        return branch.vehicles.count()


# ─── Inputs ───────────────────────────────────────────────────────────────


def _photo(upload):
    try:
        validate_image_upload(
            upload,
            extensions=settings.VEHICLE_PHOTO_EXTENSIONS,
            max_bytes=settings.VEHICLE_PHOTO_MAX_BYTES,
        )
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages) from exc
    return upload


class DocumentInputSerializer(serializers.Serializer):
    """A statutory document (Fleet.Add, SA-3); a renewal is a new one."""

    document_type = serializers.ChoiceField(choices=VehicleDocument.DocumentType.choices)
    document_number = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )
    valid_from = serializers.DateField(required=False, allow_null=True, default=None)
    expiry_date = serializers.DateField()


class DocumentUploadSerializer(DocumentInputSerializer):
    """The same, as multipart/form-data with an optional scan (SI-3)."""

    file = serializers.FileField(required=False, allow_null=True, validators=[_photo])


class _VehicleFields(serializers.Serializer):
    registration_no = serializers.CharField(max_length=16)
    category = serializers.PrimaryKeyRelatedField(queryset=VehicleCategory.objects.all())
    brand = serializers.CharField(max_length=64)
    model = serializers.CharField(max_length=64)
    year = serializers.IntegerField(min_value=1990, max_value=2100)  # the model's validators
    colour = serializers.CharField(max_length=32)
    fuel_type = serializers.ChoiceField(choices=FuelType.choices)
    transmission = serializers.ChoiceField(
        choices=Car.Transmission.choices, required=False, allow_null=True
    )
    seating_capacity = serializers.IntegerField(
        min_value=1, max_value=60, required=False, allow_null=True
    )
    engine_cc = serializers.IntegerField(
        min_value=1, max_value=5000, required=False, allow_null=True
    )
    chassis_number = serializers.CharField(max_length=32)
    home_branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    odometer = serializers.IntegerField(min_value=0, max_value=9_999_999)
    fuel_capacity = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Litres (petrol, diesel), kg (CNG) or kWh (electric): BR-12 needs it.",
    )
    available_from = serializers.DateField()


class VehicleCreateSerializer(_VehicleFields):
    """Fleet.Add as multipart/form-data: `photos` repeated (at least four images) and
    `documents` a JSON list of the four statutory documents with their expiry dates."""

    photos = serializers.ListField(child=serializers.FileField(validators=[_photo]))
    documents = serializers.JSONField()

    def validate_photos(self, value):
        if len(value) > 20:
            raise serializers.ValidationError("Send at most 20 photographs.")
        return value

    def validate_documents(self, value):
        if not isinstance(value, list) or len(value) > 12:
            raise serializers.ValidationError("Send a JSON list of at most 12 documents.")
        documents = DocumentInputSerializer(data=value, many=True)
        documents.is_valid(raise_exception=True)
        return [dict(item) for item in documents.validated_data]


class VehicleUpdateSerializer(_VehicleFields):
    """UC 11 "edit": any of the master data fields (send only those that change)."""


class RetireSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class PhotoUploadSerializer(serializers.Serializer):
    image = serializers.FileField(validators=[_photo])


class BranchInputSerializer(serializers.Serializer):
    branch_name = serializers.CharField(max_length=100)
    address = serializers.CharField(max_length=1000)


class AreaInputSerializer(serializers.Serializer):
    pincode = serializers.RegexField(
        r"^[0-9]{6}$", error_messages={"invalid": "A pincode is six digits."}
    )
    locality = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
