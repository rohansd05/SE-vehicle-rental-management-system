"""Booking background jobs (Celery)."""

from celery import shared_task
from django.db import transaction


@shared_task
def release_expired_holds() -> int:
    """Book.Hold.Expire: return expired Pending Payment holds to Draft (scheduled every minute)."""
    from .lifecycle import release_expired_holds as release

    with transaction.atomic():
        return release()


@shared_task
def declare_no_shows() -> int:
    """Appendix B No-show: uncollected bookings NO_SHOW_AFTER past pickup (every minute, 0005)."""
    from .services import declare_no_shows as declare

    with transaction.atomic():
        return declare()
