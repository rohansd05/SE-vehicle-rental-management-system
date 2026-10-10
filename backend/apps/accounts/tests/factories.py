"""factory-boy factories for accounts."""

from datetime import date, timedelta
from functools import cache

import factory
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.accounts.models import (
    Administrator,
    BranchManager,
    BranchStaff,
    Customer,
    Licence,
    LicenceCategory,
    MaintenanceTechnician,
    OneTimePassword,
    User,
)
from apps.core.choices import VehicleType

DEFAULT_PASSWORD = "Test@12345"


@cache
def hash_password(raw: str) -> str:
    """bcrypt at 12 rounds is slow by design (SE-2); hash each raw value once."""
    return make_password(raw)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@vrms.test")
    name = factory.Faker("name")
    mobile_no = factory.Sequence(lambda n: f"+9190000{n:05d}")
    role = User.Role.CUSTOMER
    password = factory.Transformer(DEFAULT_PASSWORD, transform=hash_password)


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    user = factory.SubFactory(UserFactory, role=User.Role.CUSTOMER)
    date_of_birth = date(1995, 6, 15)
    emergency_contact_name = factory.Faker("name")
    emergency_contact_mobile = factory.Sequence(lambda n: f"+9191000{n:05d}")


class MaintenanceTechnicianFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MaintenanceTechnician

    user = factory.SubFactory(UserFactory, role=User.Role.MAINTENANCE_TECHNICIAN)
    workshop = "Agency workshop"


class AdministratorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Administrator

    user = factory.SubFactory(UserFactory, role=User.Role.ADMINISTRATOR, is_staff=True)


class BranchStaffFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BranchStaff

    user = factory.SubFactory(UserFactory, role=User.Role.BRANCH_STAFF)
    branch = factory.SubFactory("apps.fleet.tests.factories.BranchFactory")


class BranchManagerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BranchManager

    user = factory.SubFactory(UserFactory, role=User.Role.BRANCH_MANAGER)
    branch = factory.SubFactory("apps.fleet.tests.factories.BranchFactory")


class LicenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Licence

    customer = factory.SubFactory(CustomerFactory)
    licence_number = factory.Sequence(lambda n: f"MH01 2020{n:07d}")
    issuing_authority = "RTO Mumbai"
    issue_date = date(2020, 1, 1)
    expiry_date = factory.LazyFunction(lambda: date.today() + timedelta(days=3650))
    status = Licence.Status.VERIFIED


class LicenceCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LicenceCategory

    licence = factory.SubFactory(LicenceFactory)
    category = VehicleType.CAR


class OneTimePasswordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OneTimePassword

    user = factory.SubFactory(UserFactory)
    purpose = OneTimePassword.Purpose.REGISTRATION
    destination = factory.SelfAttribute("user.mobile_no")
    code_hash = factory.LazyFunction(lambda: hash_password("123456"))
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=10))
