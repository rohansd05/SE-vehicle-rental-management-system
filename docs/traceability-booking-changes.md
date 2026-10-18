# Traceability: Modify / Cancel / Extend booking and No-show (Module R2)

Maps SRS 3.1 Book.Modify, Book.Modify.Price, Book.Cancel,
Book.Cancel.Release, Book.Extend and Book.Status, History.View (filters and
rebook), Notify.Booking (modification, extension, cancellation, no-show),
Reliability-1, BR-1, BR-2, BR-5, BR-8 and the Appendix B No-show to the code
and the tests, with Exp 2 use case 4 "Modify / Cancel Booking" and use case 5
extension 5a "rebook", the Exp 3 `Booking.modify_booking()`,
`cancel_booking()` and `extend_booking()`, the Exp 4 messages reused here,
the Exp 5 "2 h after pickup, not collected" time event and Exp 6 processes
3.6 and 3.7. SRS: `docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf`.

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`. Test names are pytest functions (file in brackets)
or Vitest `it` titles (in quotes). Test files: `B:bookings/tests/`
`test_changes.py` [changes], `test_changes_api.py` [api],
`test_states.py` [states], `test_concurrency.py` [concurrency],
`test_seed_changes.py` [seed], `test_payment_methods.py` [cash];
`F:features/history/booking-changes.test.tsx` (Vitest).

Money moves only through R1's services (`docs/payments-api.md`): an extra
charge through `authorize()` (the pay flow, Pay.Idempotent), refunds through
`refund_payment()` and `refund_deposit()`, the capture of a cancelled or
missed booking through `capture_charges()`.

## 1. Requirements

| Requirement | Implemented in | Tests |
|---|---|---|
| **Book.Modify** "change the period, the pickup branch or the add-ons of a Confirmed booking, provided that the request is made at least 12 hours before the pickup time and the vehicle is free for the new period" | `B:bookings/services.py` `modification_quote()`, `modify_booking()`: `_check_modifiable()` (Confirmed, no handover report, `MODIFICATION_CUTOFF`), `_vehicle_free()` (BR-1 buffer, maintenance windows; R2-P3 branch rule), `check_period()` (BR-5), `_check_licence()` (BR-2); vehicle row lock; exclusion constraint as the last word (`_save_change()`); API `POST /api/v1/bookings/{id}/modify/quote/`, `POST /api/v1/bookings/{id}/modify/`; UI `F:features/history/BookingActions.tsx` `ModifyBooking` | `test_a_longer_period_is_charged_at_once`, `test_no_change_inside_the_12_hour_cut_off`, `test_the_turnaround_buffer_still_applies`, `test_a_new_branch_needs_a_vehicle_based_there`, `test_only_a_confirmed_booking_can_be_changed`, `test_a_booking_being_handed_over_cannot_be_changed`, `test_br5_and_br2_still_apply_to_the_new_period`, `test_an_unchanged_request_changes_nothing`, `test_doorstep_delivery_cannot_be_added` [changes]; `test_the_customer_prices_then_makes_a_change`, `test_the_cut_off_is_a_409_that_says_so`, `test_a_period_outside_br5_is_a_field_error` [api]; "checks the new price, takes the extra charge by card and confirms", "states the 12-hour cut-off (UC 4 2a)", "asks for the price to be checked before confirming" |
| **Book.Modify.Price** "recalculate the price, charge any additional amount immediately, and refund any excess under the cancellation rules of BR-8" | `_plan()` reprices with `lifecycle.booking_quote()` at the booking's own tariff and discount (R2-P4); extra: `_charge_extra()` → `payments.authorize(deposit_amount=0)`, `record_booking_ledger(note=)` Charge entry, `issue_debit_note()` (R2-P6); excess: `refund_percent()` of the difference (R2-P5) → `_refund_rental()` → `payments.refund_payment()` (credit note by R1); 409 `price_changed` if the amounts differ from those shown (R2-P2); 402 on a decline changes nothing | `test_a_longer_period_is_charged_at_once`, `test_a_shorter_period_refunds_the_excess_under_br8`, `test_add_ons_keep_their_booked_rate_and_new_ones_take_todays`, `test_a_changed_price_must_be_confirmed_again`, `test_a_declined_extra_charge_changes_nothing`, `test_an_extra_charge_needs_a_payment_method`, `test_the_same_key_never_charges_twice`, `test_raising_then_cancelling_refunds_both_payments` [changes]; `test_a_declined_extra_charge_is_a_402`, `test_modifying_asks_for_the_password` [api]; "shows the BR-8 refund for a cheaper change and sends no payment" |
| **Book.Cancel** "cancel a Confirmed booking at any time before the vehicle is handed over … display the refund computed per BR-8 and … require confirmation" | `cancellation_quote()` / `_cancellation_quote()` (`CancellationQuote`); `cancel_booking(expected_refund=)` refuses 409 `refund_changed` if BR-8 now gives another amount (R2-P2); `_check_cancellable()` refuses an Active booking or one with a handover report (N1); API `GET` and `POST /api/v1/bookings/{id}/cancel/` (password, SE-9); UI `CancelBooking` (refund shown in the dialog, then the password) | `test_cancelling_48_hours_ahead_refunds_everything`, `test_later_cancellations_refund_less_but_always_the_whole_deposit` (75 %, 50 %), `test_a_changed_refund_must_be_confirmed_again`, `test_cancelling_twice_refunds_once`, `test_an_active_booking_cannot_be_cancelled`, `test_a_booking_being_handed_over_cannot_be_cancelled`, `test_a_held_card_booking_is_not_cancelled_it_simply_expires` [changes]; `test_the_customer_sees_the_refund_then_cancels`, `test_cancelling_asks_for_the_password`, `test_a_changed_refund_is_a_409`, `test_an_active_booking_cannot_be_cancelled_over_http` [api]; "shows the BR-8 refund, asks for the password and cancels", "shows the new refund when it changed before confirming" |
| **Book.Cancel.Release** "immediately release the vehicle, set the booking status to Cancelled, initiate the refund and notify the customer and the branch" | in one transaction: `states.mark_cancelled()` (the blocked period stops holding the vehicle; no vehicle status changes before handover, as at Book.Done), audit "Vehicle Released From Booking"; `_settle()`: `capture_charges(lines=[])`, `refund_payment()` per rental payment, `refund_deposit()` (R2-P7); above `REFUND_AUTO_APPROVAL_LIMIT` the refund waits in `/app/refunds` (UC 13), a cash refund on the Cash desk; `_notify()` e-mails the customer (`booking_cancelled`) and the pickup branch's staff (`booking_branch_update`) through Celery | `test_cancelling_48_hours_ahead_refunds_everything` (release, ledger, credit note, audit, both e-mails, the period bookable again), `test_a_refund_above_the_approval_limit_waits_for_an_administrator`, `test_a_confirmed_cash_booking_refund_waits_at_the_cash_desk`, `test_an_unpaid_cash_booking_is_cancelled_with_nothing_to_refund` [changes]; "says when part of the refund waits for an administrator", "an unpaid cash booking has nothing to refund" |
| **Book.Extend** "extend an Active rental only if no confirmed booking of the same vehicle conflicts with the extended period and the total period remains within BR-5. The additional charge shall be collected before the extension takes effect" | `extension_quote()`, `extend_booking()`: `_plan_extension()` (Active only; later and future return; `RENTAL_PERIOD_MAXIMUM` from the pickup; licence through the new return; `_held_by_others()` with the BR-1 buffer); the extra is authorised first, then the return moves (`states.record_extension()`, constraint backstop), Charge entry and debit note; API `POST /api/v1/bookings/{id}/extend/quote/`, `POST /api/v1/bookings/{id}/extend/`; UI `ExtendBooking` | `test_an_active_rental_is_extended_once_the_extra_is_paid`, `test_no_extension_into_another_booking_or_its_buffer`, `test_the_whole_rental_stays_within_30_days`, `test_only_an_active_rental_is_extended`, `test_the_new_return_must_be_later`, `test_a_declined_extension_changes_nothing`, `test_extending_twice_with_one_key_charges_once` [changes]; `test_the_customer_prices_then_extends_a_rental`, `test_a_confirmed_booking_cannot_be_extended_over_http` [api]; "quotes the extra charge and collects it before extending", "shows why an extension is refused" |
| **Book.Status** "only the transitions shown in the state-transition diagram in Appendix B" | `B:bookings/states.py`: `ALLOWED_TRANSITIONS` (plus R2-P1), and four separate functions that each accept one source status: `record_modification()` (Confirmed → Confirmed), `record_extension()` (Active → Active), `mark_cancelled()`, `mark_no_show()`; every change through `transition()`, audited | `test_the_table_is_exactly_appendix_b`, `test_every_pair_is_allowed_or_refused` (49 pairs), `test_each_r2_change_is_saved_and_audited`, `test_each_r2_change_refuses_other_statuses`, `test_a_cash_booking_may_be_cancelled_or_a_no_show_before_payment`, `test_only_a_confirmed_card_booking_becomes_a_no_show` [states] |
| **Appendix B No-show** "when the customer has not collected the vehicle two hours after the pickup time"; **BR-8** "in the case of a no-show, 50 percent is retained" | `services.declare_no_shows()` (Confirmed, or unpaid cash Pending Payment, `NO_SHOW_AFTER` past pickup, no handover report, `SKIP LOCKED`); `_declare_no_show()`: `mark_no_show()`, release audit, `_settle()` with `NO_SHOW_RETAINED_PERCENT`, `booking_no_show` e-mail; Celery task `B:bookings/tasks.py` `declare_no_shows`, scheduled every minute by migration `B:bookings/migrations/0005_schedule_no_show.py`; `lifecycle.release_expired_holds()` now leaves cash bookings to it | `test_an_uncollected_booking_is_a_no_show_two_hours_after_pickup`, `test_a_handed_over_booking_is_never_a_no_show`, `test_an_unpaid_cash_booking_becomes_a_no_show_and_frees_the_vehicle`, `test_other_statuses_are_left_alone`, `test_a_gateway_refusal_leaves_the_booking_for_the_next_run`, `test_the_no_show_task_is_scheduled_every_minute` [changes]; `test_an_uncollected_cash_booking_is_released_after_the_no_show_window` [cash] |
| **BR-8** 100 % at 48 h or more, 75 % at 12 to 48 h, 50 % under 12 h; the deposit always refunded in full | `refund_percent()` reads `CANCELLATION_*` from `config/settings/business_rules.py`; `_share()` rounds half-up to the paisa | `test_br8_refund_percent_by_notice` (6 boundaries), `test_later_cancellations_refund_less_but_always_the_whole_deposit` [changes] |
| **BR-1** one confirmed booking per vehicle at any instant plus the 60-minute buffer; **Reliability-1** "100 simultaneous confirmations of one vehicle, of which exactly one must succeed" | modify and extend lock the vehicle row (as Book.Create) and check `requested_block()`; the PostgreSQL exclusion constraint decides | `test_exactly_one_of_simultaneous_bookings_succeeds` (2, 20, 100), `test_exactly_one_of_simultaneous_modifications_onto_one_slot_succeeds` (20, 100) [concurrency]; `test_the_turnaround_buffer_still_applies`, `test_no_extension_into_another_booking_or_its_buffer` [changes] |
| **BR-5** 4 hours to 30 days "including any extension" | modify: `check_period()`; extend: `RENTAL_PERIOD_MAXIMUM` measured from the pickup | `test_br5_and_br2_still_apply_to_the_new_period`, `test_the_whole_rental_stays_within_30_days` [changes]; `test_a_period_outside_br5_is_a_field_error` [api] |
| **BR-2** the licence valid for the entire rental period | `_check_licence()` → `eligibility.licence_is_valid()` on the new return | `test_br5_and_br2_still_apply_to_the_new_period` [changes] |
| **History.View** "filter them by date range, status and vehicle type or search them by booking reference" | `B:bookings/views.py` `BookingFilter` (`pickup_from`, `pickup_to`, `status`, `vehicle_type`, `reference`) on `GET /api/v1/bookings/`; UI `F:features/history/BookingHistoryPage.tsx` filter toolbar | `test_history_filters_by_dates_status_vehicle_type_and_reference` (includes History.Privacy) [api]; "filters by vehicle type, pickup dates and reference"; existing "filters by status" |
| **Exp 2 UC 5 extension 5a** "rebook … a new booking pre-filled with that vehicle, subject to current availability and tariff" | `BookingActions` `Rebook`: the vehicle page with a period of the same length from tomorrow (R2-P12); the server re-checks availability and prices at today's tariff | "opens the vehicle again with a period of the same length" |
| **Notify.Booking** "on the … modification, extension, cancellation and no-show of a booking, stating the booking reference and the resulting status" | `_notify()` → `queue_email()` (Celery after commit); templates `B:bookings/notification_templates.py` (`booking_modified`, `booking_extended`, `booking_cancelled`, `booking_no_show`, `booking_branch_update`), registered by `BookingsConfig.ready()` | the e-mail assertions in the modify, cancel, extend and no-show tests [changes]; `test_every_template_renders` [`B:notifications/tests/test_delivery.py`] |
| **SE-4, SE-5** explicit permission class on every endpoint; only the customer's own booking | `IsCustomer` on the five R2 views; `_own_booking()` (404 for another customer's) | `test_only_customers_change_bookings` (6 endpoints x staff, manager, admin, technician), `test_an_anonymous_visitor_is_asked_to_sign_in`, `test_another_customers_booking_is_not_found` [api]; "a card hold being paid has no change actions" |
| **SE-9** re-authentication before a payment or refund | `require_password()` on cancel, modify and extend | `test_cancelling_asks_for_the_password`, `test_modifying_asks_for_the_password` [api] |
| **SE-10** audit | `transition()` ("Booking Status Changed"), "Booking Modified" and "Booking Extended" with before and after, "Vehicle Released From Booking", and R1's payment, refund, ledger and note entries | `test_cancelling_48_hours_ahead_refunds_everything`, `test_a_longer_period_is_charged_at_once`, `test_an_active_rental_is_extended_once_the_extra_is_paid` [changes]; `test_each_r2_change_is_saved_and_audited` [states] |
| **Pay.Idempotent** | modify and extend: the client key (`modify-…`, `extend-…`) on `authorize()` and the refund keys; cancel and no-show: `cancel-<id>` and `no-show-<id>` | `test_the_same_key_never_charges_twice`, `test_extending_twice_with_one_key_charges_once`, `test_cancelling_twice_refunds_once` [changes] |
| **Pay.Invoice**, **Pay.Ledger** | extra charge: Charge entry and `issue_debit_note()` (DN-YYYY-NNNNNN); refunds: R1's Refund, Deposit Release and credit notes; credit notes may now reach the invoice total plus its debit notes | `test_a_longer_period_is_charged_at_once`, `test_raising_then_cancelling_refunds_both_payments` [changes] |
| **CO-6** Decimal money, UTC time | `Decimal` everywhere; the client sends the amounts it was shown as decimal strings; filters by local pickup date | every amount assertion above |

## 2. Exp 2 use case 4 "Modify / Cancel Booking"

| Step | Implemented in | Tests |
|---|---|---|
| 1 open a Confirmed booking | `F:features/history/BookingDetailPage.tsx` → `BookingActions` (Confirmed: Modify, Cancel; Active: Extend; unpaid cash: Cancel; past: Book again) | "a confirmed booking can be modified or cancelled", "an active rental can only be extended", "an unpaid cash booking can be cancelled" |
| 2 choose to modify the period, branch or add-ons, or cancel | `ModifyBooking` (pickup, return, branch, add-ons), `CancelBooking` | as above |
| 2a less than 12 hours before pickup: refuse and state the cut-off | `ModificationCutoffError` (409 `modification_cutoff`, message names the cut-off and the pickup time) | `test_no_change_inside_the_12_hour_cut_off`, `test_the_cut_off_is_a_409_that_says_so`; "states the 12-hour cut-off (UC 4 2a)" |
| 3 check the vehicle is free and recalculate the price | `modification_quote()` | `test_a_longer_period_is_charged_at_once` |
| 3a not free: offer an available vehicle of the same category at the same tariff | `ModificationQuote.alternatives` (`available_vehicles()` of the category at the pickup branch); the booking keeps its own tariff | `test_a_busy_vehicle_offers_one_of_the_same_category`, `test_a_busy_vehicle_lists_alternatives`; "offers a vehicle of the same category when this one is not free (UC 4 3a)" |
| 4 for a cancellation, display the refund due | `cancellation_quote()` | `test_the_customer_sees_the_refund_then_cancels` |
| 5 the actor confirms | the password dialog with the amounts; `expected_*` checked on the server | `test_a_changed_price_must_be_confirmed_again`, `test_a_changed_refund_must_be_confirmed_again` |
| 6 update or cancel and notify the actor and the branch | `modify_booking()`, `cancel_booking()`, `_notify(branches=…)` | `test_a_longer_period_is_charged_at_once`, `test_cancelling_48_hours_ahead_refunds_everything` |
| Post-condition: new details, or Cancelled with a refund initiated | as above | as above |

## 3. Exp 3 class diagram

| Exp 3 | Code |
|---|---|
| `Booking.modify_booking()` | `B:bookings/services.py` `modify_booking()` |
| `Booking.cancel_booking()` | `B:bookings/services.py` `cancel_booking()` |
| `Booking.extend_booking()` | `B:bookings/services.py` `extend_booking()` |
| `Booking.status` | `Booking.Status`; transitions in `B:bookings/states.py` |
| `Payment.authorize()`, `Payment.capture()`, `Payment.refund()` | R1's `authorize()`, `capture_charges()`, `refund_payment()` / `refund_deposit()` |
| `Invoice` | debit note (`issue_debit_note()`) and credit notes (R1) |

## 4. Exp 4 messages reused by Module R2

Exp 4 has no sequence diagram for UC 4; the change flows reuse the messages
of sequence 1 (Book Vehicle) and sequence 2 (Return Vehicle):

| Message | Where | Tests |
|---|---|---|
| `Licence.is_valid()` | `_check_licence()` (modify, extend) | `test_br5_and_br2_still_apply_to_the_new_period` |
| `Vehicle.check_availability()` and alt "vehicle not free" | `_vehicle_free()`, `_held_by_others()`, `is_available()` for an alternative | `test_a_busy_vehicle_offers_one_of_the_same_category`, `test_no_extension_into_another_booking_or_its_buffer` |
| `Tariff.calculate_price()` | `booking_quote(pickup=, return_=, add_ons=)` at the booking's tariff | `test_add_ons_keep_their_booked_rate_and_new_ones_take_todays` |
| `Payment.authorize()` and alt "declined" | `_charge_extra()` → `authorize()`; a decline keeps the booking as it was | `test_a_declined_extra_charge_changes_nothing`, `test_a_declined_extension_changes_nothing` |
| `Vehicle.update_status()` | not called: before handover a booking changes no vehicle status (team decision at Book.Done); the release is audited as "Vehicle Released From Booking" | `test_cancelling_48_hours_ahead_refunds_everything` |
| `Invoice.generate_invoice()` | never re-issued; a debit or credit note references it | `test_raising_then_cancelling_refunds_both_payments` |
| `Payment.refund()` (sequence 2) | `refund_payment()`, `refund_deposit()` | the cancel and no-show tests |

## 5. Exp 5 activity diagram and Exp 6 DFD

| Item | Code |
|---|---|
| Exp 5 time event "2 h after pickup, not collected" → "Set No-show, retain 50% (BR-8)" | `declare_no_shows()` and its Celery Beat schedule (migration 0005) |
| Exp 6 process 3.6 "Modify or Extend Booking" (D4 Booking, Payment Gateway) | `modify_booking()`, `extend_booking()` |
| Exp 6 process 3.7 "Cancel Booking and Compute Refund (BR-8)" (refund advice to the customer) | `cancellation_quote()`, `cancel_booking()` |

## 6. Demo (seed_demo)

`B:bookings/seed_changes.py`, loaded by `seed_demo` (additive):
changes@vrms.test (password as the other demo accounts) with two demo
hatchbacks at Andheri. Modify or cancel the booking five days ahead (100 %
refund); move it onto its second booking's day to see the 3a alternatives;
the booking whose pickup was yesterday becomes No-show once Celery Beat runs.
Extend: hand over the handover demo booking (handover@vrms.test) as
staff@vrms.test, then sign in as that customer. Tests: [seed].

## 7. Proposed readings (awaiting team approval)

| # | Item | Proposal |
|---|---|---|
| R2-P1 | Unpaid cash booking | **Not in Appendix B.** A cash-at-collection booking is Pending Payment until staff record the cash (R1-P1). As the team asked: cancelling it is Pending Payment → Cancelled with nothing to refund, and the no-show task makes it Pending Payment → No-show at `NO_SHOW_AFTER` (the end of its R1-P1 hold); the hold sweep no longer returns it to Draft. Only a cash booking may take these two transitions (`states.py`) |
| R2-P2 | Confirming the amounts | The client sends the refund (cancel) or the extra charge and refund (modify, extend) it showed; if the server now computes another amount (BR-8 band crossed, tariff of an alternative, a concurrent change), nothing happens and 409 asks for confirmation again |
| R2-P3 | Changing the pickup branch | A vehicle is collected at the branch it is based at, so a new branch needs a vehicle based there; the 3a alternatives list that branch's free vehicles of the same category |
| R2-P4 | Repricing | At the booking's own tariff (BR-13) and fixed discount amount; kept add-ons keep their booked rate, new ones take today's published rate |
| R2-P5 | BR-8 on a cheaper modification | The excess is refunded at the BR-8 percentage for the notice from the request to the original pickup time; never more than is still refundable |
| R2-P6 | Extra charges | By card or on-line only (cash is for collection, BR-9); authorised at once and captured with the rest at settlement; a Charge ledger entry and a debit note on the invoice. R1's `authorize()` accepts a zero deposit and `record_booking_ledger()` a note for this |
| R2-P7 | Money on cancellation and no-show | `capture_charges()` with no lines captures the authorisation, then the rental share and the whole deposit are refunded; the deposit refund carries BR-14's 7-working-day date like any deposit refund |
| R2-P8 | Extension rules | The new return is later than the current one and in the future; scheduled maintenance windows block it, as they block search |
| R2-P9 | No-show schedule | Every minute; a booking with any handover condition report is skipped (N1), and a row locked by a handover is skipped and seen Active next time; a gateway refusal is logged and retried on the next run |
| R2-P10 | Notifications | E-mail only (the SMS copy of Notify.Booking is Module R3, now built: `docs/traceability-reports.md`); the branch is told of modifications and cancellations (UC 4 step 6), the customer of all four changes |
| R2-P11 | History date range | Filters on the local pickup date, inclusive |
| R2-P12 | Rebook | The vehicle page with a period of the same length from tomorrow at the same time of day; offered for Completed, Cancelled and No-show bookings |
| R2-P13 | Who may change a booking | The customer only (UC 4's actor); staff and administrators cannot |
| R2-P14 | A handover in progress | A Confirmed booking with a handover report can no longer be modified or cancelled |

## 8. Known limits

- The approval limit applies per refund (R1): a rental refund split over the
  original payment and a modification's extra payment can be issued without
  approval even when their sum is above `REFUND_AUTO_APPROVAL_LIMIT`.
- The 100-contender Reliability-1 tests need about 110 free PostgreSQL
  connections; the default `max_connections = 100` skips them with a
  message. Run PostgreSQL with `-c max_connections=200` to include them.
- A Pending Payment cash booking cannot be modified (Book.Modify names a
  Confirmed booking); the customer may cancel and book again.
- No "Soon" placeholder existed for these screens ("My bookings" was already
  available), so none was removed from `navigation.ts`.
