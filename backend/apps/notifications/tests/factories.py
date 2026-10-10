"""factory-boy factories for notifications."""

import factory

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    recipient = factory.SubFactory(UserFactory)
    channel = Notification.Channel.EMAIL
    destination = factory.SelfAttribute("recipient.email")
    template = "booking_confirmed"
    context = factory.LazyFunction(lambda: {"booking_reference": "VRMS-20261010-0001"})
