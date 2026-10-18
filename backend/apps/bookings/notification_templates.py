"""Booking-change message templates (SI-2.1), registered by BookingsConfig.ready().

Notify.Booking: the customer is told of a modification, extension,
cancellation and no-show, with the booking reference and the resulting
status. Exp 2 UC 4 step 6 and Book.Cancel.Release: the branch is told of a
modification or cancellation. Module R3 added the SMS copies of Notify.Booking,
Book.Done.Customer and Notify.Remind; Book.Done.Branch reuses booking_branch_update.
Add a new version rather than editing one that has been sent.
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
    # Module R3. {pickup_code} is read from the booking at send time and never stored.
    # Book.Done.Customer, CI-6: the booking, the price and the collection details.
    ("booking_confirmed", 1): Template(
        subject="{agency}: booking {reference} is confirmed",
        body=(
            "Hello {name},\n\n"
            "Your booking {reference} is confirmed. You collect {vehicle} ({registration_no}) "
            "at our {branch} branch on {pickup} and return it by {return_at}.\n\n"
            "Price:\n{price}\n\n"
            "Collection: our {branch} branch, {branch_address}, on {pickup}. Please bring "
            "{documents}. Your six-digit pickup code is sent to you by SMS.\n\n"
            "Status: {status}\n\n{agency}"
        ),
    ),
    # Book.Done.Customer, CI-5: the booking reference and the pickup code by SMS.
    ("booking_confirmed_sms", 1): Template(
        subject="",
        body=(
            "{agency}: booking {reference} is {status}. Pickup code {pickup_code}. "
            "Collect {vehicle} at {branch} on {pickup}."
        ),
    ),
    # Notify.Remind: the branch, the time, the pickup code and the documents to bring.
    ("pickup_reminder", 1): Template(
        subject="{agency}: reminder, you collect {vehicle} on {pickup}",
        body=(
            "Hello {name},\n\n"
            "A reminder that you collect {vehicle} ({registration_no}) for booking {reference} "
            "at our {branch} branch, {branch_address}, on {pickup}.\n"
            "Pickup code: {pickup_code}\n"
            "Please bring {documents}.\n\n"
            "Status: {status}\n\n{agency}"
        ),
    ),
    ("pickup_reminder_sms", 1): Template(
        subject="",
        body=(
            "{agency}: reminder, collect {vehicle} at {branch} on {pickup}. Booking {reference}, "
            "pickup code {pickup_code}. Bring {documents}."
        ),
    ),
    # Notify.Booking: the SMS copies of R2's messages, with the reference and the status.
    ("booking_modified_sms", 1): Template(
        subject="",
        body=(
            "{agency}: booking {reference} has been changed. Collect {vehicle} at {branch} on "
            "{pickup}, return by {return_at}. Status: {status}."
        ),
    ),
    ("booking_cancelled_sms", 1): Template(
        subject="",
        body="{agency}: booking {reference} has been cancelled. {refund} Status: {status}.",
    ),
    ("booking_extended_sms", 1): Template(
        subject="",
        body="{agency}: rental {reference} now ends on {return_at}. {money} Status: {status}.",
    ),
    ("booking_no_show_sms", 1): Template(
        subject="",
        body=(
            "{agency}: booking {reference} was not collected and is closed as a no-show. "
            "{refund} Status: {status}."
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
    "branch_address": "Ground floor, Link Road, Andheri (W), Mumbai 400053",
    "documents": "your driving licence MH02 20150012345",
    "price": "- Rental, 2 days: INR 3,600.00\n- Tax: INR 648.00\nTotal: INR 4,248.00",
    "pickup_code": "135790",
}


def register() -> None:
    from apps.notifications.templates import TEMPLATES as ALL

    for key, template in TEMPLATES.items():
        ALL.setdefault(key, template)
