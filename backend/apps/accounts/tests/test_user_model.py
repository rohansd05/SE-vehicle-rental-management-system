"""Minimal custom user (Phase 0)."""

import pytest

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_create_user_uses_email_as_username_and_defaults_to_customer():
    user = User.objects.create_user(
        email="Asha@Example.COM", password="Str0ng!Passw0rd", name="Asha", mobile_no="+919800000001"
    )
    assert user.get_username() == "Asha@example.com"
    assert user.role == User.Role.CUSTOMER
    assert user.is_active
    assert not user.is_staff
    assert not user.is_superuser


def test_create_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="x", name="No Email", mobile_no="1")


def test_create_superuser_is_staff_superuser_administrator():
    admin = User.objects.create_superuser(
        email="admin@vrms.test", password="Str0ng!Passw0rd", name="Admin", mobile_no="+919800000002"
    )
    assert admin.is_staff
    assert admin.is_superuser
    assert admin.role == User.Role.ADMINISTRATOR


def test_create_superuser_rejects_is_staff_false():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="bad@vrms.test", password="x", name="Bad", mobile_no="1", is_staff=False
        )


def test_create_superuser_rejects_is_superuser_false():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="bad2@vrms.test", password="x", name="Bad", mobile_no="1", is_superuser=False
        )


def test_role_choices_match_srs_user_classes():
    assert [label for _, label in User.Role.choices] == [
        "Customer",
        "Branch Staff",
        "Maintenance Technician",
        "Administrator",
        "Branch Manager",
    ]


def test_factory_builds_a_valid_user():
    user = UserFactory()
    assert str(user) == user.email
    assert user.check_password("Test@12345")
