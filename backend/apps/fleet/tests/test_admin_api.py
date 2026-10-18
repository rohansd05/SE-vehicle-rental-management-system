"""Fleet administration API (Module N3): SRS 3.7 Fleet.Add, Fleet.Status, Fleet.Retire,
Fleet.Audit; Exp 2 use case 11 with extension 1a; SA-3 documents; branches and
serviceable areas. Administrator only (SE-4)."""

import json
from datetime import timedelta

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.tests.factories import BookingFactory
from apps.core.choices import VehicleType
from apps.core.models import AuditLog
from apps.fleet.models import Branch, Car, TwoWheeler, Vehicle, VehicleDocument
from apps.fleet.tests.factories import (
    BranchFactory,
    BranchServiceableAreaFactory,
    CarFactory,
    VehicleCategoryFactory,
    VehicleDocumentFactory,
    VehiclePhotoFactory,
)
from apps.rentals.tests.factories import image_file

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def admin():
    return AdministratorFactory().user


@pytest.fixture
def client(admin):
    return authenticated_client(admin)


def _documents(**expiries) -> str:
    return json.dumps(
        [
            {"document_type": name, "expiry_date": expiries.get(name, "2027-12-31")}
            for name in settings.HANDOVER_REQUIRED_DOCUMENTS
        ]
    )


def _car(**overrides) -> dict:
    data = {
        "registration_no": "MH 02 ZZ 9001",
        "category": VehicleCategoryFactory(name="Hatchback").pk,
        "brand": "Tata",
        "model": "Altroz",
        "year": 2025,
        "colour": "Gold",
        "fuel_type": "Petrol",
        "transmission": "Manual",
        "seating_capacity": 5,
        "chassis_number": "demochassis 0099",
        "home_branch": BranchFactory().pk,
        "odometer": 120,
        "fuel_capacity": "37.00",
        "available_from": timezone.localdate().isoformat(),
        "photos": [image_file(f"side-{i}.jpg") for i in range(4)],
        "documents": _documents(),
    }
    data.update(overrides)
    return data


LIST = reverse("fleet:admin-vehicles")


def _detail(vehicle):
    return reverse("fleet:admin-vehicle", args=[vehicle.pk])


# ─── Fleet.Add (UC 11 step 1) ─────────────────────────────────────────────


def test_an_administrator_adds_a_car_with_photos_and_documents(client, admin):
    response = client.post(LIST, _car(), format="multipart")

    assert response.status_code == 201, response.content
    data = response.json()
    car = Car.objects.get(pk=data["id"])
    assert (car.registration_no, car.chassis_number) == ("MH02ZZ9001", "DEMOCHASSIS0099")
    assert (car.status, car.transmission, car.seating_capacity) == ("Available", "Manual", 5)
    assert str(car.fuel_capacity) == "37.00"
    assert len(data["photos"]) == 4 and all(p["url"] for p in data["photos"])
    assert {d["document_type"] for d in data["documents"]} == set(
        settings.HANDOVER_REQUIRED_DOCUMENTS
    )
    assert data["document_alerts"] == []
    # Fleet.Audit: the vehicle, each photo and each document, by the Administrator.
    created = AuditLog.objects.filter(action="Create", actor=admin)
    assert sorted(created.values_list("entity_type", flat=True)) == sorted(
        ["fleet.Car"] + ["fleet.VehiclePhoto"] * 4 + ["fleet.VehicleDocument"] * 4
    )


def test_a_two_wheeler_needs_its_engine_capacity(client):
    category = VehicleCategoryFactory(name="Scooter", vehicle_type=VehicleType.TWO_WHEELER)
    base = _car(category=category.pk)
    del base["transmission"], base["seating_capacity"]
    assert client.post(LIST, base, format="multipart").json() == {
        "engine_cc": ["Enter the engine capacity."]
    }
    photos = [image_file(f"again-{i}.jpg") for i in range(4)]  # the first upload was read
    response = client.post(LIST, {**base, "engine_cc": 110, "photos": photos}, format="multipart")
    assert response.status_code == 201, response.content
    assert TwoWheeler.objects.get(pk=response.json()["id"]).engine_cc == 110


def test_a_car_needs_its_transmission_and_seats(client):
    data = _car()
    del data["transmission"]
    assert "transmission" in client.post(LIST, data, format="multipart").json()


@pytest.mark.parametrize(
    ("field", "value"),
    [("registration_no", "mh02zz 9001"), ("chassis_number", "DEMOCHASSIS0099")],
)
def test_an_existing_registration_or_chassis_number_is_rejected_uc11_1a(client, field, value):
    CarFactory(registration_no="MH02ZZ9001", chassis_number="DEMOCHASSIS0099")
    other = {"registration_no": "MH02ZZ1111", "chassis_number": "NEWCHASSIS"}
    response = client.post(LIST, _car(**{**other, field: value}), format="multipart")
    assert response.status_code == 400
    assert "already exists" in response.json()[field][0]
    assert Vehicle.objects.count() == 1


def test_fewer_than_four_photos_are_refused(client):
    photos = [image_file("one.jpg"), image_file("two.jpg"), image_file("three.jpg")]
    response = client.post(LIST, _car(photos=photos), format="multipart")
    assert response.status_code == 400 and "at least 4" in response.json()["photos"][0]
    assert not Vehicle.objects.exists()


def test_every_statutory_document_needs_an_expiry_date(client):
    documents = json.dumps([{"document_type": "Insurance", "expiry_date": "2027-01-01"}])
    response = client.post(LIST, _car(documents=documents), format="multipart")
    assert response.status_code == 400
    assert "Road Tax" in response.json()["documents"][0]


@pytest.mark.parametrize("capacity", ["0", ""])
def test_the_tank_or_battery_capacity_is_required(client, capacity):
    response = client.post(LIST, _car(fuel_capacity=capacity), format="multipart")
    assert response.status_code == 400 and "fuel_capacity" in response.json()


def test_a_file_that_is_not_an_image_is_refused(client):
    photos = [image_file(f"p{i}.jpg") for i in range(3)] + [image_file("fake.png", "JPEG")]
    response = client.post(LIST, _car(photos=photos), format="multipart")
    assert response.status_code == 400 and "photos" in response.json()


# ─── Fleet.Status: the fleet display ──────────────────────────────────────


def test_the_fleet_lists_every_vehicle_with_status_and_document_alerts(client):
    car = CarFactory(registration_no="MH01AA0001", status="Unsafe")
    VehicleDocumentFactory(
        vehicle=car, document_type="Insurance", expiry_date=timezone.localdate() + timedelta(days=5)
    )
    CarFactory(registration_no="MH01AA0002")

    rows = client.get(LIST).json()["results"]

    assert [r["registration_no"] for r in rows] == ["MH01AA0001", "MH01AA0002"]
    alerts = {a["document_type"]: a["state"] for a in rows[0]["document_alerts"]}
    assert alerts["Insurance"] == "Expiring" and alerts["Road Tax"] == "Missing"
    assert [
        r["registration_no"] for r in client.get(LIST, {"status": "Unsafe"}).json()["results"]
    ] == ["MH01AA0001"]
    assert client.get(LIST, {"q": "aa0002"}).json()["count"] == 1


def test_the_detail_marks_the_current_document_of_each_type(client):
    car = CarFactory()
    old = VehicleDocumentFactory(vehicle=car, expiry_date=timezone.localdate() - timedelta(days=1))
    new = VehicleDocumentFactory(
        vehicle=car, expiry_date=timezone.localdate() + timedelta(days=300)
    )
    documents = {d["id"]: d for d in client.get(_detail(car)).json()["documents"]}
    assert (documents[new.pk]["current"], documents[new.pk]["state"]) == (True, "Valid")
    assert (documents[old.pk]["current"], documents[old.pk]["state"]) == (False, "Expired")


# ─── Edit (UC 11 step 1) ──────────────────────────────────────────────────


def test_an_edit_is_audited_with_the_previous_and_new_values(client, admin):
    car = CarFactory(colour="White")
    response = client.patch(_detail(car), {"colour": "Red", "status": "Retired"}, format="json")
    assert response.status_code == 200
    assert response.json()["colour"] == "Red"
    assert response.json()["status"] == "Available"  # the status is not edited here
    entry = AuditLog.objects.get(action="Update", actor=admin)
    assert (entry.before["colour"], entry.after["colour"]) == ("White", "Red")


def test_the_odometer_never_goes_down_and_the_type_never_changes(client):
    car = CarFactory(odometer=12000)
    assert "odometer" in client.patch(_detail(car), {"odometer": 11999}, format="json").json()
    scooter = VehicleCategoryFactory(name="Scooter", vehicle_type=VehicleType.TWO_WHEELER)
    assert "category" in client.patch(_detail(car), {"category": scooter.pk}, format="json").json()
    assert client.patch(_detail(car), {"odometer": 12500}, format="json").status_code == 200


def test_an_edit_cannot_take_another_vehicles_registration(client):
    CarFactory(registration_no="MH01XX0001")
    car = CarFactory()
    response = client.patch(_detail(car), {"registration_no": "mh01xx0001"}, format="json")
    assert "already exists" in response.json()["registration_no"][0]


# ─── Fleet.Retire through the state machine ───────────────────────────────


def test_a_vehicle_with_a_future_booking_is_not_retired(client):
    booking = BookingFactory()
    url = reverse("fleet:admin-vehicle-retire", args=[booking.vehicle_id])
    response = client.post(url, {"reason": "Old"}, format="json")
    assert response.status_code == 409 and "bookings that are not over" in response.json()["detail"]
    assert Vehicle.objects.get(pk=booking.vehicle_id).status == "Available"


def test_retiring_goes_through_the_state_machine_and_is_audited(client, admin):
    car = CarFactory()
    url = reverse("fleet:admin-vehicle-retire", args=[car.pk])
    assert client.post(url, {"reason": " "}, format="json").status_code == 400
    response = client.post(url, {"reason": "Written off after an accident."}, format="json")
    assert response.json()["status"] == "Retired"
    entry = AuditLog.objects.get(action="Vehicle Status Changed")
    assert entry.actor == admin
    assert entry.after == {"status": "Retired", "reason": "Written off after an accident."}


# ─── Photos and documents ─────────────────────────────────────────────────


def test_photos_are_added_and_removed_but_four_always_stay(client):
    car = CarFactory()
    photos = [VehiclePhotoFactory(vehicle=car) for _ in range(4)]
    added = client.post(
        reverse("fleet:admin-vehicle-photos", args=[car.pk]),
        {"image": image_file("new.jpg")},
        format="multipart",
    )
    assert added.status_code == 201 and added.json()["position"] == 4
    remove = reverse("fleet:admin-vehicle-photo", args=[car.pk, photos[0].pk])
    assert client.delete(remove).status_code == 204
    last = reverse("fleet:admin-vehicle-photo", args=[car.pk, photos[1].pk])
    response = client.delete(last)
    assert response.status_code == 400 and "at least 4" in response.json()["detail"][0]
    assert car.photos.count() == 4


def test_a_renewal_is_a_new_document_and_a_mistake_can_be_removed(client, admin):
    car = CarFactory()
    old = VehicleDocumentFactory(vehicle=car, document_type="Insurance")
    url = reverse("fleet:admin-vehicle-documents", args=[car.pk])
    response = client.post(
        url,
        {"document_type": "Insurance", "document_number": "POL-NEW", "expiry_date": "2028-03-31"},
        format="multipart",
    )
    assert response.status_code == 201, response.content
    assert car.documents.count() == 2  # the history is kept
    bad = client.post(
        url,
        {"document_type": "Road Tax", "valid_from": "2027-01-01", "expiry_date": "2026-01-01"},
        format="multipart",
    )
    assert "expiry_date" in bad.json()
    delete = reverse("fleet:admin-vehicle-document", args=[car.pk, old.pk])
    assert client.delete(delete).status_code == 204
    assert not VehicleDocument.objects.filter(pk=old.pk).exists()
    assert AuditLog.objects.filter(action="Delete", actor=admin).count() == 1


# ─── Branches and serviceable areas ───────────────────────────────────────


def test_branches_are_added_edited_and_their_areas_managed(client, admin):
    BranchFactory(branch_name="Andheri")
    branches = reverse("fleet:admin-branches")
    assert (
        "branch_name"
        in client.post(branches, {"branch_name": "andheri", "address": "x"}, format="json").json()
    )
    created = client.post(
        branches, {"branch_name": "Borivali", "address": "SV Road"}, format="json"
    )
    assert created.status_code == 201
    pk = created.json()["branch_id"]
    edited = client.patch(
        reverse("fleet:admin-branch", args=[pk]), {"address": "LT Road"}, format="json"
    )
    assert edited.json()["address"] == "LT Road"

    areas = reverse("fleet:admin-branch-areas", args=[pk])
    area = client.post(areas, {"pincode": "400092", "locality": "Borivali West"}, format="json")
    assert area.status_code == 201
    assert (
        "pincode"
        in client.post(
            areas, {"pincode": "400092", "locality": "Borivali West"}, format="json"
        ).json()
    )
    assert "pincode" in client.post(areas, {"pincode": "40009"}, format="json").json()
    listed = {b["branch_name"]: b for b in client.get(branches).json()}
    assert listed["Borivali"]["serviceable_areas"][0]["pincode"] == "400092"
    remove = reverse("fleet:admin-branch-area", args=[pk, area.json()["id"]])
    assert client.delete(remove).status_code == 204
    labels = AuditLog.objects.filter(actor=admin).values_list("action", "entity_type")
    assert set(labels) == {
        ("Create", "fleet.Branch"),
        ("Update", "fleet.Branch"),
        ("Create", "fleet.BranchServiceableArea"),
        ("Delete", "fleet.BranchServiceableArea"),
    }
    assert Branch.objects.get(pk=pk).serviceable_areas.count() == 0


# ─── SE-4: Administrator only, every endpoint, every role ─────────────────

ROLES = ["anonymous", "customer", "staff", "technician", "admin", "manager"]


def _user(role):
    return {
        "customer": lambda: CustomerFactory().user,
        "staff": lambda: BranchStaffFactory().user,
        "technician": lambda: MaintenanceTechnicianFactory().user,
        "admin": lambda: AdministratorFactory().user,
        "manager": lambda: BranchManagerFactory().user,
        "anonymous": lambda: None,
    }[role]()


def _vehicle_url(name, *extra):
    return lambda: reverse(f"fleet:{name}", args=[CarFactory().pk, *extra])


def _area_url():
    area = BranchServiceableAreaFactory()
    return reverse("fleet:admin-branch-area", args=[area.branch_id, area.pk])


ENDPOINTS = [
    ("admin-vehicles-get", "get", lambda: LIST),
    ("admin-vehicles-post", "post", lambda: LIST),
    ("admin-vehicle-get", "get", _vehicle_url("admin-vehicle")),
    ("admin-vehicle-patch", "patch", _vehicle_url("admin-vehicle")),
    ("admin-vehicle-retire", "post", _vehicle_url("admin-vehicle-retire")),
    ("admin-vehicle-photos", "post", _vehicle_url("admin-vehicle-photos")),
    ("admin-vehicle-photo", "delete", _vehicle_url("admin-vehicle-photo", 999999)),
    ("admin-vehicle-documents", "post", _vehicle_url("admin-vehicle-documents")),
    ("admin-vehicle-document", "delete", _vehicle_url("admin-vehicle-document", 999999)),
    ("admin-branches-get", "get", lambda: reverse("fleet:admin-branches")),
    ("admin-branches-post", "post", lambda: reverse("fleet:admin-branches")),
    ("admin-branch", "patch", lambda: reverse("fleet:admin-branch", args=[BranchFactory().pk])),
    (
        "admin-branch-areas",
        "post",
        lambda: reverse("fleet:admin-branch-areas", args=[BranchFactory().pk]),
    ),
    ("admin-branch-area", "delete", _area_url),
]


@pytest.mark.parametrize(
    ("method", "url", "role"),
    [
        pytest.param(method, url, role, id=f"{name}-{role}")
        for name, method, url in ENDPOINTS
        for role in ROLES
    ],
)
def test_endpoint_permission(api_client, method, url, role):
    user = _user(role)
    client = authenticated_client(user) if user else api_client
    response = getattr(client, method)(url(), {}, format="json")
    if role == "admin":
        assert response.status_code not in (401, 403), response.content
    else:
        assert response.status_code == (401 if role == "anonymous" else 403), response.content


def test_every_fleet_admin_route_is_in_the_matrix():
    from apps.fleet.urls import urlpatterns

    named = {p.name for p in urlpatterns if p.name.startswith("admin-")}
    covered = {name.rsplit("-", 1)[0] if name.endswith(("-get", "-post", "-patch")) else name
               for name, *_ in ENDPOINTS}  # fmt: skip
    assert named == covered
