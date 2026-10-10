"""Notification delivery log (SRS 3.8; SI-2).

Owner: Rohan (WBS 1.4.5). Only the owner edits this file or its migrations.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Notification(TimeStampedModel):
    """One outbound message and its delivery status (SI-2.2).

    The message body is not stored: `context` holds the template variables,
    and must never contain an OTP code, password or card detail (SE-2, CO-2).
    """

    class Channel(models.TextChoices):
        EMAIL = "Email", "Email"
        SMS = "SMS", "SMS"
        PUSH = "Push", "Push"

    class Status(models.TextChoices):  # values proposed; SI-2.2 names none
        QUEUED = "Queued", "Queued"
        SENT = "Sent", "Sent"
        DELIVERED = "Delivered", "Delivered"
        FAILED = "Failed", "Failed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notifications"
    )
    channel = models.CharField(max_length=8, choices=Channel.choices)
    destination = models.CharField(max_length=254, help_text="E-mail, mobile or device token.")
    # SI-2.1: versioned message templates.
    template = models.CharField(max_length=100)
    template_version = models.PositiveSmallIntegerField(default=1)
    context = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    provider_message_id = models.CharField(max_length=128, blank=True)
    error = models.CharField(max_length=255, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="notifications",
    )
    queued_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-queued_at"]
        indexes = [models.Index(fields=["status", "queued_at"])]

    def __str__(self) -> str:
        return f"{self.channel} '{self.template}' to {self.destination} ({self.status})"
