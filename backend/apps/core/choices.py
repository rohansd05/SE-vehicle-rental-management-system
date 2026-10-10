"""Choices shared by more than one app."""

from django.db import models


class VehicleType(models.TextChoices):
    """The two vehicle types the agency offers (Exp 3: Car, TwoWheeler).

    Also the licence categories: BR-2 and BR-3 distinguish only these two.
    """

    CAR = "Car", "Car"
    TWO_WHEELER = "Two-Wheeler", "Two-Wheeler"


class FuelType(models.TextChoices):
    """Search.Filter fuel type. Values are proposed (see docs/model-mapping.md)."""

    PETROL = "Petrol", "Petrol"
    DIESEL = "Diesel", "Diesel"
    CNG = "CNG", "CNG"
    ELECTRIC = "Electric", "Electric"
