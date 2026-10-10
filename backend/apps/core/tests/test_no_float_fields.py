"""CO-6: no floating-point column anywhere in the schema."""

from django.apps import apps
from django.db import models


def test_no_installed_model_has_a_float_field():
    offenders = [
        f"{model._meta.label}.{field.name}"
        for model in apps.get_models()
        for field in model._meta.get_fields()
        if isinstance(field, models.FloatField)
    ]
    assert offenders == []
