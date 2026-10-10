"""Fleet models: branches, vehicles and their documents (SRS 3.7, Appendix A).

Vehicle is a concrete base (Exp 3 «interface» Vehicle); Car and TwoWheeler
are multi-table children, so every booking points at the single vehicle
table. Mappings and SRS additions are listed in docs/model-mapping.md.

Owner: Rohan (WBS 1.4.1); fleet/services/availability.py is Nidhi's.
"""

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q

from apps.core.choices import FuelType, VehicleType
from apps.core.models import TimeStampedModel

pincode_validator = RegexValidator(r"^[0-9]{6}$", "A pincode is six digits.")


class Branch(TimeStampedModel):
    """Exp 3 Branch. serviceable_areas is the reverse of BranchServiceableArea."""

    branch_id = models.BigAutoField(primary_key=True)
    branch_name = models.CharField(max_length=100, unique=True)
    address = models.TextField()

    class Meta:
        ordering = ["branch_name"]
        verbose_name_plural = "branches"

    def __str__(self) -> str:
        return self.branch_name


class BranchServiceableArea(models.Model):
    """One serviceable pincode/locality of a branch (Book.Deliver.Location).

    Exp 3 Branch.serviceable_areas is a list; one row per area keeps the
    schema in third normal form (CO-5).
    """

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="serviceable_areas")
    pincode = models.CharField(max_length=6, validators=[pincode_validator])
    locality = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["branch", "pincode"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "pincode", "locality"], name="fleet_serviceablearea_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.branch}: {self.pincode} {self.locality}".strip()


class VehicleCategory(TimeStampedModel):
    """Appendix A "vehicle category" (e.g. Hatchback, SUV, Scooter).

    A table rather than fixed choices: Fleet.Tariff defines rates per
    category, Search.Filter and the reports group by it, and the SRS does not
    enumerate the categories, so they are master data the Administrator
    maintains.
    """

    name = models.CharField(max_length=64, unique=True)
    vehicle_type = models.CharField(max_length=16, choices=VehicleType.choices)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["vehicle_type", "name"]
        verbose_name_plural = "vehicle categories"

    def __str__(self) -> str:
        return f"{self.name} ({self.vehicle_type})"


class Vehicle(TimeStampedModel):
    """Exp 3 «interface» Vehicle as a concrete base; Fleet.Add attributes."""

    class Status(models.TextChoices):
        AVAILABLE = "Available", "Available"
        ON_RENT = "On Rent", "On Rent"
        UNDER_MAINTENANCE = "Under Maintenance", "Under Maintenance"
        UNSAFE = "Unsafe", "Unsafe"
        RETIRED = "Retired", "Retired"

    registration_no = models.CharField(max_length=16, unique=True)
    brand = models.CharField(max_length=64)
    model = models.CharField(max_length=64)
    # Appendix A: whole kilometres; may never decrease (Return.Odometer).
    odometer = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.AVAILABLE)
    # Fleet.Add attributes not in the class diagram:
    category = models.ForeignKey(VehicleCategory, on_delete=models.PROTECT, related_name="vehicles")
    # Branch ◇ Vehicle (Exp 3 aggregation); "home branch" in Fleet.Add.
    home_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="vehicles")
    year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1990), MaxValueValidator(2100)]
    )
    colour = models.CharField(max_length=32)
    fuel_type = models.CharField(max_length=16, choices=FuelType.choices)  # Search.Filter
    chassis_number = models.CharField(max_length=32, unique=True)
    available_from = models.DateField()  # Fleet.Add availability date
    # Maint.Complete, Search.Detail, BR-15: last completed service.
    last_service_date = models.DateField(null=True, blank=True)
    last_service_odometer = models.PositiveIntegerField(null=True, blank=True)
    # Proposed: tank (litres/kg) or battery (kWh) capacity, needed to turn a
    # fuel-level shortfall into a quantity for BR-12.
    fuel_capacity = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["registration_no"]
        indexes = [models.Index(fields=["home_branch", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(last_service_odometer__isnull=True)
                | Q(last_service_odometer__lte=F("odometer")),
                name="fleet_vehicle_service_odometer_not_ahead",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.registration_no} {self.brand} {self.model}"

    @property
    def vehicle_type(self) -> str:
        """Appendix A "vehicle type", derived from the category."""
        return self.category.vehicle_type


class Car(Vehicle):
    """Exp 3 Car."""

    class Transmission(models.TextChoices):
        MANUAL = "Manual", "Manual"
        AUTOMATIC = "Automatic", "Automatic"

    seating_capacity = models.PositiveSmallIntegerField()
    transmission = models.CharField(max_length=16, choices=Transmission.choices)

    def __str__(self) -> str:
        return f"Car {super().__str__()}"


class TwoWheeler(Vehicle):
    """Exp 3 TwoWheeler."""

    engine_cc = models.PositiveIntegerField()

    def __str__(self) -> str:
        return f"Two-wheeler {super().__str__()}"


class VehicleDocument(TimeStampedModel):
    """A statutory document of a vehicle (Fleet.Add, SA-3, Handover.Refuse).

    A renewal is a new row, so the history is kept.
    """

    class DocumentType(models.TextChoices):
        INSURANCE = "Insurance", "Insurance"
        POLLUTION = "Pollution Certificate", "Pollution Certificate"
        FITNESS = "Fitness Certificate", "Fitness Certificate"
        ROAD_TAX = "Road Tax", "Road Tax"

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=32, choices=DocumentType.choices)
    document_number = models.CharField(max_length=64, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()  # Fleet.Add: expiry date of each document
    file = models.FileField(upload_to="vehicles/documents/", blank=True)  # SI-3

    class Meta:
        ordering = ["vehicle", "document_type", "-expiry_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_from__isnull=True) | Q(expiry_date__gte=F("valid_from")),
                name="fleet_vehicledocument_valid_period",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.vehicle.registration_no} {self.document_type} (expires {self.expiry_date})"


class VehiclePhoto(models.Model):
    """Fleet.Add / Search.Detail: at least four photographs per vehicle.

    SI-3: only the object key is stored in the database.
    """

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="photos")
    image = models.FileField(upload_to="vehicles/photos/")
    position = models.PositiveSmallIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["vehicle", "position"]

    def __str__(self) -> str:
        return f"Photo {self.position} of {self.vehicle.registration_no}"
