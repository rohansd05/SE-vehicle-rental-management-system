"""Handover Vehicle services (SRS 3.3; Exp 2 use case 7; Exp 5 handover fork/join)."""

from datetime import date, timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.models import Licence
from apps.accounts.tests.factories import BranchStaffFactory
from apps.bookings.models import Booking
from apps.bookings.states import IllegalBookingTransition, activate_booking
from apps.bookings.tests.factories import BookingAddOnFactory, BookingFactory
from apps.core.models import AuditLog
from apps.fleet.models import Vehicle, VehicleDocument
from apps.fleet.tests.factories import TwoWheelerFactory
from apps.notifications.models import Notification
from apps.notifications.templates import render
from apps.pricing.tests.factories import AddOnFactory
from apps.rentals import services
from apps.rentals.models import ConditionReport
from apps.rentals.notification_templates import SAMPLE_CONTEXT
from apps.rentals.tests.factories import checklist, ready_booking

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def codes(booking) -> list[str]:
    booking = Booking.objects.get(pk=booking.pk)
    return [refusal.code for refusal in services.handover_refusals(booking)]


def staff_at(booking):
    return BranchStaffFactory(branch=booking.pickup_branch).user


# ─── Handover.Refuse ──────────────────────────────────────────────────────


class TestHandoverRefuse:
    def test_a_ready_booking_has_no_refusal(self):
        assert codes(ready_booking()) == []

    def test_an_expired_licence_is_refused(self):
        booking = ready_booking()
        Licence.objects.filter(customer=booking.customer).update(
            expiry_date=date.today() - timedelta(days=1)
        )
        assert codes(booking) == ["licence_expired"]

    def test_a_licence_expiring_during_the_rental_is_refused_br2(self):
        booking = ready_booking()
        Licence.objects.filter(customer=booking.customer).update(
            expiry_date=timezone.localdate(booking.return_datetime) - timedelta(days=1)
        )
        assert codes(booking) == ["licence_expires_before_return"]

    def test_a_licence_without_the_category_is_refused_br3(self):
        booking = ready_booking(vehicle=TwoWheelerFactory())
        Licence.objects.get(customer=booking.customer).categories.filter(
            category="Two-Wheeler"
        ).delete()
        assert codes(booking) == ["licence_category"]

    def test_an_unverified_licence_is_refused(self):
        booking = ready_booking()
        Licence.objects.filter(customer=booking.customer).update(
            status=Licence.Status.PENDING_VERIFICATION
        )
        assert codes(booking) == ["licence_not_verified"]

    @pytest.mark.parametrize(
        ("document_type", "code"),
        [
            ("Insurance", "document_insurance"),
            ("Pollution Certificate", "document_pollution_certificate"),
            ("Fitness Certificate", "document_fitness_certificate"),
            ("Road Tax", "document_road_tax"),
        ],
    )
    def test_each_statutory_document_must_cover_the_whole_rental_sa3(self, document_type, code):
        booking = ready_booking()
        VehicleDocument.objects.filter(vehicle=booking.vehicle, document_type=document_type).update(
            expiry_date=timezone.localdate(booking.pickup_datetime)
        )
        assert codes(booking) == [code]
        refusal = services.handover_refusals(Booking.objects.get(pk=booking.pk))[0]
        assert "before the return date" in refusal.message
        assert document_type.lower() in refusal.message

    def test_a_missing_document_is_named(self):
        booking = ready_booking()
        VehicleDocument.objects.filter(vehicle=booking.vehicle, document_type="Road Tax").delete()
        (refusal,) = services.handover_refusals(Booking.objects.get(pk=booking.pk))
        assert refusal.code == "document_road_tax"
        assert "is not on record" in refusal.message

    def test_a_document_not_yet_valid_on_the_pickup_date_is_refused(self):
        booking = ready_booking()
        VehicleDocument.objects.filter(vehicle=booking.vehicle, document_type="Insurance").update(
            valid_from=date.today() + timedelta(days=5)
        )
        (refusal,) = services.handover_refusals(Booking.objects.get(pk=booking.pk))
        assert "not yet valid" in refusal.message

    def test_a_vehicle_flagged_unsafe_is_refused_sa2(self):
        booking = ready_booking()
        Vehicle.objects.filter(pk=booking.vehicle_id).update(status=Vehicle.Status.UNSAFE)
        assert codes(booking) == ["vehicle_unsafe"]

    def test_a_vehicle_under_maintenance_is_refused(self):
        booking = ready_booking()
        Vehicle.objects.filter(pk=booking.vehicle_id).update(
            status=Vehicle.Status.UNDER_MAINTENANCE
        )
        assert codes(booking) == ["vehicle_unavailable"]

    def test_an_unpaid_booking_is_refused_until_cash_is_recorded(self):
        booking = ready_booking()
        booking.payments.all().delete()
        assert codes(booking) == ["payment_due"]

    def test_before_the_pickup_time_the_handover_waits(self):
        booking = ready_booking()
        with freeze_time(booking.pickup_datetime - timedelta(minutes=1)):
            assert codes(booking) == ["pickup_not_arrived"]

    def test_every_failed_condition_is_listed(self):
        booking = ready_booking()
        Vehicle.objects.filter(pk=booking.vehicle_id).update(status=Vehicle.Status.UNSAFE)
        booking.payments.all().delete()
        assert codes(booking) == ["vehicle_unsafe", "payment_due"]

    @pytest.mark.parametrize("status", ["Cancelled", "No-show", "Completed", "Pending Payment"])
    def test_only_a_confirmed_booking_can_be_handed_over(self, status):
        assert codes(ready_booking(status=status)) == ["booking_not_confirmed"]

    def test_an_active_booking_is_already_handed_over(self):
        assert codes(ready_booking(status=Booking.Status.ACTIVE)) == ["already_handed_over"]


# ─── Branch bookings (UC 7 step 1) ────────────────────────────────────────


class TestBranchCollections:
    def test_today_and_upcoming_are_split_by_the_pickup_date(self):
        now = timezone.localtime().replace(hour=12, minute=0)
        with freeze_time(now):
            today = BookingFactory(pickup_datetime=now - timedelta(hours=2))
            later = BookingFactory(pickup_datetime=now + timedelta(days=2))
            BookingFactory(pickup_datetime=now + timedelta(hours=3), status="Cancelled")
            bookings = Booking.objects.all()
            assert list(services.branch_collections(bookings)) == [today]
            assert list(services.branch_collections(bookings, when="upcoming")) == [later]

    def test_find_by_reference_pickup_code_or_mobile(self):
        booking = BookingFactory(pickup_datetime=timezone.now() - timedelta(days=3))
        BookingFactory()
        mobile = booking.customer.user.mobile_no
        for query in [
            booking.booking_reference.lower(),
            booking.pickup_code,
            mobile,
            mobile[-10:],
            f"{mobile[:3]} {mobile[3:8]} {mobile[8:]}",
        ]:
            found = services.branch_collections(Booking.objects.all(), query=query)
            assert list(found) == [booking], query

    def test_a_search_never_finds_a_booking_that_is_not_confirmed(self):
        booking = BookingFactory(status=Booking.Status.ACTIVE)
        found = services.branch_collections(Booking.objects.all(), query=booking.booking_reference)
        assert not found.exists()


# ─── Handover.Checklist ───────────────────────────────────────────────────


def test_expected_accessories_are_the_add_ons():
    booking = ready_booking()
    BookingAddOnFactory(booking=booking, add_on=AddOnFactory(name="Child seat"), quantity=2)
    assert services.expected_accessories(booking) == [{"name": "Child seat", "quantity": 2}]


def test_a_two_wheeler_comes_with_br7s_free_helmet():
    booking = ready_booking(vehicle=TwoWheelerFactory())
    assert services.expected_accessories(booking) == [{"name": "Helmet", "quantity": 1}]


# ─── Handover.Activate (one transaction) ──────────────────────────────────


class TestHandoverVehicle:
    def test_records_signs_and_activates_atomically(self, outbox):
        booking = ready_booking()
        staff = staff_at(booking)
        report = services.handover_vehicle(booking.pk, staff, **checklist())

        booking.refresh_from_db()
        assert booking.status == Booking.Status.ACTIVE
        assert booking.handed_over_at is not None  # Handover.Activate: the actual time
        assert Vehicle.objects.get(pk=booking.vehicle_id).status == Vehicle.Status.ON_RENT

        report = ConditionReport.objects.get(pk=report.pk)
        assert report.is_signed_in_db and report.signed_at is not None
        assert report.recorded_by.user == staff
        assert [p.caption for p in report.photos.all()] == ["Front", "Rear", "Left", "Right"]
        assert report.accessories == [{"name": "Child seat", "quantity": 1}]
        assert report.damage_marks[0]["note"] == "Scratch on the rear bumper"

        actions = set(AuditLog.objects.filter(actor=staff).values_list("action", flat=True))
        assert actions == {
            "Condition Report Signed",
            "Booking Status Changed",
            "Vehicle Status Changed",
        }
        assert AuditLog.objects.verify_chain()

        # Handover.Sign: a copy to the customer, through the Celery task.
        notification = Notification.objects.get(template="handover_report")
        assert notification.status == Notification.Status.SENT
        assert notification.recipient == booking.customer.user
        (email,) = [m for m in outbox if m.channel == "email"]
        assert booking.booking_reference in email.subject
        assert "Odometer: 15000 km" in email.body
        assert "Child seat x1" in email.body

    def test_a_refusal_changes_nothing(self):
        booking = ready_booking()
        Vehicle.objects.filter(pk=booking.vehicle_id).update(status=Vehicle.Status.UNSAFE)
        with pytest.raises(services.HandoverRefusedError) as raised:
            services.handover_vehicle(booking.pk, staff_at(booking), **checklist())
        assert [r.code for r in raised.value.refusals] == ["vehicle_unsafe"]
        booking.refresh_from_db()
        assert booking.status == Booking.Status.CONFIRMED and booking.handed_over_at is None
        assert not ConditionReport.objects.exists()
        assert not Notification.objects.filter(template="handover_report").exists()

    def test_a_second_handover_is_refused(self):
        booking = ready_booking()
        staff = staff_at(booking)
        services.handover_vehicle(booking.pk, staff, **checklist())
        with pytest.raises(services.HandoverRefusedError) as raised:
            services.handover_vehicle(booking.pk, staff, **checklist())
        assert [r.code for r in raised.value.refusals] == ["already_handed_over"]
        assert ConditionReport.objects.count() == 1

    def test_staff_of_another_branch_cannot_hand_over(self):
        booking = ready_booking()
        with pytest.raises(services.HandoverError, match="another branch"):
            services.handover_vehicle(booking.pk, BranchStaffFactory().user, **checklist())

    def test_a_failure_after_the_report_rolls_everything_back(self, monkeypatch):
        booking = ready_booking()

        def fail(*args, **kwargs):
            raise RuntimeError("status service down")

        monkeypatch.setattr(services, "update_status", fail)
        with pytest.raises(RuntimeError):
            services.handover_vehicle(booking.pk, staff_at(booking), **checklist())
        booking.refresh_from_db()
        assert booking.status == Booking.Status.CONFIRMED
        assert not ConditionReport.objects.exists()


class TestActivateBooking:
    """bookings.states.activate_booking(), added for Module N1 (Rohan to review)."""

    def test_confirmed_becomes_active_with_the_handover_time(self):
        booking = BookingFactory()
        staff = BranchStaffFactory().user
        activate_booking(booking, staff)
        booking.refresh_from_db()
        assert booking.status == Booking.Status.ACTIVE
        assert booking.handed_over_at is not None
        entry = AuditLog.objects.get(action="Booking Status Changed")
        assert entry.actor == staff
        assert entry.before == {"status": "Confirmed"}

    @pytest.mark.parametrize("status", ["Draft", "Pending Payment", "Cancelled", "Completed"])
    def test_only_from_confirmed(self, status):
        with pytest.raises(IllegalBookingTransition):
            activate_booking(BookingFactory(status=status), None)


def test_the_handover_e_mail_renders():
    subject, body = render("handover_report", 1, SAMPLE_CONTEXT)
    assert "VRMS-20261016-0001" in subject
    assert "Existing damage: Scratch on the rear bumper" in body
