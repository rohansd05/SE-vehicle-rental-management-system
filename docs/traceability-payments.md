# Traceability: Payments completion (Module R1)

Maps every requirement of SRS 3.4 (Pay.Method, Pay.Authorize, Pay.Deposit,
Pay.Confirm.OK, Pay.Idempotent, Pay.Invoice, Pay.Ledger, Pay.Refund,
Pay.Dues), Book.Confirm.Pay, SI-1.1 to SI-1.4, SE-9, BR-4, BR-9 and BR-14,
Exp 2 use case 13 "Approve Refund" (and the "Make Payment" include of Book
Vehicle), the Exp 3 `Payment`, `CardPayment`, `CashPayment`,
`OnlinePayment` and `Invoice` classes, the Exp 4 messages that move money,
the Exp 5 payment and refund activities and Exp 6 processes 4 and 6.4 to the
code and the tests. SRS: `docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf`.
The services other modules call are described in `docs/payments-api.md`.

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`, `I:` = `backend/integrations/`. Test names are pytest
functions (file in brackets) or Vitest `it` titles (in quotes). Test files:
`B:payments/tests/` `test_capture.py`, `test_refunds.py`, `test_dues.py`,
`test_webhook.py`, `test_api.py`, `test_seed.py`;
`B:bookings/tests/test_payment_methods.py`; `I:tests/test_payment_gateway.py`;
`F:features/payment/` `methods.test.tsx`, `due.test.tsx`, `cash-desk.test.tsx`;
`F:features/refunds/refunds.test.tsx`; `F:features/history/refunds.test.tsx`.

## 1. Requirements (SRS 3.4 and related)

| Requirement | Implemented in | Tests |
|---|---|---|
| **Pay.Method** card, on-line transfer, wallet (D6: channels of `OnlinePayment`) | `B:payments/services.py` `authorize(channel=, upi_id=)` → `_instrument_row()`; `B:bookings/lifecycle.py` `pay_booking(method=)`; `B:bookings/serializers.py` `PayBookingSerializer` (method, channel, upi_id); UI `F:features/payment/MethodPicker.tsx`, `PaymentPage.tsx` | `test_an_online_payment_confirms_the_booking` (UPI, Net Banking, Wallet), `test_paying_online_needs_a_channel_and_cash_needs_no_token` [test_payment_methods]; "pays by UPI with the UPI ID and an on-line sandbox token, then confirms", "pays by net banking or wallet without a UPI ID" |
| **Pay.Method** cash "for a booking to be collected at a branch, cash at the time of collection" (BR-9) | `lifecycle._choose_cash()`: the booking stays Pending Payment, `cash_on_collection` set, held for the collection (R1-P1); refused for a doorstep delivery (`cash_not_available`) | `test_choosing_cash_keeps_the_booking_unconfirmed_and_held_for_the_collection`, `test_cash_is_only_for_collection_at_the_branch`, `test_an_uncollected_cash_booking_is_released_after_the_no_show_window`, `test_a_cash_booking_can_still_be_paid_by_card` [test_payment_methods]; "cash at collection keeps the booking held and says what to bring (BR-9)", "a booking already set for cash opens with cash chosen and its collection hold", "shows a refusal of cash from the server" |
| **Book.Confirm.Pay** "after a staff member records a cash payment"; **BR-9** "recorded in the system by a named staff member when it is received" | `lifecycle.record_cash_payment()` → `payments.services.record_cash()` (`CashPayment.received_by` = the staff member, Capture rows) → the same `_confirm()` Book.Done transaction as a card; API `POST /api/v1/bookings/{id}/cash/` (`IsBranchStaff`, pickup branch only), list `GET /api/v1/bookings/awaiting-cash/`; UI `F:features/payment/CashDeskPage.tsx` (`/app/cash`) | `test_staff_record_the_cash_and_the_same_book_done_confirms_it`, `test_the_cash_must_be_exactly_the_rental_and_the_deposit`, `test_recording_the_same_cash_twice_never_records_it_twice`, `test_only_a_cash_booking_waiting_for_its_cash_can_be_recorded`, `test_staff_of_another_branch_cannot_find_the_booking`, `test_the_cash_desk_lists_only_its_branchs_held_cash_bookings`, `test_recording_cash_over_http_asks_for_the_staff_password` [test_payment_methods]; "lists the customers who pay cash at collection, with what they owe", "records the cash with the staff password and a fresh key; the booking is confirmed" |
| **Pay.Authorize** rental + deposit before confirming | unchanged one-call authorisation (`authorize()`), now for on-line channels too | Module 1 tests (`docs/traceability-booking.md`, message 5); `test_an_online_payment_confirms_the_booking` |
| **Pay.Deposit** held apart, never revenue | Security Deposit payment rows; Deposit Hold / Deposit Release ledger entries; no credit note for a deposit refund; the deposit stays off the invoice | `test_a_deposit_refund_is_a_deposit_release_and_never_a_credit_note` [test_refunds]; `test_each_charge_is_recorded_and_the_authorisation_is_captured` [test_capture] |
| **Pay.Confirm.OK** reference and transaction number | cash confirmation shows the booking reference (flash "Cash recorded. Booking … is confirmed.") and the cash transaction id on the booking | `test_staff_record_the_cash_and_the_same_book_done_confirms_it`; "records the cash with the staff password and a fresh key; the booking is confirmed" |
| **Pay.Idempotent** "a repeated gateway notification, a duplicate submission or a refreshed browser page cannot result in the customer being charged twice" | Keys on every money endpoint: pay (`previous_authorization()`), record cash (same), capture (`LedgerEntry.idempotency_key`, once per booking), refund (`RefundRequest.idempotency_key`), pay due (`Payment.idempotency_key`), webhook (`GatewayNotification.event_id`); the mock gateway also replays a key's first answer | `test_the_same_key_returns_the_first_capture_and_never_charges_twice`, `test_another_key_after_a_capture_is_refused` [test_capture]; `test_the_same_key_never_refunds_twice`, `test_one_deposit_refund_per_booking` [test_refunds]; `test_the_same_key_never_charges_the_due_twice`, `test_another_customers_key_is_not_theirs` [test_dues]; `test_recording_the_same_cash_twice_never_records_it_twice` [test_payment_methods]; `test_a_signed_notification_is_stored_once`, `test_a_failed_refund_is_reversed_once_however_often_it_is_reported` [test_webhook]; `test_a_repeated_submission_never_charges_or_refunds_twice` (due, capture, refund) [test_api]; `test_same_idempotency_key_returns_same_response` [gateway]; "records the cash with the staff password and a fresh key; the booking is confirmed" |
| **Pay.Invoice** "an issued invoice shall never be modified; a correction shall be made by a credit note that references the original invoice" | `issue_credit_note()` (`InvoiceAdjustment` CN-YYYY-NNNNNN, tax at the invoice's own rate, never above the invoice total); `_issue()` issues one for every rental refund. The invoice download flow is unchanged | `test_a_rental_refund_corrects_the_issued_invoice_with_a_credit_note`, `test_credit_notes_never_exceed_the_invoice` [test_refunds]; `B:payments/tests/test_append_only.py` (InvoiceAdjustment); Module 1's `test_the_invoice_downloads_as_a_pdf` |
| **Pay.Ledger** "each charge, capture, refund, deposit hold, deposit release and adjustment with its amount, method, gateway reference, timestamp and the user who initiated it" | Charge and Deposit Hold at Book.Done (and Capture for cash, `record_booking_ledger()`); Charge per line and Capture (`capture_charges()`, `_capture()`); Refund or Deposit Release (`_issue()`); Adjustment reversing a failed refund (`_refund_failed()`). Method from `Payment.method` (Card, Online, Cash) | `test_each_charge_is_recorded_and_the_authorisation_is_captured`, `test_cash_is_already_in_hand_so_only_the_charges_are_recorded` [test_capture]; `test_a_refund_within_the_limit_goes_back_to_the_original_card_at_once`, `test_an_uncaptured_authorisation_is_captured_before_it_is_refunded`, `test_a_cash_refund_is_paid_out_by_the_named_staff_member` [test_refunds]; `test_staff_record_the_cash_and_the_same_book_done_confirms_it`, `test_an_online_payment_confirms_the_booking` [test_payment_methods]; `test_a_failed_refund_is_reversed_once_however_often_it_is_reported` [test_webhook]; append-only: `B:payments/tests/test_append_only.py` |
| **Pay.Refund** "to the original payment instrument, or, where the original payment was in cash, as a cash refund recorded by a named staff member and acknowledged by the customer" | `refund_payment()` → `_issue()`: gateway refund of the original authorisation (`original_payment`), or a `CashPayment` refund naming the staff member with `customer_acknowledged_at`; an Approved cash refund is paid out with `pay_out_cash_refund()` (`POST /api/v1/payments/refunds/{id}/pay-out/`, acknowledgement required); staff API `POST /api/v1/payments/{id}/refund/` | `test_a_refund_within_the_limit_goes_back_to_the_original_card_at_once`, `test_no_more_than_was_paid_can_be_refunded_counting_refunds_waiting`, `test_only_a_successful_booking_payment_can_be_refunded`, `test_a_refund_the_gateway_refuses_is_marked_failed`, `test_a_cash_refund_is_paid_out_by_the_named_staff_member`, `test_a_cash_refund_asked_for_elsewhere_waits_for_the_branch`, `test_a_large_cash_refund_is_approved_then_paid_out` [test_refunds]; "pays out an approved cash refund only once the customer has acknowledged it"; customer view: `test_the_booking_detail_shows_its_refunds` [test_api], "shows each refund and where it stands" |
| **Pay.Dues** "record any amount not recovered from the security deposit as a due … display it on the customer's home screen … prevent further bookings until it is cleared … clear a due on-line at any time … lift the restriction immediately on payment" | `record_due()` (adds to `Customer.outstanding_due`, audited); BR-4 check unchanged in `B:bookings/eligibility.py`; `pay_due()` authorises and captures the whole due and sets it to zero in the same transaction; API `GET/POST /api/v1/payments/due/`; UI home notice `F:pages/DashboardPage.tsx` `DueNotice`, page `F:features/payment/DuePage.tsx` (`/app/due`) | `test_a_due_is_added_to_the_customer_and_audited`, `test_a_due_must_be_a_positive_decimal_with_a_reason`, `test_a_due_blocks_booking_and_paying_it_lifts_the_restriction_at_once`, `test_a_due_can_be_paid_through_an_online_channel`, `test_a_declined_due_payment_keeps_the_due_and_is_recorded`, `test_nothing_to_pay_without_a_due` [test_dues]; `test_paying_the_due_returns_the_new_due_and_the_transaction`, `test_a_declined_due_payment_is_a_402` [test_api]; "the customer home screen shows the due and leads to paying it", "the home screen says nothing when nothing is owed", "pays the whole due on-line with the password; booking is allowed again at once", "a declined payment keeps the due and says so", "with no due there is nothing to pay", "cash is not offered for a due" |
| **SI-1.2** capture when the rental is completed and the charges are known | `capture_charges()`; gateway `capture()`; API `POST /api/v1/payments/bookings/{id}/capture/` | `test_capture.py` (all 7) |
| **SI-1.3** "full or partial refund of a rental amount or a security deposit, and … store the reference returned" | gateway `refund()` returns its own reference (`rfnd_…`), stored as the refund row's `gateway_reference` | `test_a_refund_within_the_limit_goes_back_to_the_original_card_at_once` [test_refunds]; `test_authorize_capture_refund_happy_path` [gateway] |
| **SI-1.4** "an endpoint to receive asynchronous payment and refund notifications … verify the signature of every notification … process each notification idempotently" | `PaymentGateway.verify_notification()` (mock: HMAC-SHA256 under `PAYMENT_WEBHOOK_SECRET`); `handle_notification()` stores each event once (`GatewayNotification`, append-only by model guard and PostgreSQL trigger); `refund.failed` reverses the refund (R1-P12); API `POST /api/v1/payments/webhook/` (`AllowAny`, the signature is the credential) | `test_webhook.py` (all 5); `test_a_notification_is_accepted_only_with_its_signature` [gateway]; `test_the_gateway_notification_needs_only_its_signature` (every role) [test_api] |
| Interface rule: the gateway behind `integrations/` with a mock | `I:payment_gateway/interface.py` (authorize, capture, refund, verify_notification), `mock.py` (shared state per process, unique ids) | `I:tests/test_payment_gateway.py` (all 10) |
| **SE-9** "re-authentication shall be required before a payment or a refund" | `B:payments/reauth.py` `require_password()` on pay, record cash, pay due, capture, refund, approve, reject and pay-out; failures audited | `test_a_wrong_password_moves_no_money_and_is_audited` (7 endpoints) [test_api]; `test_recording_cash_over_http_asks_for_the_staff_password` [test_payment_methods]; "asks for the password first, and shows a wrong one on its field (SE-9)", "a wrong password is shown on its field and nothing changes (SE-9)" |
| **SE-4, SE-5** explicit permission classes; scoping with `scope_queryset()` | `B:payments/views.py` (every view declares `permission_classes`; `scoped_refunds()`, scoped bookings and payments), `B:bookings/views.py` `AwaitingCashListView`, `BookingCashView` | `test_every_endpoint_for_every_role` (11 endpoints x anonymous, customer, staff, technician, manager, admin), `test_staff_of_another_branch_get_a_404`, `test_each_role_sees_only_the_refunds_in_its_scope` [test_api]; "is closed to other roles (the API refuses them too)", "appears in the menu for branch staff only", "is in the Administrator menu" |
| **SE-10** audit of every payment, refund and status change | `record_audit()` in every service; refund statuses through `_set_refund_status()` (REFUND_TRANSITIONS); booking statuses through `B:bookings/states.py` `transition()` | `test_approving_issues_the_refund_and_records_the_approver` (audit order), `test_refund_statuses_follow_their_transition_table` [test_refunds]; `test_a_due_is_added_to_the_customer_and_audited` [test_dues]; `test_staff_record_the_cash_and_the_same_book_done_confirms_it` |
| **Notify.*** (SRS 3.7) "change in the status of a refund", through Celery (SI-2.2) | `_notify_customer()` → `queue_email()`; templates `refund_issued`, `refund_rejected`, `refund_failed` in `B:notifications/templates.py` | `test_rejecting_records_the_reason_and_notifies_the_customer_through_celery`, `test_a_refund_within_the_limit_goes_back_to_the_original_card_at_once` [test_refunds]; `test_a_failed_refund_is_reversed_once_however_often_it_is_reported` [test_webhook]; `test_every_template_renders` [notifications] |
| **CO-6** Decimal money | every amount `Decimal`; services refuse a float | `test_a_charge_needs_a_description_and_a_positive_decimal_amount`, `test_only_a_successful_booking_payment_can_be_refunded`, `test_a_due_must_be_a_positive_decimal_with_a_reason`, `test_amounts_must_be_positive_decimals` |

## 2. Exp 2 use cases

| Use case step | Implemented in | Tests |
|---|---|---|
| **UC 13 Approve Refund**, precondition "a refund request is pending approval" | `refund_payment()`: above `REFUND_AUTO_APPROVAL_LIMIT` the `RefundRequest` stays Pending Approval, nothing is refunded | `test_a_refund_above_the_limit_waits_for_an_administrator`, `test_the_limit_is_the_refund_auto_approval_setting`, `test_a_deposit_refund_is_a_deposit_release_and_never_a_credit_note` (exactly the limit is automatic) [test_refunds] |
| UC 13 step 1: "reviews the pending refund, its amount and reason" | `GET /api/v1/payments/refunds/?status=Pending Approval` (`RefundListView`); UI `F:features/refunds/RefundQueuePage.tsx` (`/app/refunds`) | `test_the_administrator_queue_filters_by_status` [test_api]; "lists each pending refund with its amount, reason, customer and booking", "says when no refund is waiting" |
| UC 13 step 2–3: "approves … issues the refund to the original payment instrument and records the approver" | `approve_refund()` (`decided_by`, `decided_at`, then `_issue()`); `POST …/refunds/{id}/approve/` (`IsAdministrator`, SE-9) | `test_approving_issues_the_refund_and_records_the_approver`, `test_only_an_administrator_approves_or_rejects`, `test_a_decided_refund_cannot_be_decided_again` [test_refunds]; "approves with the password; the refund is issued and the queue empties", "an approved cash refund is left for the branch to pay out" |
| UC 13 extension 2a: "rejects … records the reason and notifies the customer" | `reject_refund()` (`rejection_reason`, e-mail through Celery); `POST …/refunds/{id}/reject/` | `test_rejecting_records_the_reason_and_notifies_the_customer_through_celery`, `test_a_rejection_needs_a_reason` [test_refunds]; "rejecting needs a reason, which the customer is sent" |
| UC 13 post-condition: "the decision is recorded in the audit log" | "Refund Approved", "Refund Status Changed" audit entries | `test_approving_issues_the_refund_and_records_the_approver`, `test_rejecting_records_the_reason_and_notifies_the_customer_through_celery` |
| **Book Vehicle** step 6 "include: Make Payment"; 6a "the payment authorisation is declined" | `pay_booking()` with card, on-line or cash; declines keep the hold (Module 1) | `test_payment_methods.py`; Module 1 payment tests; `F:features/payment/payment.test.tsx` (unchanged, still passing) |
| **Return Vehicle** step 5 "deducts the charges from the security deposit and refunds any balance" (built by N2) | provided: `capture_charges()`, `refund_deposit()`, `record_due()` (`docs/payments-api.md`) | `test_capture.py`, `test_the_deposit_balance_is_due_within_seven_working_days` [test_refunds], `test_dues.py` |

## 3. Exp 4 sequence diagram messages

The diagrams are images; the message list follows `docs/VRMS_Handoff.md` §4.

| Message | Implemented in | Tests |
|---|---|---|
| Seq. 1 (Book Vehicle), message 5: Booking → Payment: `authorize()` | now also an `OnlinePayment` (D6 channel) | `test_an_online_payment_confirms_the_booking` |
| Seq. 1, alt (cash, Book.Confirm.Pay): staff record the cash instead of `authorize()` | `record_cash_payment()` → `record_cash()` → `_confirm()` | `test_staff_record_the_cash_and_the_same_book_done_confirms_it` |
| Seq. 1, messages 6–8 (block, `generate_invoice()`, Confirmed) for a cash booking | the same `_confirm()` (one transaction: reference, pickup code, invoice, ledger) | `test_staff_record_the_cash_and_the_same_book_done_confirms_it` (invoice, ledger, reference, pickup code, audit) |
| Seq. 2 (Return Vehicle): `Tariff.calculate_price()` (settlement under BR-10 to BR-12) → **`Payment.refund()`** | provided for N2: `capture_charges()` (Exp 3 `Payment.capture()`) then `refund_deposit()` → `refund_payment()` (Exp 3 `Payment.refund()`); the settlement computation and the call are N2's | `test_capture.py`, `test_refunds.py` |

## 4. Exp 3 class-diagram elements

| Element | Implemented in | Tests |
|---|---|---|
| `Payment` (transaction_id, amount, status, timestamp; `authorize()`, `capture()`, `refund()`) | `B:payments/models.py` `Payment` (+ `method`; `booking` nullable only for a due payment, `payments_booking_unless_due`); `authorize()`, `capture_charges()`/`_capture()`, `refund_payment()`/`_issue()` | sections 1–3 |
| `CardPayment` (card_token, card_brand) | unchanged; CO-2 token only | `test_card_payment_stores_no_card_data` [test_models] |
| `CashPayment` (received_by) | `received_by` → `BranchStaff` (BR-9), `customer_acknowledged_at` (Pay.Refund) | `test_staff_record_the_cash_and_the_same_book_done_confirms_it`, `test_a_cash_refund_is_paid_out_by_the_named_staff_member` |
| `OnlinePayment` (upi_id) + D6 `channel` | `authorize(channel=, upi_id=)`, `pay_due(channel=, upi_id=)` | `test_an_online_payment_confirms_the_booking`, `test_a_due_can_be_paid_through_an_online_channel`, `test_online_payment_channels_are_d6` [test_models] |
| `Invoice` (`generate_invoice()`) + `InvoiceAdjustment` (credit note) | `issue_invoice()`; `issue_credit_note()` | `test_a_rental_refund_corrects_the_issued_invoice_with_a_credit_note` |
| `Administrator.approve_refund()` | `approve_refund()`, `reject_refund()` | section 2 |
| `Customer.outstanding_due` | read by `check_eligibility()`, written only by `record_due()` and `pay_due()` | `test_dues.py` |
| Additions: `RefundRequest`, `GatewayNotification`, `LedgerEntry.idempotency_key`, `Booking.cash_on_collection` | `B:payments/models.py`, migration `payments/0002_refunds_dues_and_notifications`; `B:bookings/models.py`, migration `bookings/0004_booking_cash_on_collection` | `test_refunds.py`, `test_webhook.py`, `test_capture.py`, `test_payment_methods.py` |

## 5. Business rules

| Rule | Where enforced | Tests |
|---|---|---|
| **BR-4** no new booking with an outstanding due above zero | `B:bookings/eligibility.py` (unchanged) reading the due that `record_due()` sets and `pay_due()` clears | `test_a_due_blocks_booking_and_paying_it_lifts_the_restriction_at_once` [test_dues]; Module 1 `test_a_customer_with_a_due_cannot_book` |
| **BR-9** cash only for branch collection, recorded by a named staff member when received | `_choose_cash()` (refuses a delivery booking), `record_cash_payment()` (Branch Staff of the pickup branch; exact amount), `CashPayment.received_by` | `test_cash_is_only_for_collection_at_the_branch`, `test_staff_record_the_cash_and_the_same_book_done_confirms_it`, `test_the_cash_must_be_exactly_the_rental_and_the_deposit`, `test_staff_of_another_branch_cannot_find_the_booking` |
| **BR-14** the deposit balance refunded to the original instrument within 7 working days | `refund_deposit()` sets `refund_due_by` with `add_working_days(today, DEPOSIT_REFUND_WORKING_DAYS)` (existing setting) and refunds the original deposit payment | `test_the_deposit_balance_is_due_within_seven_working_days`, `test_working_days_skip_the_weekend`, `test_one_deposit_refund_per_booking`, `test_a_booking_without_a_deposit_payment_has_none_to_refund` [test_refunds]; "shows each refund and where it stands" |
| **BR-3** deposit amounts (unchanged) | the deposit refunded is the deposit authorised or received | `test_each_charge_is_recorded_and_the_authorisation_is_captured` |

## 6. Exp 5 activity diagram and Exp 6 DFD

| Element | Implemented in |
|---|---|
| Exp 5 Customer: "Select payment method and submit payment" | `F:features/payment/MethodPicker.tsx`, `PaymentPage.tsx` |
| Exp 5 Branch Staff: "Record cash refund if paid in cash (BR-9)" | `_issue()` cash path; Cash desk "Pay out" (`F:features/payment/CashDeskPage.tsx`) |
| Exp 5 VRMS: "Refund deposit balance within 7 days (BR-14)" | `refund_deposit()`; BR-14's "7 working days" is followed where the diagram says "7 days" |
| Exp 5 decision "Refund above threshold?" → Administrator "Approve or reject refund, record approver" | `refund_payment()` limit; `approve_refund()`, `reject_refund()`; `/app/refunds` |
| Exp 5 Notification Service: "Send settlement and refund notification" | refund e-mails through Celery (`_notify_customer()`) |
| Exp 6 process 4 "Process Payment and Invoicing", store D5 "Payment Ledger" | `B:payments/services.py`; `LedgerEntry`, `Payment`, `InvoiceAdjustment` |
| Exp 6 process 6.4 "Settle Deposit and Refund" (D5, Payment Gateway) | `capture_charges()`, `refund_deposit()`, `record_due()` for N2 |
| Exp 6 Payment Gateway flows "authorize / authorization result / refund" | `I:payment_gateway/` |

## 7. Proposed readings (awaiting team approval)

The SRS does not settle these; the code implements them as listed.

| # | Item | Proposal |
|---|---|---|
| R1-P1 | Hold of a cash booking | Choosing cash keeps the booking Pending Payment, held until `NO_SHOW_AFTER` (2 hours) after the pickup time instead of the 15-minute Book.Hold; then the no-show task marks it No-show (R2-P1, `docs/traceability-booking-changes.md`; it returned to Draft before Module R2). **Differs from Book.Hold's 15 minutes**, which cannot cover a collection days later. The customer can still pay by card or on-line before then |
| R1-P2 | Automatic approval limit (UC 13) | `REFUND_AUTO_APPROVAL_LIMIT = Decimal("5000.00")` in `business_rules.py`; "above" means strictly greater, so a full car deposit (5,000.00) is refunded without approval |
| R1-P3 | Who approves refunds | Administrator only (UC 13's actor); a Branch Manager does not |
| R1-P4 | Cash refunds | Issued at once when a Branch Staff member asks for them (the customer is at the counter; the acknowledgement is recorded then); asked for by anyone else, they wait as Approved on the branch's Cash desk; above the limit they need approval first, like every refund |
| R1-P5 | Capture at settlement | `capture_charges()` captures the whole rental and deposit authorisation, and the deposit balance is refunded through the gateway, so it has a refund reference (SRS 3.4.2, SI-1.3) and BR-14's window applies |
| R1-P6 | Refund of an uncaptured authorisation | Captured first, then refunded (the gateway refunds only captured money) |
| R1-P7 | Working days (BR-14) | Monday to Friday; no public-holiday calendar |
| R1-P8 | SE-9 for staff | Every endpoint that moves money asks for the caller's password, including recording cash, capture, approve, reject and pay-out |
| R1-P9 | Cash amount | Staff enter the cash received; it must equal the rental plus the deposit, or nothing is recorded |
| R1-P10 | Paying a due | The whole due at once, by card or on-line; not in cash; no partial payment |
| R1-P11 | Credit notes | A rental refund issues a credit note for the refunded amount, tax inside at the invoice's rate; a deposit refund issues none |
| R1-P12 | Gateway notifications | Stored once by event id. Only `refund.failed` acts: the refund row and request become Failed, an Adjustment ledger entry references the Refund entry, the customer is e-mailed. Other events (`refund.processed`, `payment.*`) are stored only. A bad signature is 403 |
| R1-P13 | Refund e-mails | When a refund is issued, rejected or reported failed |
| R1-P14 | New screens and menu entries | "Cash desk" (`/app/cash`, Branch Staff), "Refunds" (`/app/refunds`, Administrator), "Pay your due" (`/app/due`, customers, reached from the home-screen notice); the booking page lists refunds. No "Soon" placeholder existed for these, so none was removed |
| R1-P15 | Due payments | A payment that clears a due has no booking and therefore no ledger entry (the ledger is per booking, Pay.Ledger); its Payment row and the audit log record it |
| R1-P16 | Mock gateway (development only) | State shared per process; a `mock_txn_` reference from another process (seed_demo, a restart) is accepted |

## 8. Not built in Module R1

A staff screen to start an ad-hoc refund (the API `POST /api/v1/payments/{id}/refund/`
exists; R2 and N2 call the services); a debit note or invoice for the return
charges (Pay.Invoice at completion, N2's flow); reversing an authorisation when
Book.Done fails after it (the mock has no void); a live gateway backend; a
holiday calendar; partial due payments; refunding a due payment;
`apps/rentals/services._is_paid()` (P24) still reads the payment rows directly
and stays correct for cash bookings, because a recorded cash deposit is a
Succeeded Security Deposit payment.

## 9. Demo data

`B:payments/seed.py`, called from `seed_demo` (one-line additions):
`payments@vrms.test` (password `Demo@1234`) with a due of 850.00; MH02DP4001,
booked by that customer for tomorrow 10:00 with cash at collection (Branch
Staff `staff@vrms.test` → Cash desk); MH02DP4002, paid by card ten days ahead,
with a refund of 8,260.00 waiting for `admin@vrms.test` at Refunds. No invoice
or ledger entry is seeded, so `--reset` can remove it all. Tests:
`B:payments/tests/test_seed.py`, `B:core/tests/test_seed_demo.py` (counts),
`B:bookings/tests/test_seed.py` (search count).
