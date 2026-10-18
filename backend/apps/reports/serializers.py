"""Reports API serializers: the period asked for, and the report shapes (Decimal strings)."""

from django.utils import timezone
from rest_framework import serializers

from .services import Period


def _money():
    return serializers.DecimalField(max_digits=14, decimal_places=2)


def _hours():
    return serializers.DecimalField(max_digits=12, decimal_places=1)


class PeriodQuerySerializer(serializers.Serializer):
    """UC 14 step 1: the period, as local dates (CO-6). Default: this month to today."""

    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        date_to = attrs.get("date_to") or timezone.localdate()
        date_from = attrs.get("date_from") or date_to.replace(day=1)
        if date_from > date_to:
            raise serializers.ValidationError(
                {"date_to": "The end of the period cannot be before its start."}
            )
        return {"period": Period(date_from, date_to)}


class _Header(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    scope = serializers.CharField(help_text='"All branches", or the Branch Manager\'s branch.')


# ─── Utilisation ──────────────────────────────────────────────────────────


class UtilisationGroupSerializer(serializers.Serializer):
    name = serializers.CharField()
    vehicles = serializers.IntegerField()
    rented_hours = _hours()
    available_hours = _hours()
    utilisation_percent = serializers.DecimalField(max_digits=6, decimal_places=1, allow_null=True)


class UtilisationVehicleSerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField()
    registration_no = serializers.CharField()
    vehicle = serializers.CharField()
    category = serializers.CharField()
    branch = serializers.CharField()
    rented_hours = _hours()
    available_hours = _hours()
    maintenance_days = _hours()
    utilisation_percent = serializers.DecimalField(max_digits=6, decimal_places=1, allow_null=True)


class UtilisationReportSerializer(_Header):
    totals = UtilisationGroupSerializer()
    by_vehicle = UtilisationVehicleSerializer(many=True)
    by_category = UtilisationGroupSerializer(many=True)
    by_branch = UtilisationGroupSerializer(many=True)
    least_utilised = UtilisationVehicleSerializer(many=True)


# ─── Revenue ──────────────────────────────────────────────────────────────


class RevenueTotalsSerializer(serializers.Serializer):
    invoices = serializers.IntegerField()
    rental = _money()
    add_ons = _money()
    discounts = _money()
    tax = _money()
    invoiced = _money()
    debit_notes = _money()
    credit_notes = _money()
    net_revenue = _money()
    refunds_awaiting_approval = _money()
    outstanding_dues = _money()


class RevenueGroupSerializer(serializers.Serializer):
    name = serializers.CharField()
    rental = _money()
    add_ons = _money()
    discounts = _money()
    tax = _money()
    debit_notes = _money()
    credit_notes = _money()
    net_revenue = _money()


class RevenueMethodSerializer(serializers.Serializer):
    method = serializers.CharField()
    charges = _money()
    refunds = _money()
    net = _money()


class RevenueReportSerializer(_Header):
    totals = RevenueTotalsSerializer()
    by_branch = RevenueGroupSerializer(many=True)
    by_category = RevenueGroupSerializer(many=True)
    by_method = RevenueMethodSerializer(many=True)


# ─── Maintenance cost ─────────────────────────────────────────────────────


class MaintenanceCostTotalsSerializer(serializers.Serializer):
    jobs = serializers.IntegerField()
    labour = _money()
    parts = _money()
    total = _money()
    invoices_attached = serializers.IntegerField()


class MaintenanceCostVehicleSerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField()
    registration_no = serializers.CharField()
    vehicle = serializers.CharField()
    branch = serializers.CharField()
    jobs = serializers.IntegerField()
    labour = _money()
    parts = _money()
    total = _money()


class MaintenanceCostJobTypeSerializer(serializers.Serializer):
    job_type = serializers.CharField()
    jobs = serializers.IntegerField()
    automatic = serializers.IntegerField(help_text="Raised by the system (Maint.Auto.Km, .Time).")
    labour = _money()
    parts = _money()
    total = _money()


class MaintenanceCostReportSerializer(_Header):
    totals = MaintenanceCostTotalsSerializer()
    by_vehicle = MaintenanceCostVehicleSerializer(many=True)
    by_job_type = MaintenanceCostJobTypeSerializer(many=True)


# ─── Customers ────────────────────────────────────────────────────────────


class CustomerTotalsSerializer(serializers.Serializer):
    new = serializers.IntegerField()
    active = serializers.IntegerField()
    no_shows = serializers.IntegerField()
    with_dues = serializers.IntegerField()
    dues_total = _money()


class TopCustomerSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    bookings = serializers.IntegerField()
    no_shows = serializers.IntegerField()
    net_revenue = _money()


class CustomerDueSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    outstanding_due = _money()


class CustomerReportSerializer(_Header):
    totals = CustomerTotalsSerializer()
    top = TopCustomerSerializer(many=True)
    with_dues = CustomerDueSerializer(many=True)


# ─── Dashboard ────────────────────────────────────────────────────────────


class StatusCountSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()


class PeriodFiguresSerializer(serializers.Serializer):
    period = serializers.CharField(help_text="today, week (from Monday) or month.")
    bookings = serializers.IntegerField()
    revenue = _money()


class DashboardSerializer(serializers.Serializer):
    scope = serializers.CharField()
    vehicles_by_status = StatusCountSerializer(many=True)
    collections_today = serializers.IntegerField()
    returns_today = serializers.IntegerField()
    overdue_returns = serializers.IntegerField()
    open_maintenance_jobs = serializers.IntegerField()
    periods = PeriodFiguresSerializer(many=True)
