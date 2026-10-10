"""Role permissions and object scoping, enforced on the server (SE-4, CO-3).

Role classes answer "may this kind of user call this endpoint?". The scoping
helpers answer "may this user see this record?" (SE-5, History.Privacy,
Report.Access):

- a Customer sees only their own records;
- Branch Staff and Branch Managers see only records of their own branch;
- an Administrator sees everything.

Every view still declares permission_classes explicitly; combine roles with
DRF's operators, e.g. ``permission_classes = [IsBranchStaff | IsAdministrator]``.
"""

from django.db.models import QuerySet
from rest_framework.permissions import BasePermission

from apps.accounts.models import User

Role = User.Role


class HasRole(BasePermission):
    """Authenticated, active, holding one of `allowed_roles` and its profile."""

    allowed_roles: tuple[str, ...] = ()
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role in self.allowed_roles
            and self.has_profile(user)
        )

    def has_profile(self, user) -> bool:
        return True


class IsCustomer(HasRole):
    allowed_roles = (Role.CUSTOMER,)

    def has_profile(self, user) -> bool:
        return hasattr(user, "customer")


class IsBranchStaff(HasRole):
    allowed_roles = (Role.BRANCH_STAFF,)

    def has_profile(self, user) -> bool:
        return hasattr(user, "branch_staff")


class IsMaintenanceTechnician(HasRole):
    allowed_roles = (Role.MAINTENANCE_TECHNICIAN,)

    def has_profile(self, user) -> bool:
        return hasattr(user, "maintenance_technician")


class IsAdministrator(HasRole):
    allowed_roles = (Role.ADMINISTRATOR,)


class IsBranchManager(HasRole):
    allowed_roles = (Role.BRANCH_MANAGER,)

    def has_profile(self, user) -> bool:
        return branch_id_of(user) is not None


# ─── Object scoping ───────────────────────────────────────────────────────


def branch_id_of(user) -> int | None:
    """The branch a staff member or branch manager is limited to."""
    if user.role == Role.BRANCH_STAFF and hasattr(user, "branch_staff"):
        return user.branch_staff.branch_id
    if user.role == Role.BRANCH_MANAGER and hasattr(user, "administrator"):
        manager = getattr(user.administrator, "branchmanager", None)
        return manager.branch_id if manager is not None else None
    return None


def customer_id_of(user) -> int | None:
    if user.role == Role.CUSTOMER and hasattr(user, "customer"):
        return user.customer.pk
    return None


def _resolve(obj, lookup: str):
    value = obj
    for part in lookup.split("__"):
        value = getattr(value, part)
        if value is None:
            return None
    return value


def can_access(user, obj, *, customer_lookup: str | None = None, branch_lookup: str | None = None):
    """Object-level rule. Lookups are ORM-style paths ending in an id, e.g.
    ``customer_lookup="booking__customer_id"``, ``branch_lookup="pickup_branch_id"``."""
    if not (user and user.is_authenticated and user.is_active):
        return False
    if user.role == Role.ADMINISTRATOR:
        return True
    if user.role == Role.CUSTOMER and customer_lookup:
        own = customer_id_of(user)
        return own is not None and _resolve(obj, customer_lookup) == own
    if user.role in (Role.BRANCH_STAFF, Role.BRANCH_MANAGER) and branch_lookup:
        branch = branch_id_of(user)
        return branch is not None and _resolve(obj, branch_lookup) == branch
    return False


def scope_queryset(
    queryset: QuerySet,
    user,
    *,
    customer_lookup: str | None = None,
    branch_lookup: str | None = None,
) -> QuerySet:
    """Filter `queryset` to what `user` may see (same rules as can_access)."""
    if not (user and user.is_authenticated and user.is_active):
        return queryset.none()
    if user.role == Role.ADMINISTRATOR:
        return queryset
    if user.role == Role.CUSTOMER and customer_lookup:
        own = customer_id_of(user)
        return queryset.filter(**{customer_lookup: own}) if own else queryset.none()
    if user.role in (Role.BRANCH_STAFF, Role.BRANCH_MANAGER) and branch_lookup:
        branch = branch_id_of(user)
        return queryset.filter(**{branch_lookup: branch}) if branch else queryset.none()
    return queryset.none()


class ScopedObjectPermission(BasePermission):
    """Object permission using the view's `customer_lookup` / `branch_lookup`."""

    def has_object_permission(self, request, view, obj) -> bool:
        return can_access(
            request.user,
            obj,
            customer_lookup=getattr(view, "customer_lookup", None),
            branch_lookup=getattr(view, "branch_lookup", None),
        )
