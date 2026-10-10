"""BranchStaff and BranchManager (Exp 3; SRS 2.2)."""

import pytest
from django.db.models import ProtectedError

from apps.accounts.models import Administrator
from apps.accounts.tests.factories import BranchManagerFactory, BranchStaffFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "factory_class", [BranchStaffFactory, BranchManagerFactory], ids=lambda f: f.__name__
)
def test_factory_creates_a_valid_row(factory_class):
    instance = factory_class()
    instance.full_clean()
    assert instance.pk is not None
    assert str(instance)


def test_staff_belong_to_a_branch():
    staff = BranchStaffFactory()
    assert list(staff.branch.staff.all()) == [staff]
    assert staff.staff_id


def test_branch_manager_is_an_administrator():
    manager = BranchManagerFactory()
    administrator = Administrator.objects.get(pk=manager.admin_id)
    assert administrator.branchmanager == manager
    assert manager.user.administrator.branchmanager.branch == manager.branch


def test_branch_with_staff_cannot_be_deleted():
    """Branch ◇ BranchStaff: PROTECT."""
    with pytest.raises(ProtectedError):
        BranchStaffFactory().branch.delete()
