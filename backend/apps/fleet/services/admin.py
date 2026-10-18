"""Fleet administration (SRS 3.7 Fleet.Add, Fleet.Status, Fleet.Retire, Fleet.Audit;
Exp 2 use case 11 "Manage Fleet and Tariffs"; Exp 3 Administrator.manage_fleet()).

Vehicles with their photographs and statutory documents, and branches with
their serviceable areas. Every write is audited (Fleet.Audit, SE-10); a
vehicle's status changes only through fleet/services/status.py, so retiring
is the state machine's Retired transition (no future booking may exist).

Module N3 (Nidhi). Kept apart from the catalogue and search code (Rohan's) in
this file, its admin_serializers.py and admin_views.py.
"""

import uuid

from django.conf import settings
from django.db import transaction

from apps.core.audit import record_audit, snapshot
from apps.core.choices import VehicleType
from apps.fleet.models import (
    Branch,
    BranchServiceableArea,
    Car,
    TwoWheeler,
    Vehicle,
    VehicleDocument,
    VehiclePhoto,
)

from .status import update_status

COMMON_FIELDS = (
    "registration_no",
    "brand",
    "model",
    "category",
    "home_branch",
    "year",
    "colour",
    "fuel_type",
    "chassis_number",
    "available_from",
    "odometer",
    "fuel_capacity",
)
TYPE_FIELDS = {
    VehicleType.CAR: (Car, ("seating_capacity", "transmission")),
    VehicleType.TWO_WHEELER: (TwoWheeler, ("engine_cc",)),
}
LABELS = {
    "seating_capacity": "seating capacity",
    "transmission": "transmission",
    "engine_cc": "engine capacity",
}


class FleetAdminError(Exception):
    """The change is refused; `field` names the input at fault, if one is."""

    def __init__(self, message: str, *, field: str | None = None):
        self.field = field
        super().__init__(message)


def _audit(actor, action: str, obj, before, after, request) -> None:
    record_audit(actor, action, obj, before, after, request)


def _key(upload, prefix: str):
    """An unguessable object key with the upload's extension (SI-3)."""
    extension = upload.name.rsplit(".", 1)[-1].lower()
    upload.name = f"{prefix}-{uuid.uuid4().hex}.{extension}"
    return upload


def concrete(vehicle: Vehicle) -> Car | TwoWheeler | Vehicle:
    """The Car or TwoWheeler row of a vehicle (Exp 3 generalisation)."""
    return getattr(vehicle, "car", None) or getattr(vehicle, "twowheeler", None) or vehicle


def _normalised(data: dict) -> dict:
    data = dict(data)
    if "registration_no" in data:
        data["registration_no"] = "".join(data["registration_no"].split()).upper()
    if "chassis_number" in data:
        data["chassis_number"] = "".join(data["chassis_number"].split()).upper()
    return data


def _check_unique(data: dict, exclude_pk: int | None = None) -> None:
    """UC 11 extension 1a: an existing registration or chassis number is rejected."""
    others = Vehicle.objects.exclude(pk=exclude_pk)
    if (
        "registration_no" in data
        and others.filter(registration_no__iexact=data["registration_no"]).exists()
    ):
        raise FleetAdminError(
            "A vehicle with this registration number already exists.", field="registration_no"
        )
    if (
        "chassis_number" in data
        and others.filter(chassis_number__iexact=data["chassis_number"]).exists()
    ):
        raise FleetAdminError(
            "A vehicle with this chassis number already exists.", field="chassis_number"
        )


def _check_capacity(data: dict) -> None:
    """BR-12 (N2-P3): the tank, gas or battery capacity turns a fuel shortfall into a quantity."""
    if "fuel_capacity" in data and (data["fuel_capacity"] is None or data["fuel_capacity"] <= 0):
        raise FleetAdminError(
            "Enter the tank capacity (or the battery capacity of an electric vehicle).",
            field="fuel_capacity",
        )


# ─── Vehicles ─────────────────────────────────────────────────────────────


@transaction.atomic
def create_vehicle(
    actor, data: dict, *, photos: list, documents: list[dict], request=None
) -> Vehicle:
    """Fleet.Add (UC 11 step 1): the master data, at least four photographs and the
    expiry date of each statutory document. The vehicle is Available, so bookable
    from its availability date."""
    data = _normalised(data)
    vehicle_type = data["category"].vehicle_type
    model, type_fields = TYPE_FIELDS[vehicle_type]
    for name in type_fields:
        if data.get(name) in (None, ""):
            raise FleetAdminError(f"Enter the {LABELS[name]}.", field=name)
    _check_unique(data)
    _check_capacity({"fuel_capacity": data.get("fuel_capacity")})
    if len(photos) < settings.VEHICLE_PHOTOS_MINIMUM:
        raise FleetAdminError(
            f"Add at least {settings.VEHICLE_PHOTOS_MINIMUM} photographs (Fleet.Add).",
            field="photos",
        )
    given = {document["document_type"] for document in documents}
    missing = [name for name in settings.HANDOVER_REQUIRED_DOCUMENTS if name not in given]
    if missing:
        raise FleetAdminError(
            "Enter the expiry date of each statutory document (Fleet.Add); missing: "
            + ", ".join(missing)
            + ".",
            field="documents",
        )
    vehicle = model.objects.create(
        **{name: data[name] for name in COMMON_FIELDS},
        **{name: data[name] for name in type_fields},
        status=Vehicle.Status.AVAILABLE,
    )
    _audit(actor, "Create", vehicle, None, snapshot(vehicle), request)
    for upload in photos:
        add_photo(vehicle, upload, actor, request=request)
    for document in documents:
        add_document(vehicle, document, actor, request=request)
    return vehicle


@transaction.atomic
def update_vehicle(vehicle: Vehicle, actor, data: dict, request=None) -> Vehicle:
    """UC 11 step 1 "edits": the master data. The status is not edited here (Fleet.Status:
    only the state machine moves it) and the type stays (retire and add instead)."""
    row = concrete(Vehicle.objects.select_for_update().get(pk=vehicle.pk))
    data = _normalised(data)
    vehicle_type = row.category.vehicle_type
    if "category" in data and data["category"].vehicle_type != vehicle_type:
        raise FleetAdminError(
            f"Choose a {vehicle_type.lower()} category; a vehicle's type cannot change.",
            field="category",
        )
    if "odometer" in data and data["odometer"] < row.odometer:
        # Appendix A: an odometer reading may never decrease.
        raise FleetAdminError(
            f"The odometer cannot go below its current {row.odometer} km.", field="odometer"
        )
    _check_unique(data, exclude_pk=row.pk)
    _check_capacity(data)
    _, type_fields = TYPE_FIELDS[vehicle_type]
    editable = (*COMMON_FIELDS, *type_fields)
    before = snapshot(row)
    for name, value in data.items():
        if name in editable:
            setattr(row, name, value)
    row.save()
    _audit(actor, "Update", row, before, snapshot(row), request)
    return row


def retire_vehicle(vehicle: Vehicle, actor, reason: str, request=None) -> Vehicle:
    """Fleet.Retire through the vehicle state machine: Administrator only, and refused
    while a future booking exists (VehicleStatusError). History is kept."""
    if not reason.strip():
        raise FleetAdminError("Give the reason for retiring the vehicle.", field="reason")
    return update_status(
        vehicle, Vehicle.Status.RETIRED, actor=actor, reason=reason.strip(), request=request
    )


def add_photo(vehicle: Vehicle, upload, actor, request=None) -> VehiclePhoto:
    """Fleet.Add, Search.Detail: one more photograph of the vehicle."""
    last = vehicle.photos.order_by("-position").values_list("position", flat=True).first()
    photo = VehiclePhoto.objects.create(
        vehicle=vehicle, image=_key(upload, "photo"), position=0 if last is None else last + 1
    )
    _audit(actor, "Create", photo, None, snapshot(photo), request)
    return photo


@transaction.atomic
def remove_photo(photo: VehiclePhoto, actor, request=None) -> None:
    """Keeps Fleet.Add's minimum: the last four photographs cannot be removed."""
    Vehicle.objects.select_for_update().get(pk=photo.vehicle_id)
    if VehiclePhoto.objects.filter(vehicle_id=photo.vehicle_id).count() <= (
        settings.VEHICLE_PHOTOS_MINIMUM
    ):
        raise FleetAdminError(
            f"A vehicle keeps at least {settings.VEHICLE_PHOTOS_MINIMUM} photographs; add "
            "another before removing this one."
        )
    before, pk = snapshot(photo), photo.pk
    photo.delete()
    photo.pk = pk
    _audit(actor, "Delete", photo, before, None, request)


def add_document(vehicle: Vehicle, data: dict, actor, request=None) -> VehicleDocument:
    """A statutory document with its expiry date (Fleet.Add, SA-3). A renewal is a new
    row, so the history is kept and the latest expiry counts at handover."""
    valid_from = data.get("valid_from")
    if valid_from and data["expiry_date"] < valid_from:
        raise FleetAdminError("The expiry date is before the start date.", field="expiry_date")
    upload = data.get("file")
    document = VehicleDocument.objects.create(
        vehicle=vehicle,
        document_type=data["document_type"],
        document_number=data.get("document_number", "").strip(),
        valid_from=valid_from,
        expiry_date=data["expiry_date"],
        file=_key(upload, "document") if upload else "",
    )
    _audit(actor, "Create", document, None, snapshot(document), request)
    return document


def remove_document(document: VehicleDocument, actor, request=None) -> None:
    """A document entered in error. The audit entry keeps what it said."""
    before, pk = snapshot(document), document.pk
    document.delete()
    document.pk = pk
    _audit(actor, "Delete", document, before, None, request)


# ─── Branches and serviceable areas ───────────────────────────────────────


def _check_branch_name(name: str, exclude_pk: int | None = None) -> str:
    name = name.strip()
    if Branch.objects.exclude(pk=exclude_pk).filter(branch_name__iexact=name).exists():
        raise FleetAdminError("A branch with this name already exists.", field="branch_name")
    return name


@transaction.atomic
def create_branch(actor, data: dict, request=None) -> Branch:
    branch = Branch.objects.create(
        branch_name=_check_branch_name(data["branch_name"]), address=data["address"].strip()
    )
    _audit(actor, "Create", branch, None, snapshot(branch), request)
    return branch


@transaction.atomic
def update_branch(branch: Branch, actor, data: dict, request=None) -> Branch:
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    before = snapshot(branch)
    if "branch_name" in data:
        branch.branch_name = _check_branch_name(data["branch_name"], exclude_pk=branch.pk)
    if "address" in data:
        branch.address = data["address"].strip()
    branch.save()
    _audit(actor, "Update", branch, before, snapshot(branch), request)
    return branch


def add_area(branch: Branch, data: dict, actor, request=None) -> BranchServiceableArea:
    """Book.Deliver.Location: a pincode and locality the branch delivers to."""
    locality = data.get("locality", "").strip()
    if branch.serviceable_areas.filter(pincode=data["pincode"], locality=locality).exists():
        raise FleetAdminError("The branch already serves this area.", field="pincode")
    area = BranchServiceableArea.objects.create(
        branch=branch, pincode=data["pincode"], locality=locality
    )
    _audit(actor, "Create", area, None, snapshot(area), request)
    return area


def remove_area(area: BranchServiceableArea, actor, request=None) -> None:
    before, pk = snapshot(area), area.pk
    area.delete()
    area.pk = pk
    _audit(actor, "Delete", area, before, None, request)
