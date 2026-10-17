"""Payment Gateway interface.

CO-2: card numbers, expiry dates and CVV never reach VRMS. Callers pass only
the opaque token produced by the gateway's hosted fields (card) or hosted
page (UPI, net banking, wallet; D6).
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
        """SI-1.1: place a hold for `amount` against the instrument behind `payment_token`."""

    @abstractmethod
    def capture(
        self, transaction_id: str, amount: Decimal, idempotency_key: str
    ) -> GatewayResponse:
        """SI-1.2: capture up to the authorized amount of an earlier authorization."""

    @abstractmethod
    def refund(self, transaction_id: str, amount: Decimal, idempotency_key: str) -> GatewayResponse:
        """SI-1.3: refund up to the captured amount to the original instrument."""

    @abstractmethod
    def verify_notification(self, payload: bytes, signature: str) -> bool:
        """SI-1.4: True only if `signature` is the gateway's signature of `payload`."""
