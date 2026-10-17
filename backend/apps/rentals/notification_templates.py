"""Rentals message templates (SI-2.1), registered by RentalsConfig.ready().

They join apps.notifications.templates.TEMPLATES at start-up, so the
notifications app needs no rentals-specific edits. Add a new version rather
than editing one that has been sent.
"""

from apps.notifications.templates import Template

TEMPLATES: dict[tuple[str, int], Template] = {
    # Handover.Sign: "shall e-mail a copy to the customer"; Exp 2 UC 7 step 5.
    ("handover_report", 1): Template(
        subject="{agency}: your signed handover report for {reference}",
        body=(
            "Hello {name},\n\n"
            "You collected {vehicle} ({registration_no}) at our {branch} branch on "
            "{handed_over_at}. This is a copy of the condition report you signed.\n\n"
            "Booking: {reference}\n"
            "Odometer: {odometer} km\n"
            "Fuel or charge: {fuel_level}%\n"
            "Accessories issued: {accessories}\n"
            "Existing damage: {damage}\n"
            "Photographs: {photo_count}\n"
            "Recorded by: {staff}\n\n"
            "Please return the vehicle by {return_at}.\n\n{agency}"
        ),
    ),
}


# Every variable the templates above use, for tests that render all templates.
SAMPLE_CONTEXT = {
    "name": "Demo Customer",
    "reference": "VRMS-20261016-0001",
    "vehicle": "Maruti Suzuki Baleno",
    "registration_no": "MH02DH3001",
    "branch": "Andheri",
    "handed_over_at": "16 Oct 2026 10:05",
    "return_at": "16 Oct 2026 21:00",
    "odometer": 12000,
    "fuel_level": "75",
    "accessories": "Child seat x1",
    "damage": "Scratch on the rear bumper",
    "photo_count": 4,
    "staff": "Demo Branch Staff",
}


def register() -> None:
    from apps.notifications.templates import TEMPLATES as ALL

    for key, template in TEMPLATES.items():
        ALL.setdefault(key, template)
