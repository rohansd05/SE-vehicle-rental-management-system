"""Deterministic in-memory payment gateway for development and tests.

- State is shared by every instance in a process, as a real gateway's is.
  Transaction ids are unique: mock_txn_ plus 12 hex digits.
- A mock_txn_ id this process has not seen was authorised by another
  process (seed_demo, or the server before a restart): it is accepted, with
  the capture and refund limits counted from then on.
- The token DECLINE_TOKEN is always declined, to exercise the
  "declined -> hold retained" branch of the Book Vehicle sequence (Exp 4).
- Repeating a call with the same idempotency key returns the first response.
- Amounts must be Decimal (CO-6); a float raises TypeError.
- Notifications are signed with HMAC-SHA256 of the body under
  settings.PAYMENT_WEBHOOK_SECRET (sign() makes test notifications).
"""

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

from .interface import GatewayResponse, PaymentGateway

PREFIX = "mock_txn_"


@dataclass
class _Transaction:
    authorized: Decimal
    captured: Decimal = Decimal("0")
    refunded: Decimal = Decimal("0")


class MockPaymentGateway(PaymentGateway):
    DECLINE_TOKEN = "tok_decline"

    _transactions: dict[str, _Transaction] = {}
    _responses: dict[tuple[str, str], GatewayResponse] = {}

    @classmethod
    def reset(cls) -> None:
        """Forget every transaction and response (tests)."""
        cls._transactions.clear()
        cls._responses.clear()

    @staticmethod
    def sign(payload: bytes) -> str:
        secret = settings.PAYMENT_WEBHOOK_SECRET.encode()
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()

    def verify_notification(self, payload: bytes, signature: str) -> bool:
        return bool(signature) and hmac.compare_digest(self.sign(payload), signature)

    @staticmethod
    def _check_amount(amount: Decimal) -> None:
        if not isinstance(amount, Decimal):
            raise TypeError("Monetary amounts must be Decimal, never float (CO-6).")
        if amount <= 0:
            raise ValueError("Amount must be positive.")

    def _remember(self, operation: str, key: str, response: GatewayResponse) -> GatewayResponse:
        self._responses[(operation, key)] = response
        return response

    def _find(self, transaction_id: str) -> _Transaction | None:
        if transaction_id not in self._transactions and transaction_id.startswith(PREFIX):
            self._transactions[transaction_id] = _Transaction(authorized=Decimal("Infinity"))
        return self._transactions.get(transaction_id)

    def authorize(
        self, amount: Decimal, currency: str, payment_token: str, idempotency_key: str
    ) -> GatewayResponse:
        if ("authorize", idempotency_key) in self._responses:
            return self._responses[("authorize", idempotency_key)]
        self._check_amount(amount)
        if payment_token == self.DECLINE_TOKEN:
            response = GatewayResponse(False, "", amount, "Declined by mock gateway.")
            return self._remember("authorize", idempotency_key, response)
        transaction_id = f"{PREFIX}{uuid.uuid4().hex[:12]}"
        self._transactions[transaction_id] = _Transaction(authorized=amount)
        response = GatewayResponse(True, transaction_id, amount, "Authorized.")
        return self._remember("authorize", idempotency_key, response)

    def capture(
        self, transaction_id: str, amount: Decimal, idempotency_key: str
    ) -> GatewayResponse:
        if ("capture", idempotency_key) in self._responses:
            return self._responses[("capture", idempotency_key)]
        self._check_amount(amount)
        txn = self._find(transaction_id)
        if txn is None:
            response = GatewayResponse(False, transaction_id, amount, "Unknown transaction.")
        elif amount > txn.authorized - txn.captured:
            response = GatewayResponse(False, transaction_id, amount, "Exceeds authorized amount.")
        else:
            txn.captured += amount
            response = GatewayResponse(True, transaction_id, amount, "Captured.")
        return self._remember("capture", idempotency_key, response)

    def refund(self, transaction_id: str, amount: Decimal, idempotency_key: str) -> GatewayResponse:
        if ("refund", idempotency_key) in self._responses:
            return self._responses[("refund", idempotency_key)]
        self._check_amount(amount)
        txn = self._find(transaction_id)
        if txn is None:
            response = GatewayResponse(False, transaction_id, amount, "Unknown transaction.")
        elif amount > txn.captured - txn.refunded:
            response = GatewayResponse(False, transaction_id, amount, "Exceeds captured amount.")
        else:
            txn.refunded += amount
            response = GatewayResponse(True, f"rfnd_{uuid.uuid4().hex[:12]}", amount, "Refunded.")
        return self._remember("refund", idempotency_key, response)
