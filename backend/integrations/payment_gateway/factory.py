"""Pick the payment gateway implementation from settings.PAYMENT_GATEWAY_BACKEND."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .interface import PaymentGateway

BACKENDS = {
    "mock": "integrations.payment_gateway.mock.MockPaymentGateway",
}


def get_payment_gateway() -> PaymentGateway:
    name = settings.PAYMENT_GATEWAY_BACKEND
    try:
        path = BACKENDS[name]
    except KeyError as exc:
        raise ImproperlyConfigured(
            f"Unknown PAYMENT_GATEWAY_BACKEND {name!r}; expected one of {sorted(BACKENDS)}."
        ) from exc
    return import_string(path)()
