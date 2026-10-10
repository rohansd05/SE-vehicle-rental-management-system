"""Maintenance message templates (SI-2.1), registered by MaintenanceConfig.ready().

They join apps.notifications.templates.TEMPLATES at start-up, so the
notifications app needs no maintenance-specific edits. Add a new version
rather than editing one that has been sent.
"""

from apps.notifications.templates import Template

TEMPLATES: dict[tuple[str, int], Template] = {
    # Maint.Schedule: the assigned technician is told about the job.
    ("maintenance_assigned", 1): Template(
        subject="{agency}: maintenance job {job_id} assigned to you",
        body=(
            "Hello {name},\n\n"
            "Maintenance job {job_id} ({job_type}, severity {severity}) on vehicle "
            "{registration_no} has been assigned to you.\n"
            "Problem reported: {problem}\n"
            "Scheduled: {scheduled_from} to {scheduled_to}\n\n{agency}"
        ),
    ),
    # BR-16, Exp 4 sequence 3: an Administrator must clear the Unsafe flag.
    ("maintenance_clearance_requested", 1): Template(
        subject="{agency}: clearance needed for vehicle {registration_no}",
        body=(
            "Hello {name},\n\n"
            "{technician} has completed maintenance job {job_id} on vehicle "
            "{registration_no}, which is flagged Unsafe. Review the work and clear the "
            "flag in the clearance queue before the vehicle can be rented again.\n"
            "Work performed: {work}\n\n{agency}"
        ),
    ),
}


# Every variable the templates above use, for tests that render all templates.
SAMPLE_CONTEXT = {
    "job_id": 7,
    "registration_no": "MH01AB1234",
    "job_type": "Corrective",
    "severity": "High",
    "problem": "Brakes squeal.",
    "scheduled_from": "14 Oct 2026 10:00",
    "scheduled_to": "14 Oct 2026 18:00",
    "technician": "Ravi",
    "work": "Replaced brake pads.",
}


def register() -> None:
    from apps.notifications.templates import TEMPLATES as ALL

    for key, template in TEMPLATES.items():
        ALL.setdefault(key, template)
