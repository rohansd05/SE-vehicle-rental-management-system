"""Load the Exp 8 / Exp 10 Booking demo scenarios (fictitious; apps/bookings/seed_scenarios.py).

Run after `seed_demo` and `seed_demo --reports`. Running it again creates nothing.
"""

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bookings.seed_scenarios import EMAILS, seed_booking_scenarios
from apps.core.management.commands.seed_demo import DEMO_PASSWORD


class Command(BaseCommand):
    help = (
        "Load DEMO data for the Booking scenarios of Exp 8 and Exp 10 (BR-8 refund slabs, "
        "BR-2 under-21 refusal, SE-8 lockout account). Run after seed_demo. Idempotent."
    )

    def handle(self, *args, **options):
        self.created: dict[str, int] = {}
        try:
            with transaction.atomic():
                seed_booking_scenarios(self._count)
        except ObjectDoesNotExist as exc:
            raise CommandError(f"Run `python manage.py seed_demo` first ({exc}).") from exc
        created = ", ".join(f"{n} {label}" for label, n in self.created.items()) or "nothing"
        self.stdout.write(self.style.SUCCESS(f"Booking scenarios ready. Created: {created}."))
        self.stdout.write(f"Demo accounts use the password {DEMO_PASSWORD}: ")
        self.stdout.write("  " + ", ".join(EMAILS))

    def _count(self, label: str, created: bool) -> None:
        if created:
            self.created[label] = self.created.get(label, 0) + 1
