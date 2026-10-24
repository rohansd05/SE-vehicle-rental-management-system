"""Load the Exp 10 Maintenance demo scenarios (fictitious; apps/maintenance/seed_scenarios.py).

Run after `seed_demo`. Running it again creates nothing.
"""

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.maintenance.seed_scenarios import REGISTRATIONS, seed_maintenance_scenarios


class Command(BaseCommand):
    help = (
        "Load DEMO data for the Maintenance scenarios of Exp 10 (BR-15 service due at the "
        "boundaries, TC-M1 to TC-M5): four Powai vehicles. Run after seed_demo. Idempotent."
    )

    def handle(self, *args, **options):
        self.created: dict[str, int] = {}
        try:
            with transaction.atomic():
                seed_maintenance_scenarios(self._count)
        except ObjectDoesNotExist as exc:
            raise CommandError(f"Run `python manage.py seed_demo` first ({exc}).") from exc
        created = ", ".join(f"{n} {label}" for label, n in self.created.items()) or "nothing"
        self.stdout.write(self.style.SUCCESS(f"Maintenance scenarios ready. Created: {created}."))
        self.stdout.write("Demo vehicles at Powai: " + ", ".join(REGISTRATIONS))

    def _count(self, label: str, created: bool) -> None:
        if created:
            self.created[label] = self.created.get(label, 0) + 1
