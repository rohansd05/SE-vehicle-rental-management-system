"""Maintenance background jobs (Celery), scheduled daily by migration 0004."""

from celery import shared_task


@shared_task
def raise_preventive_jobs() -> int:
    """Maint.Auto.Time (BR-15, evaluated daily) with the service-due alert."""
    from .services import raise_due_preventive_jobs

    return raise_due_preventive_jobs()


@shared_task
def alert_expiring_documents() -> int:
    """The context diagram's document expiry alert to the Administrators (SA-3)."""
    from .services import alert_expiring_documents as alert

    return alert()
