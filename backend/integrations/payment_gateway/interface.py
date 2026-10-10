"""Payment Gateway interface.

CO-2: card numbers, expiry dates and CVV never reach VRMS. Callers pass only
the opaque token produced by the gateway's hosted fields.
Every call takes an idempotency key, because payment endpoints and webhooks
must be idempotent.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class GatewayResponse:
    success: bool
    transaction_id: str
    amount: Decimal
    message: str = ""


class PaymentGateway(ABC):
    @abstractmethod
    def authorize(
        self, amount: Decimal, currency: str, payment_token: str, idempotency_key: str
    ) -> GatewayResponse:
        """Place a hold for `amount` against the instrument behind `payment_token`."""

    @abstractmethod
    def capture(
        self, transaction_id: str, amount: Decimal, idempotency_key: str
    ) -> GatewayResponse:
        """Capture up to the authorized amount of an earlier authorization."""

    @abstractmethod
    def refund(self, transaction_id: str, amount: Decimal, idempotency_key: str) -> GatewayResponse:
        """Refund up to the captured amount to the original instrument."""
