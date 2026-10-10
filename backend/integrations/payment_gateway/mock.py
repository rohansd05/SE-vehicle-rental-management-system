"""Deterministic in-memory payment gateway for development and tests.

- Transaction ids are sequential per instance: mock_txn_000001, ...
- The token DECLINE_TOKEN is always declined, to exercise the
  "declined -> hold retained" branch of the Book Vehicle sequence (Exp 4).
- Repeating a call with the same idempotency key returns the first response.
- Amounts must be Decimal (CO-6); a float raises TypeError.
"""

from dataclasses import dataclass
from decimal import Decimal

from .interface import GatewayResponse, PaymentGateway


@dataclass
class _Transaction:
    authorized: Decimal
    captured: Decimal = Decimal("0")
    refunded: Decimal = Decimal("0")


class MockPaymentGateway(PaymentGateway):
    DECLINE_TOKEN = "tok_decline"

    def __init__(self) -> None:
        self._transactions: dict[str, _Transaction] = {}
        self._responses: dict[tuple[str, str], GatewayResponse] = {}
        self._counter = 0

    @staticmethod
    def _check_amount(amount: Decimal) -> None:
        if not isinstance(amount, Decimal):
            raise TypeError("Monetary amounts must be Decimal, never float (CO-6).")
        if amount <= 0:
            raise ValueError("Amount must be positive.")

    def _remember(self, operation: str, key: str, response: GatewayResponse) -> GatewayResponse:
        self._responses[(operation, key)] = response
        return response

    def authorize(
        self, amount: Decimal, currency: str, payment_token: str, idempotency_key: str
    ) -> GatewayResponse:
        if ("authorize", idempotency_key) in self._responses:
            return self._responses[("authorize", idempotency_key)]
        self._check_amount(amount)
        if payment_token == self.DECLINE_TOKEN:
            response = GatewayResponse(False, "", amount, "Declined by mock gateway.")
            return self._remember("authorize", idempotency_key, response)
        self._counter += 1
        transaction_id = f"mock_txn_{self._counter:06d}"
        self._transactions[transaction_id] = _Transaction(authorized=amount)
        response = GatewayResponse(True, transaction_id, amount, "Authorized.")
        return self._remember("authorize", idempotency_key, response)

    def capture(
        self, transaction_id: str, amount: Decimal, idempotency_key: str
    ) -> GatewayResponse:
        if ("capture", idempotency_key) in self._responses:
            return self._responses[("capture", idempotency_key)]
        self._check_amount(amount)
        txn = self._transactions.get(transaction_id)
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
        txn = self._transactions.get(transaction_id)
        if txn is None:
            response = GatewayResponse(False, transaction_id, amount, "Unknown transaction.")
        elif amount > txn.captured - txn.refunded:
            response = GatewayResponse(False, transaction_id, amount, "Exceeds captured amount.")
        else:
            txn.refunded += amount
            response = GatewayResponse(True, transaction_id, amount, "Refunded.")
        return self._remember("refund", idempotency_key, response)
