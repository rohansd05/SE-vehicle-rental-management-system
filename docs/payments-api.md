# Payments services: the public API (Module R1)

For developers of other modules who move money: N2 Return and settlement
(UC 8) calls `capture_charges`, `refund_deposit` and `record_due`; R2
Modify/Cancel/Extend (UC 4) calls `authorize`, `record_booking_ledger`,
`issue_debit_note`, `capture_charges`, `refund_payment` and `refund_deposit`
(`docs/traceability-booking-changes.md`).
Everything here is in `backend/apps/payments/services.py` (owner: Rohan).
Call these functions; never create `Payment`, `LedgerEntry`,
`RefundRequest` or `InvoiceAdjustment` rows yourself (CLAUDE.md: cross-module
calls go through the owner's services).

SRS: 3.4 Pay.*, SI-1.2 to SI-1.4, BR-4, BR-9, BR-14; Exp 2 UC 13 Approve
Refund; Exp 3 `Payment.capture()`, `Payment.refund()`. Traceability:
`docs/traceability-payments.md`.

## Rules that apply to every function

- **Money is `Decimal`** (CO-6). A `float` raises `TypeError`. An amount of
  zero or less raises `PaymentError(code="invalid_amount")`.
- **Refusals raise `services.PaymentError`**, with a stable `.code` and an
  HTTP `.status`. In a DRF view, answer
  `Response({"detail": str(exc), "code": exc.code}, status=exc.status)`, as
  `apps/payments/views.py` `refusal()` does.
- **`initiated_by`** is the signed-in `User` acting, or `None` for a system
  action. It is recorded on every payment, ledger entry and audit entry
  (Pay.Ledger "the user who initiated it"; SE-10).
- **Transactions.** Each function runs in its own `transaction.atomic()` and
  can be called inside yours; a refusal raised inside your transaction rolls
  your work back too. Gateway calls happen inside the transaction (the mock
  gateway never fails half-way; see "Known limits").
- **Idempotency (Pay.Idempotent).** Functions that move money take an
  `idempotency_key`. Calling again with the same key returns the first
  result and never charges or refunds twice. An API endpoint should take the
  key from the client (one per attempt, `^[A-Za-z0-9_-]{8,40}$`).
- **Re-authentication (SE-9).** The services do not check passwords; the
  view must, before calling them. Use
  `apps.payments.reauth.require_password(request, password, entity_label=..., entity_id=...)`.
- **The ledger and invoices are append-only.** Corrections are new rows:
  a credit note for an invoice, an Adjustment entry that references the
  ledger entry it reverses.

## capture_charges

```python
capture_charges(booking, lines, initiated_by, *, idempotency_key=None, request=None)
    -> list[LedgerEntry]
```

SI-1.2: "request the capture of an authorised amount when the rental is
completed and the final charges are known."

- `lines`: a list of `services.ChargeLine(description: str, amount: Decimal)`,
  one per usage-based charge (BR-10 late return, BR-11 excess kilometres,
  BR-12 fuel shortfall, an unreturned accessory, damage). Amounts are what
  the customer pays for that line. An empty list is allowed (a return with
  no extra charges, a cancellation).
- Writes one **Charge** ledger entry per line, then captures every part of
  the booking's rental and deposit authorisation that is not yet captured
  and writes a **Capture** entry for each. For a cash booking nothing is
  captured (the cash is already in hand): only the Charge entries.
- The whole deposit is captured, so its balance can be given back by
  `refund_deposit()` with a gateway refund reference (SRS 3.4.2, SI-1.3).
- Runs **once per booking**. The same key returns the first run's entries; a
  different key raises `already_captured` (409).
- Raises `not_paid` (409) if the booking has no successful payment,
  `invalid_line` (400) for a blank description, `capture_failed` (402) if the
  gateway refuses (nothing is stored).
- It issues no invoice or debit note: settling the invoice for the extra
  charges (Pay.Invoice) belongs to the caller's module.

## refund_deposit

```python
refund_deposit(booking, amount, initiated_by, *, idempotency_key=None, request=None)
    -> RefundRequest
```

BR-14: "The balance of the security deposit, after deduction of all charges
due, is refunded to the original payment instrument within 7 working days of
the rental being completed."

- `amount` is the balance to give back (deposit minus the charges taken from
  it). Pass it only when it is above zero.
- Sets `refund_due_by` to 7 working days after today (Monday to Friday; no
  holiday calendar), then calls `refund_payment()` on the deposit payment
  with the reason "Security deposit balance (BR-14)".
- Writes a **Deposit Release** ledger entry, never a credit note (the deposit
  is not on the invoice, Pay.Deposit).
- One deposit refund per booking: without a key the key is
  `deposit-refund-<booking id>`, so a second call returns the first refund,
  and a different amount raises `idempotency_key_reused` (409).
- Raises `not_paid` (409) if the booking has no deposit payment.
- Like every refund it may wait for approval (above
  `REFUND_AUTO_APPROVAL_LIMIT`), or, for a cash booking, be paid out by the
  branch staff member who calls it. Read `.status` (below).

## refund_payment

```python
refund_payment(payment, amount, reason, initiated_by, *, idempotency_key=None,
               refund_due_by=None, request=None) -> RefundRequest
```

Pay.Refund, Exp 3 `Payment.refund()`: refunds go to the original instrument;
a cash refund is recorded by a named staff member.

- `payment`: one of the booking's successful rental or deposit payments
  (`Payment.objects.get(booking=..., original_payment=None, purpose=...)`).
  A capture, a refund row, a failed payment or a due payment is refused
  (`not_refundable`).
- `reason`: required, shown to the Administrator and the customer.
- Refuses more than the payment less what is refunded or waiting
  (`exceeds_refundable`).
- **Approval (UC 13).** Above `settings.REFUND_AUTO_APPROVAL_LIMIT`
  (`config/settings/business_rules.py`, proposed Rs 5,000.00) the refund waits
  as **Pending Approval** in the Administrator's queue (`/app/refunds`);
  at or below it, it is issued at once.
- **Card and on-line payments**: an uncaptured authorisation is captured
  first, then refunded through the gateway; the gateway's refund reference
  is stored on the refund `Payment` row (SI-1.3).
- **Cash payments**: if `initiated_by` is a Branch Staff user, the refund is
  issued at once as a `CashPayment` naming them, with the customer's
  acknowledgement time (the caller must have it, for example in the
  settlement the customer acknowledges at the counter). Otherwise the refund
  is **Approved** and waits on the branch's Cash desk (`/app/cash`).
- A rental refund also issues a **credit note** on the booking's invoice
  (Pay.Invoice), with the tax at the invoice's own rate.
- Ledger: **Refund** for a rental payment, **Deposit Release** for a deposit.
- The customer is e-mailed through Celery when the refund is issued or
  rejected, or if it fails.

### RefundRequest.status

| Status | Meaning | Next |
|---|---|---|
| Pending Approval | Above the limit, waiting for an Administrator (UC 13) | Issued, Approved (cash), Rejected, Failed |
| Approved | A cash refund waiting to be paid out at the branch | Issued |
| Issued | Money returned; `refund` is the refund `Payment` row | Failed (the gateway reports it failed, SI-1.4) |
| Rejected | The Administrator refused it; `rejection_reason` was e-mailed | none |
| Failed | The gateway refused it; `failure_reason` says why | none |

## record_due

```python
record_due(customer, amount, reason, *, initiated_by=None, request=None) -> Decimal
```

Pay.Dues: "record any amount not recovered from the security deposit as a due
against the customer." Return.Settle: when the charges exceed the deposit.

- Adds `amount` to `Customer.outstanding_due` under a row lock and audits
  the old and new due with the reason. Returns the new due.
- BR-4 then refuses new bookings (`apps/bookings/eligibility.py`, code
  `outstanding_due`) until the customer pays on-line at `/app/due`
  (`pay_due()`), which lifts the restriction at once.
- Not idempotent by itself: call it once, inside the same transaction as
  the settlement that decides the due.

## Other public functions

| Function | Use |
|---|---|
| `pay_due(customer, *, payment_token, idempotency_key, channel="", upi_id="")` | The customer clears the whole due on-line (`POST /api/v1/payments/due/`) |
| `approve_refund(refund, approver)`, `reject_refund(refund, approver, reason)` | UC 13, Administrator only (`/app/refunds`) |
| `pay_out_cash_refund(refund, staff_user)` | An Approved cash refund paid out at the counter (`/app/cash`) |
| `issue_credit_note(invoice, amount, reason, *, issued_by)` | Pay.Invoice correction; `refund_payment()` calls it for rental refunds. Credit notes never exceed the invoice total plus its debit notes |
| `issue_debit_note(invoice, amount, reason, *, issued_by)` | Pay.Invoice: an extra charge after issue (Book.Modify.Price, Book.Extend), DN-YYYY-NNNNNN, tax inside at the invoice's rate |
| `captured_amount(payment)`, `refunded_amount(payment)`, `refundable_amount(payment)` | Read-only sums |
| `authorize(...)`, `record_cash(...)`, `record_booking_ledger(...)`, `issue_invoice(...)` | Book.Done (`apps/bookings/lifecycle.py`). R2 also calls `authorize(deposit_amount=Decimal("0.00"))` for an extra rental charge (no deposit row; the same key returns the first result) and `record_booking_ledger(note=...)` for its Charge entry |
| `handle_notification(payload, signature)` | SI-1.4 webhook only |

## Example: settling a return (N2)

```python
from decimal import Decimal
from apps.payments import services

with transaction.atomic():
    lines = [services.ChargeLine("Excess kilometres, 40 km at 10.00 (BR-11)", Decimal("400.00"))]
    services.capture_charges(booking, lines, staff_user, idempotency_key=key)
    charges = sum((line.amount for line in lines), Decimal("0.00"))
    balance = booking.security_deposit - charges
    if balance > 0:
        services.refund_deposit(booking, balance, staff_user)
    elif balance < 0:
        services.record_due(booking.customer, -balance, "Return charges above the deposit",
                            initiated_by=staff_user)
    # then complete the booking through apps/bookings/states.py
```

## Known limits

- The mock gateway keeps its state per process. A `mock_txn_` reference it
  has not seen (authorised by `seed_demo` or before a server restart) is
  accepted, with its limits counted from then on.
- A refused capture is raised and rolled back, so it is not stored.
- Working days skip weekends only; there is no holiday calendar.
