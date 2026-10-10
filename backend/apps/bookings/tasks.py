"""Booking background jobs (Celery)."""

from celery import shared_task
from django.db import transaction


@shared_task
def release_expired_holds() -> int:
    """Book.Hold.Expire: return expired Pending Payment holds to Draft (scheduled every minute)."""
    from .lifecycle import release_expired_holds as release

    with transaction.atomic():
        return release()
