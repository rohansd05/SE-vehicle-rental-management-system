# Traceability: Book Vehicle (Module 1)

Maps every message of Exp 4 sequence diagram 1 ("Book Vehicle"), and every
Exp 3 class-diagram element the module uses, to the code that implements it,
the tests that prove it and the business rules it enforces. SRS:
`docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf` (3.1 Book, 3.2 Search,
3.4 Pay, Appendix B, BR-1 to BR-7, BR-13). The diagram in
`AC_2024300049_ROHAN_SE_EXP4.pdf` is an image; the message list below follows
its transcription in `docs/VRMS_Handoff.md` §4 ("Sequence diagrams").

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`. Test names are pytest functions (file in brackets) or
Vitest `it` titles (in quotes). The end-to-end walk of the whole sequence on
the `seed_demo` data is `B:bookings/tests/test_end_to_end.py`.

## 1. Sequence diagram 1, message by message

The diagram is one interaction; the system serves it as two requests,
because the customer sees the price before paying (proposal BK1):
`POST /api/v1/bookings/` (messages 1–4 and the hold) and
`POST /api/v1/bookings/{id}/pay/` (messages 5–8).

| # | Message (Exp 4, seq. 1) | Requirement / rule | Implemented in | Tests |
|---|---|---|---|---|
| 1 | Customer → Booking: `create_booking()` | Book.Create, Book.Period.Limits (BR-5), Book.Quote.Terms, SA-1 | `B:bookings/lifecycle.py` `create_booking()`; API `BookingListCreateView.post` (`IsCustomer`); UI "Hold this vehicle and pay" in `F:features/booking/VehicleDetailPage.tsx` | `test_a_booking_is_held_for_15_minutes_with_its_price`, `test_the_rental_terms_must_be_accepted`, `test_a_two_wheeler_needs_the_safety_notice`, `test_a_bad_period_is_refused` [test_lifecycle]; `test_create_then_pay`, `test_only_a_customer_can_book`, `test_an_anonymous_visitor_cannot_book` [test_api]; Vitest "holds the vehicle and goes on to payment", "requires the rental terms before holding (Book.Quote.Terms)", "asks for the safety notice on a two-wheeler (SA-1)" |
| 2 | Booking → Licence: `is_valid()` | Book.Eligible.Licence, BR-2 (valid for the whole rental, minimum age), BR-3 (endorsed category), BR-4 (blacklist, dues) | `B:bookings/eligibility.py` `licence_is_valid()` (Exp 3 `Licence.is_valid()`) and `check_eligibility()` | `test_eligibility.py` (all 20 tests, incl. `test_a_licence_expiring_on_the_return_date_is_accepted`, `test_the_minimum_age_on_the_pickup_date`, `test_only_endorsed_categories_may_be_rented`); `test_book_vehicle_main_flow` [test_end_to_end] |
| 2a | alt [licence invalid]: booking refused | Book.Eligible.No | `NotEligibleError(code)` → 400 `{code: licence_not_verified \| licence_expired \| licence_expires_before_return \| licence_category \| under_age \| customer_blacklisted \| outstanding_due}` (`views.refusal`); UI `F:features/booking/BookingRefusal.tsx` offers "Submit your licence", "Keep browsing", "Exit" | `test_an_unverified_licence_refuses_the_booking` [test_lifecycle]; `test_a_licence_problem_is_answered_with_its_code` [test_api]; `test_alt_licence_not_verified_then_verified`, `test_alt_licence_expires_before_return` [test_end_to_end]; Vitest "licence refused (%s): offers to submit a licence, keep browsing or exit (Book.Eligible.No)", "an outstanding due: explains and offers to keep browsing" |
| 3 | Booking → Vehicle: `check_availability()` | Search.Available, BR-1 (60-minute buffer), Book.Hold, Fleet.Add (availability date), Appendix B (bookable status) | `B:fleet/models.py` `Vehicle.check_availability()` → `B:fleet/services/availability.py` `is_available()`; inside `create_booking()` under a vehicle row lock, after releasing expired holds | `test_check_availability_*` (6) [fleet/test_availability]; `test_the_hold_blocks_the_vehicle_for_everyone_else`, `test_an_expired_hold_of_someone_else_is_released_first` [test_lifecycle] |
| 3a | alt [vehicle not free] | Book.NoDouble, Book.Concurrent, Reliability-1 | `VehicleUnavailableError` → 409 `vehicle_unavailable`; the PostgreSQL exclusion constraint `bookings_no_overlapping_vehicle_blocks` is the last word (`_place_hold` turns its `IntegrityError` into the same 409); UI "This vehicle has just been taken" → "Choose another vehicle" | `test_a_confirmed_booking_in_the_period_refuses_the_booking`, `test_a_vehicle_that_cannot_be_handed_over_is_refused`, `test_the_constraint_is_the_last_word` [test_lifecycle]; `test_a_taken_vehicle_is_a_409` [test_api]; `test_exactly_one_of_simultaneous_bookings_succeeds` (2 and 20 threads), `test_without_the_vehicle_lock_the_constraint_still_lets_only_one_through`, `test_overlapping_but_different_periods_also_race_safely` [test_concurrency]; `test_alt_vehicle_not_available` [test_end_to_end]; `test_exclusion_constraint.py` (17); Vitest "vehicle just taken: says so and offers another vehicle" |
| 4 | Booking → Tariff: `calculate_price()` → quotation | BR-6, BR-7, BR-3 (deposit), D14 (tax rate from settings), D17 (discount), BR-13 (tariff in force; snapshot), Book.Quote.Display, Book.Quote.Terms | `B:pricing/services.py` `calculate_price()` (pure), `quote()`, `current_tariff()`; snapshot stored on the booking (`lifecycle._store_price`, `BookingAddOn.daily_rate`); quote API `POST /api/v1/pricing/quote/`; UI `F:features/booking/PriceSummary.tsx` (`PriceSummary`, `TermsList`) | `test_calculate_price.py` (32), `test_quote_service.py` (20), `pricing/tests/test_api.py` (24); `test_a_booking_keeps_its_price_after_a_code_is_edited`, `test_a_price_change_during_the_hold_is_refused` [test_lifecycle]; Vitest "itemises the price with the deposit apart", "re-prices when an add-on and a discount code are chosen", "shows a rejected discount code next to its field" |
| – | (hold) booking Pending Payment for 15 minutes | Book.Hold, Book.Hold.Expire | `lifecycle._place_hold()`; `release_expired_holds()` (on access and by the Celery task `bookings.tasks.release_expired_holds`, scheduled every minute by migration `bookings/0003_schedule_hold_release`); `hold_again()` and `POST /bookings/{id}/hold/`; UI countdown and "Hold the vehicle again" in `F:features/payment/PaymentPage.tsx` | `test_paying_after_the_hold_expired_is_refused_and_releases_it`, `test_the_sweep_releases_only_expired_holds`, `test_an_expired_booking_can_be_held_again_with_its_details`, `test_holding_again_*` (3) [test_lifecycle]; `test_an_expired_hold_is_a_409_and_can_be_held_again` [test_api]; `test_alt_hold_expires_and_is_held_again` [test_end_to_end]; Vitest "an expired hold offers to hold the vehicle again, then pays", "a booking whose hold already lapsed (Draft) starts with the hold-again step", "shows the hold, the price and what will be authorised" |
| 5 | Booking → Payment: `authorize()` | Pay.Authorize, SI-1.1, Pay.Deposit, Pay.Idempotent, SE-9 (re-authentication), CO-2 (token only) | `B:payments/services.py` `authorize()` (one gateway call for rental + deposit, two `CardPayment` rows sharing the gateway reference); `integrations/payment_gateway` (mock: `tok_decline` declines); password check in `BookingPayView`; UI `F:features/payment/PaymentPage.tsx` (sandbox token, password, a fresh idempotency key per attempt) | `test_payment_confirms_the_booking_in_one_transaction`, `test_the_same_key_never_charges_twice`, `test_a_new_key_on_a_confirmed_booking_is_refused`, `test_a_fully_discounted_rental_authorises_only_the_deposit` [test_lifecycle]; `test_a_wrong_password_stops_the_payment_and_is_audited`, `test_the_password_is_never_echoed`, `test_a_bad_idempotency_key_is_refused` [test_api]; `test_the_token_is_never_copied_into_the_audit_log` [payments/test_services]; Vitest "pays with a sandbox token and the password, then confirms the booking (Pay.Confirm.OK)", "a wrong password is shown on the password field (SE-9)", "asks for the password before sending anything" |
| 5a | alt [declined]: hold retained | BK2; SRS 3.4.2 (show the reason) | `PaymentDeclinedError` → 402 `payment_declined`; failed `CardPayment` rows kept with `failure_reason`; booking stays Pending Payment | `test_a_declined_payment_keeps_the_hold_and_can_be_retried`, `test_repeating_a_declined_key_does_not_call_the_gateway_again` [test_lifecycle]; `test_a_declined_payment_is_a_402_and_keeps_the_hold` [test_api]; `test_alt_payment_declined_hold_retained`, `test_book_vehicle_main_flow` [test_end_to_end]; Vitest "a declined card keeps the hold; another card works with a new key" |
| 6 | Booking → Vehicle: `update_status()` | Book.Done.Block, BR-1; Appendix B | Team decision (11 Oct 2026): confirmation changes no vehicle status (Appendix B moves to On Rent only at handover). The message is the block: the Confirmed booking's `blocked_period` under the exclusion constraint, plus the audit entry "Vehicle Blocked For Booking" (`lifecycle._confirm`). `Vehicle.update_status()` itself is `B:fleet/services/status.py` (Module 2) | `test_payment_confirms_the_booking_in_one_transaction` (status still Available; audit entry), `test_the_vehicle_status_is_untouched_by_confirmation` [test_api]; `test_book_vehicle_main_flow` (vehicle left out of search after confirmation) [test_end_to_end] |
| 7 | Booking → Invoice: `generate_invoice()` | Pay.Invoice (unique sequential number INV-YYYY-NNNNNN, agency tax registration, itemised lines, taxes; immutable), Pay.Ledger, History.Download | `B:payments/services.py` `issue_invoice()`, `record_booking_ledger()`; `B:bookings/numbering.py` `next_in_sequence()`; PDF `B:payments/pdf.py` (ReportLab), `GET /bookings/{id}/invoice/`; UI "Download invoice …" in `F:features/history/BookingDetailPage.tsx` | `test_payment_confirms_the_booking_in_one_transaction`, `test_references_and_invoice_numbers_are_sequential`, `test_add_ons_are_invoiced_per_line`, `test_the_discount_is_used_up_and_invoiced` [test_lifecycle]; `test_the_invoice_downloads_as_a_pdf`, `test_a_held_booking_has_no_invoice_yet` [test_api]; `test_the_pdf_renders_the_issued_invoice`, `test_numbers_run_in_sequence_inside_a_transaction` [payments/test_services]; `payments/tests/test_append_only.py`; Vitest "downloads the invoice PDF with the access token", "says so when the invoice cannot be downloaded" |
| 8 | status Confirmed, pickup code returned → Customer | Book.Done (one transaction), Book.Done.Store (reference VRMS-YYYYMMDD-NNNN, six-digit code), Book.Done.Failure, Pay.Confirm.OK | `lifecycle._confirm()` via `states.transition()` (Pending Payment → Confirmed); confirmation page `F:features/history/BookingDetailPage.tsx` (reference, pickup code, transaction, invoice) | `test_payment_confirms_the_booking_in_one_transaction`, `test_a_failure_after_authorisation_rolls_everything_back` [test_lifecycle]; `test_create_then_pay` [test_api]; `test_book_vehicle_main_flow` [test_end_to_end]; Vitest "shows the reference, pickup code, transaction, invoice and price" |

## 2. Class-diagram elements (Exp 3) used by the module

| Element | Implemented in | Behaviour | Tests |
|---|---|---|---|
| `Customer` (customer_id, date_of_birth, is_blacklisted, outstanding_due) | `B:accounts/models.py` | BR-2 age, BR-4 blacklist and dues read by `check_eligibility()` | `test_a_blacklisted_customer_cannot_book`, `test_a_customer_with_a_due_cannot_book`, `test_the_minimum_age_on_the_pickup_date` |
| `Customer.search_vehicle()` | `B:fleet/services/availability.py` `available_vehicles()`; `GET /api/v1/fleet/search/`; `F:features/search/SearchPage.tsx` | Search.Available, Search.Price (estimate per result) | `fleet/tests/test_availability.py` (53), `fleet/tests/test_search_api.py` (48); Vitest `search.test.tsx` (15) |
| `Customer.view_history()` | `GET /api/v1/bookings/` (scoped, newest pickup first); `F:features/history/BookingHistoryPage.tsx` | History.View, History.Privacy | `test_the_history_lists_own_bookings_newest_pickup_first`, `test_another_customers_booking_is_invisible`, `test_branch_staff_see_their_branchs_bookings_without_the_pickup_code` [test_api]; Vitest "lists the customer’s bookings with their status and amount", "filters by status", "pages through a long history" |
| `Licence` (licence_number, category, expiry_date, status; `is_valid()`) | `B:accounts/models.py`; `is_valid()` → `B:bookings/eligibility.py` `licence_is_valid()` | Section 1, message 2 | Section 1, message 2 |
| `Licence.verify()` | `B:accounts/services.py` `approve_licence()` (Phase 1B) | A pending licence becomes bookable once verified | `test_alt_licence_not_verified_then_verified` [test_end_to_end] |
| `Booking` (booking_reference, pickup/return datetime, status, pickup_code, total_amount) | `B:bookings/models.py` | Appendix B state machine `B:bookings/states.py`; price snapshot (tariff, total, deposit, discount, add-on rates); blocked period + exclusion constraint | `test_states.py` (52), `test_models.py`, `test_exclusion_constraint.py` |
| `Booking.create_booking()` | `B:bookings/lifecycle.py` `create_booking()` | Section 1, messages 1–4 | Section 1 |
| `Vehicle` (registration_no, brand, model, odometer, status), `Car`, `TwoWheeler` | `B:fleet/models.py`; detail `GET /api/v1/fleet/vehicles/{id}/` (`VehicleDetailSerializer`); `F:features/booking/VehicleDetailPage.tsx` | Search.Detail: photographs, specification, tariff, deposit, policies, rating, last service; Retired is never shown (Fleet.Retire) | `test_vehicle_detail_api.py` (8); Vitest "shows the photographs, specification, tariff, deposit, rating, last service and policies" |
| `Vehicle.check_availability()` | `B:fleet/models.py` → `availability.is_available()` | Section 1, message 3 | Section 1, message 3 |
| `Vehicle.update_status()` | `B:fleet/services/status.py` (Module 2); its transition table decides which statuses are bookable (`availability.bookable_statuses()`) | Section 1, message 6 | `test_bookable_statuses_come_from_the_status_service` |
| `Branch` (branch_id, branch_name, serviceable_areas) | `B:fleet/models.py`; `GET /api/v1/fleet/branches/` | The pickup branch of a search and a booking | `test_branches_are_listed_by_name`, `test_a_vehicle_of_another_branch_is_not_found` |
| `Tariff` (hourly_rate, daily_rate, security_deposit, effective_from; `calculate_price()`) | `B:pricing/models.py`, `B:pricing/services.py` | Section 1, message 4. PR3: the weekly rate is not applied; PR4: the deposit is BR-3's, not the tariff field | `test_the_weekly_rate_is_never_applied`, `test_the_deposit_is_br3s_amount_for_the_vehicle_type`, `TestTariffImmutability` (BR-13) |
| `Payment` (transaction_id, amount, status, timestamp; `authorize()`), `CardPayment` (card_token, card_brand) | `B:payments/models.py`, `B:payments/services.py` `authorize()` | Section 1, message 5. `capture()` and `refund()` (SI-1.2, SI-1.3) are built in Module R1 (`docs/traceability-payments.md`) | Section 1, message 5 |
| `Invoice` (invoice_number, issue_date, tax_amount, total_amount; `generate_invoice()`) | `B:payments/models.py` (append-only), `issue_invoice()`, `pdf.py` | Section 1, message 7 | Section 1, message 7 |
| Composition Booking ◆ Invoice | `Invoice.booking` OneToOne, PROTECT | One invoice per booking | `test_the_same_key_never_charges_twice` (one invoice after a repeat) |
| Association Booking–Payment (1:1..*) | `Payment.booking` FK | Rental and deposit rows, plus declined attempts | `test_a_declined_payment_keeps_the_hold_and_can_be_retried` |
| Dependency Booking ⇢ Licence «verifies» | `check_eligibility()` reads `customer.licence` | Section 1, message 2 | Section 1, message 2 |
| Dependency Vehicle ⇢ Tariff «priced by» | `current_tariff(vehicle.category)`, `tariffs_in_force()` | BR-13: the tariff in force when quoted; kept on the booking | `test_the_latest_tariff_already_in_force_is_used`, `test_the_estimate_uses_each_categorys_tariff_in_force` |
| Additions: `AddOn`, `BookingAddOn`, `DiscountCode`, `LedgerEntry`, `AuditLog` | `B:pricing/models.py`, `B:bookings/models.py`, `B:payments/models.py`, `B:core/models.py` | Book.Addons (BR-7), D17, Pay.Ledger, SE-10 | `test_add_ons_are_charged_per_billed_day_and_quantity`, `test_the_discount_is_used_up_and_invoiced`, ledger and audit assertions in `test_payment_confirms_the_booking_in_one_transaction` and `test_book_vehicle_main_flow` |

## 3. Business rules

| Rule | Where enforced | Tests |
|---|---|---|
| BR-1 one confirmed booking at a time + 60-minute buffer | `Booking.compute_blocked_period()` + exclusion constraint; `availability.requested_block()` | `test_pickup_after_an_earlier_booking_respects_the_buffer`, `test_return_before_a_later_booking_respects_the_buffer`, `test_search_agrees_with_the_exclusion_constraint`, `test_booking_inside_the_turnaround_buffer_is_rejected` |
| BR-2 licence valid for the whole rental; age 18/21 | `eligibility.licence_is_valid()`, `check_eligibility()` | `test_a_licence_expiring_during_the_rental_is_refused`, `test_the_minimum_age_on_the_pickup_date` |
| BR-3 endorsed categories; deposit 2,000 / 5,000 | `licence_is_valid()`; `pricing.services.security_deposit_for()` | `test_only_endorsed_categories_may_be_rented`, `test_the_deposit_is_br3s_amount_for_the_vehicle_type` |
| BR-4 no booking when blacklisted or owing | `check_eligibility()` | `test_a_blacklisted_customer_cannot_book`, `test_a_customer_with_a_due_cannot_book` |
| BR-5 4 hours to 30 days | `availability.check_period()` (search, quote, booking) | `test_a_period_outside_the_rules_is_refused`, `test_the_br5_limits_themselves_are_allowed` |
| BR-6 charge = tariff + add-ons + taxes − discount; days/hours/grace | `pricing.services.billing_period()`, `calculate_price()` (PR1, PR2, PR5–PR8) | `test_billing_period` (10 cases), `test_a_percent_discount_comes_off_before_tax`, `test_amounts_are_rounded_half_up_to_the_paisa` |
| BR-7 add-ons at the daily rate; one free helmet per rider | `calculate_price()`; `PriceSummary` | `test_add_ons_are_charged_per_billed_day_and_quantity`, `test_one_free_helmet_per_rider_with_a_two_wheeler_only` |
| BR-13 tariff never alters a confirmed booking | price snapshot on the booking; `Tariff.save()` guard | `test_a_booking_keeps_its_price_after_a_code_is_edited`, `TestTariffImmutability` |
| D14 tax rate from settings (placeholder 18%) | `settings.TAX_RATE_PERCENT` read by `calculate_price()` | `test_the_tax_rate_comes_from_the_business_rules_settings` |
| SE-4 / SE-5 access and scoping | explicit `permission_classes`; `views.scoped_bookings()` | `test_only_a_customer_can_book`, `test_staff_cannot_pay_or_hold`, `test_another_customers_booking_is_invisible`, `test_every_visitor_may_search_and_browse`, `test_only_a_customer_can_quote` |
| SE-9 re-authentication before payment | `BookingPayView` password check | `test_a_wrong_password_stops_the_payment_and_is_audited` |
| SE-10 audit of every step | `record_audit` in the lifecycle, payments and state machine | `test_payment_confirms_the_booking_in_one_transaction` (eight steps in order, chain verified) |
| CO-6 Decimal money, UTC time | `DecimalField`/`Decimal` everywhere; ISO UTC in the API | `test_every_amount_is_a_decimal`, `test_a_local_time_with_an_offset_is_understood`, `test_the_availability_date_is_read_in_local_time` |

## 4. Decisions and proposals this module relies on

Team decisions (11 Oct 2026): PR1–PR4 (pricing: discount before tax; 24 h = 1 day, part-days round up;
weekly rate not applied; BR-3 deposit), confirmation changes no vehicle status, one authorisation for
rental + deposit, invoice numbers INV-YYYY-NNNNNN, Search.Available read literally (status must be
Available now), seed counts updated and `pending@vrms.test` added.

Proposed, awaiting approval (marked in the code): S1 (pickup in the future), PR5–PR10 (rounding,
fixed-discount cap, no hourly cap, add-on days, estimate contents, code use at confirmation),
BK1–BK11 (two-request flow, decline keeps the hold, hold expiry, eligibility on the pickup date,
terms and SA-1 required, reference and pickup code, price snapshot, code used at confirmation,
invoice at confirmation, notifications, cash and delivery not built), the SA-1 notice wording.

## 5. Not built in Module 1

Book.Done.Customer / Book.Done.Branch notifications (blocked by
`apps/notifications/tests/test_delivery.py`, see Stage 3 summary); cash at the branch (BR-9, built in Module R1);
doorstep delivery (Book.Deliver.Location; the add-on is refused online); Book.Modify, Book.Cancel,
Book.Extend; capture and refund (SI-1.2, SI-1.3, built in Module R1); History.View date-range filter; nearest
alternatives when nothing is free (SRS 3.2.2); the Search.Filter filters beyond category.

## 6. Demo data

`B:bookings/seed.py`, called from `seed_demo` (one-line additions): four Available vehicles at
Andheri (MH02DB2001–2004) and `pending@vrms.test` (licence Pending Verification). Tests:
`B:bookings/tests/test_seed.py`, `B:core/tests/test_seed_demo.py`.
