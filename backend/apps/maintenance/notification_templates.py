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
    # Send Maintenance Alert (SRS 3.6.2, DFD 7.3): a Preventive job raised by BR-15.
    ("maintenance_service_due", 1): Template(
        subject="{agency}: preventive service due for vehicle {registration_no}",
        body=(
            "Hello {name},\n\n"
            "Vehicle {registration_no} has reached its preventive service interval (BR-15): "
            "due at {due}. Its odometer reads {odometer} km.\n"
            "Preventive maintenance job {job_id} has been raised; schedule it and assign a "
            "technician.\n\n{agency}"
        ),
    ),
    # Context diagram "document expiry alert" (SA-3).
    ("vehicle_documents_expiring", 1): Template(
        subject="{agency}: {count} vehicle documents expired or expiring",
        body=(
            "Hello {name},\n\n"
            "These statutory documents have expired or expire soon. A vehicle cannot be "
            "handed over unless each is valid for the whole rental (SA-3):\n"
            "{documents}\n\nRecord the renewals on the fleet screen.\n\n{agency}"
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
    "due": "25,000 km or 01 Apr 2027, whichever comes first",
    "odometer": "25,120",
    "count": 2,
    "documents": "- MH01AB1234: Insurance expires on 01 Nov 2026",
}


def register() -> None:
    from apps.notifications.templates import TEMPLATES as ALL

    for key, template in TEMPLATES.items():
        ALL.setdefault(key, template)
