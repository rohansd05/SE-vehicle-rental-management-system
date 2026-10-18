"""Module N3 maintenance: Maint.Auto.Km / Maint.Auto.Time (BR-15) with the service-due
alert, the document expiry alert, BR-16's authorised technician, the workshop
invoice (Maint.Record), the cancellation record and the daily Beat schedule."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchStaffFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.core.models import AuditLog
from apps.fleet.models import Vehicle
from apps.fleet.services.status import ActorNotPermittedError, may_clear_unsafe, update_status
from apps.fleet.tests.factories import CarFactory, TwoWheelerFactory, VehicleDocumentFactory
from apps.maintenance import services, tasks
from apps.maintenance.models import MaintenanceJob, UnsafeClearanceAuthorisation
from apps.maintenance.services import NextServiceDue
from apps.maintenance.tests.factories import MaintenanceJobFactory
from apps.rentals.tests.factories import image_file

pytestmark = pytest.mark.django_db

D = Decimal
S = MaintenanceJob.Status
V = Vehicle.Status


@pytest.fixture(autouse=True)
def _media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _months_ago(months: int) -> date:
    return services._add_months(timezone.localdate(), -months)


# ─── BR-15: when a service is due ─────────────────────────────────────────


def test_a_car_is_due_at_5000_km_or_6_months_whichever_first():
    car = CarFactory(
        odometer=17999, last_service_odometer=13000, last_service_date=date(2026, 6, 1)
    )
    assert services.service_due(car, on=date(2026, 11, 30)) is None
    car.odometer = 18000  # 5,000 km first
    assert services.service_due(car, on=date(2026, 11, 30)) == NextServiceDue(
        18000, date(2026, 12, 1)
    )
    car.odometer = 15000  # six months first
    assert services.service_due(car, on=date(2026, 12, 1)) is not None


def test_a_two_wheeler_is_due_at_3000_km_or_4_months():
    bike = TwoWheelerFactory(
        odometer=6999, last_service_odometer=4000, last_service_date=date(2026, 6, 1)
    )
    assert services.service_due(bike, on=date(2026, 9, 30)) is None
    assert services.service_due(bike, on=date(2026, 10, 1)) is not None  # four months
    bike.odometer = 7000
    assert services.service_due(bike, on=date(2026, 9, 30)) is not None  # 3,000 km


def test_without_a_service_on_record_nothing_is_due():
    assert services.service_due(CarFactory(odometer=90000)) is None


def test_due_text_names_both_points():
    assert services.due_text(NextServiceDue(18000, date(2027, 4, 1))) == (
        "18,000 km or 01 Apr 2027, whichever comes first"
    )
    assert services.due_text(NextServiceDue(18000, None)) == "18,000 km"


# ─── Maint.Auto.Km / Maint.Auto.Time: raise_preventive_job_if_due() ───────


@pytest.fixture
def due_car():
    return CarFactory(odometer=18000, last_service_odometer=13000, last_service_date=_months_ago(1))


def test_a_due_vehicle_gets_a_preventive_job_from_the_system_with_the_alert(due_car, outbox):
    technician = MaintenanceTechnicianFactory()
    admin = AdministratorFactory()
    MaintenanceTechnicianFactory(user__is_active=False)  # a disabled account is not alerted

    job = services.raise_preventive_job_if_due(due_car)

    assert (job.job_type, job.status, job.reported_by) == ("Preventive", S.REPORTED, None)
    assert job.severity == settings.PREVENTIVE_JOB_SEVERITY
    # UC 9 extension 2a: pre-filled with the due distance and date.
    assert job.due_odometer == 18000
    assert job.due_date == services._add_months(due_car.last_service_date, 6)
    assert "18,000 km" in job.reported_problem and "BR-15" in job.reported_problem
    entry = AuditLog.objects.get(entity_type="maintenance.MaintenanceJob", entity_id=str(job.pk))
    assert (entry.action, entry.actor) == ("Create", None)  # a system action
    alerted = {m.recipient for m in outbox if "preventive service due" in m.subject}
    assert alerted == {technician.user.email, admin.user.email}  # Send Maintenance Alert
    assert Vehicle.objects.get(pk=due_car.pk).status == V.AVAILABLE  # reporting changes nothing


def test_an_open_preventive_job_is_not_raised_twice(due_car):
    first = services.raise_preventive_job_if_due(due_car)
    assert services.raise_preventive_job_if_due(due_car) is None
    MaintenanceJob.objects.filter(pk=first.pk).update(status=S.SCHEDULED)
    assert services.raise_preventive_job_if_due(due_car) is None
    MaintenanceJob.objects.filter(pk=first.pk).update(status=S.CANCELLED)
    assert services.raise_preventive_job_if_due(due_car) is not None  # cancelled: due again


def test_a_corrective_job_does_not_stop_the_preventive_one(due_car):
    MaintenanceJobFactory(vehicle=due_car, status=S.REPORTED)
    assert services.raise_preventive_job_if_due(due_car) is not None


def test_nothing_is_raised_for_a_vehicle_not_due_or_retired(due_car):
    assert services.raise_preventive_job_if_due(CarFactory(odometer=12000)) is None
    Vehicle.objects.filter(pk=due_car.pk).update(status=V.RETIRED)
    assert services.raise_preventive_job_if_due(due_car) is None


def test_the_daily_sweep_raises_by_time_and_distance(outbox):
    by_time = CarFactory(
        odometer=13100, last_service_odometer=13000, last_service_date=_months_ago(6)
    )
    by_km = TwoWheelerFactory(
        odometer=7000, last_service_odometer=4000, last_service_date=_months_ago(1)
    )
    CarFactory(odometer=13100, last_service_odometer=13000, last_service_date=_months_ago(1))
    CarFactory(odometer=99000)  # never serviced: unknown, not swept

    assert tasks.raise_preventive_jobs.delay().get() == 2
    raised = MaintenanceJob.objects.filter(job_type="Preventive")
    assert set(raised.values_list("vehicle_id", flat=True)) == {by_time.pk, by_km.pk}
    assert tasks.raise_preventive_jobs.delay().get() == 0  # idempotent


# ─── Document expiry alert (context diagram, SA-3) ────────────────────────


def test_the_document_alert_lists_the_latest_expired_or_expiring_documents(outbox):
    admin = AdministratorFactory()
    today = timezone.localdate()
    car = CarFactory(registration_no="MH01DOC0001")
    VehicleDocumentFactory(
        vehicle=car, document_type="Insurance", expiry_date=today + timedelta(days=10)
    )
    VehicleDocumentFactory(
        vehicle=car, document_type="Road Tax", expiry_date=today - timedelta(days=1)
    )
    renewed = CarFactory()
    VehicleDocumentFactory(
        vehicle=renewed, document_type="Insurance", expiry_date=today + timedelta(days=5)
    )
    VehicleDocumentFactory(  # the renewal: the latest row counts
        vehicle=renewed, document_type="Insurance", expiry_date=today + timedelta(days=400)
    )
    VehicleDocumentFactory(
        vehicle=CarFactory(), document_type="Insurance", expiry_date=today + timedelta(days=31)
    )
    retired = CarFactory(status=V.RETIRED)
    VehicleDocumentFactory(vehicle=retired, expiry_date=today)

    assert tasks.alert_expiring_documents.delay().get() == 2
    [mail] = [m for m in outbox if "documents expired" in m.subject]
    assert mail.recipient == admin.user.email
    assert "MH01DOC0001: Road Tax expired on" in mail.body
    assert "MH01DOC0001: Insurance expires on" in mail.body
    assert renewed.registration_no not in mail.body


def test_no_alert_when_every_document_is_valid(outbox):
    AdministratorFactory()
    VehicleDocumentFactory()
    assert services.alert_expiring_documents() == 0
    assert outbox == []


def test_both_daily_tasks_are_scheduled_by_migration_0004():
    tasks_by_name = dict(PeriodicTask.objects.values_list("task", "interval__period"))
    assert tasks_by_name["apps.maintenance.tasks.raise_preventive_jobs"] == "days"
    assert tasks_by_name["apps.maintenance.tasks.alert_expiring_documents"] == "days"


# ─── BR-16: technicians authorised to clear Unsafe ────────────────────────


@pytest.fixture
def admin():
    return AdministratorFactory().user


@pytest.fixture
def tech():
    return MaintenanceTechnicianFactory()


def _recorded_job(tech, status=V.UNSAFE) -> MaintenanceJob:
    vehicle = CarFactory(odometer=15000, status=status)
    job = MaintenanceJobFactory(vehicle=vehicle, technician=tech, status=S.IN_PROGRESS)
    return services.record_work(
        job.pk,
        tech.user,
        service_date=timezone.localdate(),
        odometer_at_service=15100,
        work_description="Replaced the brake disc.",
        labour_cost=D("500.00"),
        downtime_hours=D("2.00"),
        parts=[],
    )


def test_an_administrator_authorises_and_revokes_a_technician_with_audit(admin, tech):
    assert not may_clear_unsafe(tech.user)
    grant = services.authorise_technician(tech, admin)
    assert grant.granted_by == admin and may_clear_unsafe(tech.user)
    services.authorise_technician(tech, admin)  # twice is once
    assert UnsafeClearanceAuthorisation.objects.count() == 1
    services.revoke_authorisation(tech, admin)
    assert not may_clear_unsafe(tech.user)
    actions = list(
        AuditLog.objects.filter(entity_type="accounts.MaintenanceTechnician")
        .order_by("id")
        .values_list("action", "actor")
    )
    assert actions == [
        ("Unsafe Clearance Authorised", admin.pk),
        ("Unsafe Clearance Revoked", admin.pk),
    ]


def test_only_an_administrator_authorises_and_never_a_disabled_technician(admin, tech):
    with pytest.raises(services.MaintenanceError):
        services.authorise_technician(tech, BranchStaffFactory().user)
    with pytest.raises(services.MaintenanceError):
        services.revoke_authorisation(tech, tech.user)
    disabled = MaintenanceTechnicianFactory(user__is_active=False)
    with pytest.raises(services.MaintenanceError):
        services.authorise_technician(disabled, admin)


def test_an_authorised_technician_clears_unsafe_while_closing_and_is_recorded(admin, tech):
    services.authorise_technician(tech, admin)
    job = _recorded_job(tech)

    job = services.complete_job(job.pk, tech.user, clear_unsafe=True)

    assert job.status == S.COMPLETED and job.closed_by == tech.user  # BR-16 identity
    assert Vehicle.objects.get(pk=job.vehicle_id).status == V.AVAILABLE
    cleared = AuditLog.objects.get(action="Vehicle Status Changed", after__status="Available")
    assert cleared.actor == tech.user and cleared.before == {"status": "Unsafe"}


def test_an_unauthorised_technician_cannot_clear_unsafe(tech):
    job = _recorded_job(tech)
    with pytest.raises(services.MaintenanceError, match="authorised technician"):
        services.complete_job(job.pk, tech.user, clear_unsafe=True)
    with pytest.raises(ActorNotPermittedError):  # nor through the state machine
        update_status(job.vehicle, V.AVAILABLE, actor=tech.user, reason="try")
    # Without clear_unsafe the job asks an Administrator, as before (Exp 4 sequence 3).
    job = services.complete_job(job.pk, tech.user)
    assert job.awaiting_clearance


def test_an_authorised_technician_may_still_ask_an_administrator(admin, tech):
    services.authorise_technician(tech, admin)
    job = services.complete_job(_recorded_job(tech).pk, tech.user)
    assert job.awaiting_clearance
    assert Vehicle.objects.get(pk=job.vehicle_id).status == V.UNSAFE


def test_a_revoked_technician_is_refused_by_the_state_machine(admin, tech):
    services.authorise_technician(tech, admin)
    services.revoke_authorisation(tech, admin)
    vehicle = CarFactory(status=V.UNSAFE)
    with pytest.raises(ActorNotPermittedError):
        update_status(vehicle, V.AVAILABLE, actor=tech.user, reason="try")


def test_an_administrator_clears_while_completing_directly(admin, tech):
    job = services.complete_job(_recorded_job(tech).pk, admin, clear_unsafe=True)
    assert job.status == S.COMPLETED and job.closed_by == admin


def test_clear_unsafe_on_a_vehicle_not_flagged_simply_completes(admin, tech):
    services.authorise_technician(tech, admin)
    job = services.complete_job(
        _recorded_job(tech, status=V.UNDER_MAINTENANCE).pk, tech.user, clear_unsafe=True
    )
    assert job.status == S.COMPLETED


# ─── API: complete with clearance, authorisation, invoice, fields ─────────


def test_complete_endpoint_takes_clear_unsafe(admin, tech):
    services.authorise_technician(tech, admin)
    job = _recorded_job(tech)
    client = authenticated_client(tech.user)
    detail = client.get(reverse("maintenance:job-detail", args=[job.pk])).json()
    assert detail["can_clear_unsafe"] is True
    response = client.post(
        reverse("maintenance:job-complete", args=[job.pk]), {"clear_unsafe": True}, format="json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["status"] == "Completed"
    assert response.json()["closed_by"] == tech.user.name


def test_can_clear_unsafe_is_false_for_an_unauthorised_technician(tech):
    job = _recorded_job(tech)
    data = authenticated_client(tech.user).get(reverse("maintenance:job-detail", args=[job.pk]))
    assert data.json()["can_clear_unsafe"] is False


def test_authorisation_endpoint_grants_and_revokes(admin, tech):
    client = authenticated_client(admin)
    url = reverse("maintenance:technician-authorisation", args=[tech.pk])
    assert client.put(url).json()["authorised_to_clear_unsafe"] is True
    listed = client.get(reverse("maintenance:technician-list")).json()
    assert listed[0]["authorised_to_clear_unsafe"] is True
    assert client.delete(url).json()["authorised_to_clear_unsafe"] is False
    assert (
        client.put(reverse("maintenance:technician-authorisation", args=[999999])).status_code
        == 404
    )


def _invoice(name="invoice.pdf", content=b"%PDF-1.4 test invoice"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def test_the_assigned_technician_attaches_a_workshop_invoice(tech):
    job = _recorded_job(tech, status=V.UNDER_MAINTENANCE)
    client = authenticated_client(tech.user)
    url = reverse("maintenance:job-invoice", args=[job.pk])

    response = client.put(url, {"workshop_invoice": _invoice()}, format="multipart")
    assert response.status_code == 200, response.content
    assert "/api/v1/files/" in response.json()["workshop_invoice_url"]  # SI-3 signed link
    job.refresh_from_db()
    assert job.workshop_invoice.name.startswith("maintenance/invoices/invoice-")
    assert AuditLog.objects.filter(action="Workshop Invoice Attached").count() == 1
    photo = client.put(url, {"workshop_invoice": image_file("bill.png", "PNG")}, format="multipart")
    assert photo.status_code == 200  # a photo of the invoice is accepted too


@pytest.mark.parametrize(
    ("upload", "message"),
    [
        (lambda: _invoice("invoice.exe"), "PDF, JPG or PNG"),
        (lambda: _invoice(content=b"not a pdf"), "not a valid PDF"),
        (lambda: image_file("bill.png", "JPEG"), "does not match"),
    ],
)
def test_an_invalid_invoice_is_refused(tech, upload, message):
    job = _recorded_job(tech, status=V.UNDER_MAINTENANCE)
    response = authenticated_client(tech.user).put(
        reverse("maintenance:job-invoice", args=[job.pk]),
        {"workshop_invoice": upload()},
        format="multipart",
    )
    assert response.status_code == 400
    assert message in str(response.json()["workshop_invoice"])


def test_an_invoice_only_while_in_progress_and_by_the_assignee(tech):
    job = _recorded_job(tech, status=V.UNDER_MAINTENANCE)
    with pytest.raises(services.MaintenanceError, match="not assigned"):
        services.attach_invoice(job.pk, MaintenanceTechnicianFactory().user, _invoice())
    MaintenanceJob.objects.filter(pk=job.pk).update(status=S.COMPLETED)
    with pytest.raises(services.MaintenanceError, match="in progress"):
        services.attach_invoice(job.pk, tech.user, _invoice())


def test_a_cancelled_job_records_who_cancelled_it_when_and_why(tech):
    vehicle = CarFactory()
    staff = BranchStaffFactory(branch=vehicle.home_branch).user
    job = MaintenanceJobFactory(vehicle=vehicle, technician=tech, status=S.REPORTED)
    services.cancel_job(job.pk, staff, "  Duplicate of job 41.  ")
    data = authenticated_client(staff).get(reverse("maintenance:job-detail", args=[job.pk])).json()
    assert data["status"] == "Cancelled"
    assert data["cancelled_by"] == staff.name
    assert data["cancel_reason"] == "Duplicate of job 41."
    assert data["cancelled_at"] is not None


def test_job_and_vehicle_fields_for_the_screens(due_car):
    job = services.raise_preventive_job_if_due(due_car)
    admin = AdministratorFactory().user
    data = authenticated_client(admin).get(reverse("maintenance:job-detail", args=[job.pk])).json()
    assert data["reported_by"] is None  # raised by the system
    assert (data["due_odometer"], data["vehicle"]["service_overdue"]) == (18000, True)
    assert data["workshop_invoice_url"] is None
