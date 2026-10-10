"""factory-boy factories for core."""

import factory

from apps.core.models import AuditLog


class AuditLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditLog

    actor = None
    action = "Create"
    entity_type = "fleet.Vehicle"
    entity_id = factory.Sequence(str)
    after = factory.LazyAttribute(lambda o: {"id": o.entity_id})
