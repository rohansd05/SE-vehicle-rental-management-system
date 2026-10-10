"""Versioned message templates (SI-2.1).

A Notification row stores the template name and version plus its context;
the text is rendered only when the message is sent. The agency name always
comes from settings (D7). Add a new version rather than editing one that
has been used, so old Notification rows still describe what was sent.
"""

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class Template:
    subject: str
    body: str


TEMPLATES: dict[tuple[str, int], Template] = {
    # SE-7, CI-5. {code} is supplied only at send time and never stored.
    ("otp", 1): Template(
        subject="",
        body=(
            "{agency}: {code} is your verification code. It expires in {minutes} minutes. "
            "Never share it with anyone."
        ),
    ),
    # SE-8: notify the registered e-mail address of a lockout.
    ("account_locked", 1): Template(
        subject="{agency}: your account has been locked",
        body=(
            "Hello {name},\n\n"
            "After {attempts} consecutive failed sign-in attempts we have locked your account "
            "for {minutes} minutes. If this was not you, change your password once the lock "
            "ends.\n\n{agency}"
        ),
    ),
    # Licence verification decisions (SE-10 audits them; the customer is told).
    ("licence_approved", 1): Template(
        subject="{agency}: your driving licence has been verified",
        body=(
            "Hello {name},\n\n"
            "Your driving licence {licence_number} has been verified. You can now book "
            "vehicles in the categories it covers.\n\n{agency}"
        ),
    ),
    ("licence_rejected", 1): Template(
        subject="{agency}: your driving licence could not be verified",
        body=(
            "Hello {name},\n\n"
            "We could not verify your driving licence {licence_number}.\n"
            "Reason: {reason}\n\n"
            "You can submit it again from your profile.\n\n{agency}"
        ),
    ),
}


def render(name: str, version: int, context: dict) -> tuple[str, str]:
    template = TEMPLATES[(name, version)]
    values = {"agency": settings.AGENCY_NAME, **context}
    return template.subject.format(**values), template.body.format(**values)
