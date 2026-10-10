"""Licence submission and verification (Book.Eligible.*, BR-2, BR-3, SE-10, SI-3, D3)."""

import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from PIL import Image

from apps.accounts.models import Licence
from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchStaffFactory,
    CustomerFactory,
    LicenceFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.core.models import AuditLog
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def image_file(name="licence.png", fmt="PNG", size=(64, 40)) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(30, 90, 160)).save(buffer, format=fmt)
    content_type = "image/png" if fmt == "PNG" else "image/jpeg"
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


def submission(**overrides):
    today = timezone.localdate()
    data = {
        "licence_number": "mh02 20190012345",
        "issuing_authority": "RTO Mumbai (West)",
        "issue_date": (today - timedelta(days=2000)).isoformat(),
        "expiry_date": (today + timedelta(days=3000)).isoformat(),
        "categories": ["Car", "Two-Wheeler"],
        "front_image": image_file("front.png"),
        "back_image": image_file("back.jpg", fmt="JPEG"),
    }
    data.update(overrides)
    return data


@pytest.fixture
def customer():
    customer = CustomerFactory()
    LicenceFactory(customer=customer, licence_number="", status=Licence.Status.NOT_SUBMITTED)
    return customer


@pytest.fixture
def customer_client(customer):
    return authenticated_client(customer.user)


def _submit(client, **overrides):
    return client.post(reverse("accounts:licence"), submission(**overrides), format="multipart")


class TestSubmission:
    def test_valid_submission_awaits_verification(self, customer, customer_client):
        response = _submit(customer_client)
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["status"] == "Pending Verification"
        assert body["licence_number"] == "MH02 20190012345"
        assert body["categories"] == ["Car", "Two-Wheeler"]
        assert body["front_image_url"] and "/api/v1/files/" in body["front_image_url"]
        licence = Licence.objects.get(customer=customer)
        assert licence.front_image.name.startswith("licences/front-")  # unguessable key
        entry = AuditLog.objects.get(action="Licence Submitted")
        assert entry.actor == customer.user

    def test_get_returns_my_licence(self, customer_client):
        _submit(customer_client)
        response = customer_client.get(reverse("accounts:licence"))
        assert response.status_code == 200
        assert response.json()["status"] == "Pending Verification"

    @pytest.mark.parametrize("name", ["front.gif", "front.pdf", "front.bmp", "front"])
    def test_wrong_extension_is_rejected(self, customer_client, name):
        response = _submit(customer_client, front_image=image_file(name))
        assert response.status_code == 400
        assert "front_image" in response.json()

    def test_oversize_file_is_rejected(self, customer_client, settings):
        settings.LICENCE_IMAGE_MAX_BYTES = 1024
        response = _submit(customer_client, front_image=image_file(size=(800, 800)))
        assert response.status_code == 400
        assert "front_image" in response.json()

    def test_corrupt_image_is_rejected(self, customer_client):
        corrupt = SimpleUploadedFile("front.png", b"\x89PNG\r\n\x1a\nnot really a png")
        response = _submit(customer_client, front_image=corrupt)
        assert response.status_code == 400
        assert "front_image" in response.json()

    def test_disguised_file_is_rejected(self, customer_client):
        """A JPEG renamed .png is caught by the format check."""
        response = _submit(customer_client, front_image=image_file("front.png", fmt="JPEG"))
        assert response.status_code == 400

    def test_both_images_are_required(self, customer_client):
        data = submission()
        del data["back_image"]
        response = customer_client.post(reverse("accounts:licence"), data, format="multipart")
        assert response.status_code == 400
        assert "back_image" in response.json()

    def test_expired_licence_is_rejected(self, customer_client):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = _submit(customer_client, expiry_date=yesterday)
        assert response.status_code == 400
        assert response.json()["detail"] == "This licence has already expired."

    def test_unknown_category_is_rejected(self, customer_client):
        response = _submit(customer_client, categories=["Truck"])
        assert response.status_code == 400

    def test_licence_number_of_another_customer_is_rejected(self, customer_client):
        LicenceFactory(licence_number="MH02 20190012345")
        response = _submit(customer_client)
        assert response.status_code == 400

    def test_resubmission_after_rejection(self, customer, customer_client):
        _submit(customer_client)
        licence = Licence.objects.get(customer=customer)
        Licence.objects.filter(pk=licence.pk).update(
            status=Licence.Status.REJECTED, rejection_reason="Blurred"
        )
        response = _submit(customer_client, categories=["Car"])
        assert response.status_code == 200
        assert response.json()["status"] == "Pending Verification"
        assert response.json()["rejection_reason"] == ""
        assert response.json()["categories"] == ["Car"]


class TestVerification:
    @pytest.fixture
    def pending(self, customer, customer_client):
        _submit(customer_client)
        return Licence.objects.get(customer=customer)

    @pytest.fixture(params=["staff", "admin"])
    def verifier(self, request):
        if request.param == "staff":
            return BranchStaffFactory().user
        return AdministratorFactory().user

    def test_pending_queue_lists_the_licence(self, pending, verifier):
        response = authenticated_client(verifier).get(reverse("accounts:licence-pending"))
        assert response.status_code == 200
        results = response.json()["results"]
        assert [item["id"] for item in results] == [pending.pk]
        assert results[0]["customer"]["email"] == pending.customer.user.email

    def test_approve(self, pending, verifier, outbox):
        url = reverse("accounts:licence-approve", args=[pending.pk])
        response = authenticated_client(verifier).post(url)
        assert response.status_code == 200
        pending.refresh_from_db()
        assert pending.status == Licence.Status.VERIFIED
        assert pending.verified_by == verifier
        entry = AuditLog.objects.get(action="Licence Verified")
        assert entry.actor == verifier
        assert entry.before["status"] == "Pending Verification"
        assert entry.after["status"] == "Verified"
        mail = Notification.objects.get(template="licence_approved")
        assert mail.status == Notification.Status.SENT
        assert outbox[-1].recipient == pending.customer.user.email

    def test_reject_with_reason(self, pending, verifier, outbox):
        url = reverse("accounts:licence-reject", args=[pending.pk])
        response = authenticated_client(verifier).post(url, {"reason": "Photo is blurred."})
        assert response.status_code == 200
        pending.refresh_from_db()
        assert pending.status == Licence.Status.REJECTED
        assert pending.rejection_reason == "Photo is blurred."
        assert AuditLog.objects.filter(action="Licence Rejected").exists()
        assert "Photo is blurred." in outbox[-1].body

    @pytest.mark.parametrize("payload", [{}, {"reason": ""}, {"reason": "   "}])
    def test_reject_without_a_reason_fails(self, pending, verifier, payload):
        url = reverse("accounts:licence-reject", args=[pending.pk])
        assert authenticated_client(verifier).post(url, payload).status_code == 400
        pending.refresh_from_db()
        assert pending.status == Licence.Status.PENDING_VERIFICATION

    def test_only_pending_licences_can_be_decided(self, pending, verifier):
        client = authenticated_client(verifier)
        client.post(reverse("accounts:licence-approve", args=[pending.pk]))
        again = client.post(reverse("accounts:licence-reject", args=[pending.pk]), {"reason": "x"})
        assert again.status_code == 400

    def test_unknown_licence_is_404(self, verifier):
        url = reverse("accounts:licence-approve", args=[999999])
        assert authenticated_client(verifier).post(url).status_code == 404


class TestSignedImageLinks:
    """SI-3: images only through signed links that expire within 15 minutes."""

    def test_link_serves_the_image_then_expires(self, api_client, customer_client):
        url = _submit(customer_client).json()["front_image_url"]
        response = api_client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        with freeze_time(timezone.now() + timedelta(seconds=901)):
            assert api_client.get(url).status_code == 404

    def test_tampered_link_is_404(self, api_client, customer_client):
        url = _submit(customer_client).json()["front_image_url"]
        assert api_client.get(url[:-3] + "abc/").status_code == 404
