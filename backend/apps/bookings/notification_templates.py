"""Booking-change message templates (SI-2.1), registered by BookingsConfig.ready().

Notify.Booking: the customer is told of a modification, extension,
cancellation and no-show, with the booking reference and the resulting
status. Exp 2 UC 4 step 6 and Book.Cancel.Release: the branch is told of a
modification or cancellation. E-mail only; the SMS copy of Notify.Booking is
Module R3. Add a new version rather than editing one that has been sent.
"""

from apps.notifications.templates import Template

TEMPLATES: dict[tuple[str, int], Template] = {
    ("booking_modified", 1): Template(
        subject="{agency}: booking {reference} has been changed",
        body=(
            "Hello {name},\n\n"
            "Your booking {reference} has been changed. You collect {vehicle} "
            "({registration_no}) at our {branch} branch on {pickup} and return it by "
            "{return_at}.\n{money}\n\nStatus: {status}\n\n{agency}"
        ),
    ),
    ("booking_cancelled", 1): Template(
        subject="{agency}: booking {reference} has been cancelled",
        body=(
            "Hello {name},\n\n"
            "Your booking {reference} for {vehicle} on {pickup} has been cancelled.\n"
            "{refund}\n\nStatus: {status}\n\n{agency}"
        ),
    ),
    ("booking_extended", 1): Template(
        subject="{agency}: booking {reference} has been extended",
        body=(
            "Hello {name},\n\n"
            "Your rental {reference} of {vehicle} ({registration_no}) now ends on "
            "{return_at}. Please return it to our {branch} branch by then.\n{money}\n\n"
            "Status: {status}\n\n{agency}"
        ),
    ),
    ("booking_no_show", 1): Template(
        subject="{agency}: booking {reference} was not collected",
        body=(
            "Hello {name},\n\n"
            "{vehicle} for booking {reference} was not collected within two hours of the "
            "pickup time ({pickup}), so the booking has been closed as a no-show.\n"
            "{refund}\n\nStatus: {status}\n\n{agency}"
        ),
    ),
    ("booking_branch_update", 1): Template(
        subject="{agency}: booking {reference} is now {status}",
        body=(
            "Hello {name},\n\n"
            "Booking {reference}: {vehicle} ({registration_no}), collected at {branch} on "
            "{pickup}, returned by {return_at}. Status: {status}.\n\n{agency}"
        ),
    ),
}


# Every variable the templates above use, for tests that render all templates.
SAMPLE_CONTEXT = {
    "name": "Demo Customer",
    "reference": "VRMS-20261020-0001",
    "vehicle": "Tata Tiago",
    "registration_no": "MH02DR5001",
    "branch": "Andheri",
    "pickup": "22 Oct 2026 10:00",
    "return_at": "24 Oct 2026 10:00",
    "status": "Confirmed",
    "money": "We have charged the extra INR 500.00.",
    "refund": "We are refunding INR 6,800.00.",
}


def register() -> None:
    from apps.notifications.templates import TEMPLATES as ALL

    for key, template in TEMPLATES.items():
        ALL.setdefault(key, template)
