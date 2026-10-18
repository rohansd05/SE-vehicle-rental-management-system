# Traceability: Return Vehicle and settlement (Module N2)

Maps every requirement of SRS 3.3 that covers the return (Return.Checklist,
Return.Odometer, Return.Charges, Return.Settle, Return.Complete, Return.Flag),
Exp 2 use case 8 with its include "Calculate Settlement Charges" and extend
"Flag Vehicle for Maintenance", every message of Exp 4 sequence diagram 2,
the Exp 5 return fork/join, DFD process 6 with its Level 2 processes 6.1 to
6.6, and BR-10, BR-11, BR-12 and BR-14 to the code and the tests. SRS:
`docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf` (3.3, 3.4 Pay.Dues,
Pay.Refund, Pay.Invoice, 5.5, Appendix A and B). Proposed readings N2-P1 to
N2-P10 are in section 9 and in `docs/model-mapping.md`, section 5 (P25 to P34).

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`. Test names are pytest functions or Vitest `it` titles;
`[return]` = `B:rentals/tests/test_return.py`, `[api]` = `test_return_api.py`,
`[settlement]` = `test_settlement.py`, `[seed]` = `test_seed.py`.

## 1. Requirements

| Requirement | Implemented in | Tests |
|---|---|---|
| UC 8 step 1: open the return checklist for the booking | `B:rentals/services.py` `branch_returns()` (Active, due today or overdue, or a search by reference or mobile); API `GET /api/v1/rentals/returns/?q=` and `GET …/returns/{id}/` (`ReturnDetailSerializer`); UI "Returns due today" and "Rentals in progress" in `F:features/handover/CollectionsPage.tsx`, page `F:features/handover/ReturnPage.tsx` (`/app/returns/:id`), "Record the return" on an Active handover | `test_branch_returns_lists_due_and_overdue_rentals_and_finds_any_active_one` [return]; `test_returns_lists_only_the_callers_branch`, `test_a_branch_manager_finds_a_rental_by_reference`, `test_detail_shows_the_handover_report_what_is_paid_and_the_terms` [api]; Vitest "lists the rentals due back today, each opening its return", "a search also finds a rental in progress", "an Active handover links to its return" |
| UC 8 precondition "The booking has status Active": Cancelled, No-show, Pending Payment, Confirmed (and Completed, Draft) refused with the reason | `services.return_refusals()` (`RETURN_REFUSALS`), `ReturnRefusedError` → 409 `{code: "return_refused", refusals}` | `test_only_an_active_booking_can_be_returned` (6 statuses, quote and completion), `test_an_active_booking_without_a_handover_report_is_refused` [return]; `test_quoting_a_booking_not_handed_over_is_409_with_the_reason`, `test_a_cancelled_booking_cannot_be_returned` [api]; Vitest "states why and offers no checklist" |
| **Return.Checklist**: odometer, fuel or charge level, accessories returned, the actual return time, at least four photographs | `ReturnReadings`, `services._accessories()` (issued at handover less the missing ones), `_check_return_time()` (N2-P8); `B:rentals/serializers.py` `ReturnReadingsSerializer`, `ReturnSerializer` (photo_front/rear/left/right required, as at handover); UI `F:features/handover/ReturnForm.tsx` | `test_an_on_time_return_completes_and_refunds_the_whole_deposit`, `test_the_return_time_lies_between_the_handover_and_now` (2), `test_a_missing_accessory_is_charged_at_the_cost_entered`, `test_an_accessory_never_issued_cannot_be_missing` [return]; `test_an_incomplete_return_is_400` (6) [api]; Vitest "asks for the readings before computing anything, and for the settlement before settling" |
| Return.Checklist: "display the handover and return photographs together so that new damage can be identified" | `ReturnDetailSerializer.handover_report` (signed links, SI-3); UI `F:features/handover/PhotoCompare.tsx`: in the form each side's handover photo beside its picker (`HandoverPhoto`), once returned each side at handover beside the same side at return (`PhotoCompare`); new damage on `VehicleDiagram.tsx` (reused from N1) | `test_complete_returns_the_signed_settlement` [api]; Vitest "records the return beside the handover photos, itemises it, and settles once signed" |
| **Return.Odometer**: a reading lower than the handover reading is rejected (UC 8 extension 2a) | `settlement.calculate_settlement()` raises `odometer_lower`; `services._settlement()` → 400 on `odometer_reading` | `test_a_reading_below_the_handover_reading_is_rejected` [settlement]; `test_a_reading_below_the_handover_is_rejected_for_correction` [return]; `test_a_reading_below_the_handover_is_400_on_the_field` [api]; Vitest "shows the server’s reason when the odometer is below the handover reading" |
| Return.Odometer: above "the configured plausibility limit", a supervisor override with a recorded reason (N2-P7) | `settlement.plausibility_limit()` (`ODOMETER_PLAUSIBILITY_KM_PER_DAY` in `backend/config/settings/business_rules.py`); `services._odometer_override()`: a Branch Manager of the branch or an Administrator signs in on the branch device through `authenticate()` (django-axes, SE-8); stored in `ConditionReport.odometer_override_by` and `odometer_override_reason`, audited "Odometer Override Approved" with the supervisor as actor; quote's `override_required`; UI supervisor fields in `ReturnForm.tsx` | `test_plausibility_limit_per_started_day` (5) [settlement]; `TestOdometerOverride` (7) [return]; `test_an_implausible_distance_without_an_override_is_400` [api]; Vitest "an implausible distance needs a supervisor’s approval and a reason" |
| Return.Odometer → DE-3, BR-15: the vehicle's odometer is updated at every return | `services._record_odometer()` (never decreases; audited "Odometer Recorded") | `test_an_on_time_return_completes_and_refunds_the_whole_deposit` [return]; `test_complete_returns_the_signed_settlement` [api] |
| **Return.Charges**: as separate items, excess km (BR-11), fuel shortfall (BR-12), late return (BR-10), any accessory not returned, damage entered by the staff member with a justification; UC 8 step 3 (include: Calculate Settlement Charges) | `B:rentals/settlement.py` (pure, 100% statement and branch coverage): `late_return()`, `excess_km()`, `fuel_shortfall()`, `calculate_settlement()` → one `ChargeItem` per charge, then tax (N2-P4); staff charges `ExtraCharge` (N2-P5); API `POST …/returns/{id}/quote/` (nothing saved); UI `F:features/handover/SettlementSummary.tsx` | all of [settlement] (41); `test_late_over_the_allowance_and_short_of_fuel_each_a_line_and_a_debit_note`, `test_damage_is_charged_with_its_justification` [return]; `test_quote_itemises_the_settlement_and_saves_nothing` [api]; Vitest "records the return beside the handover photos, itemises it, and settles once signed" |
| UC 8 step 4: the settlement presented to the customer for acknowledgement (Exp 5 "Acknowledge itemized settlement") | UI: the settlement table, then the customer signs on `SignaturePad` (reused from N1; a new settlement clears the signature); the signature is the return report's customer signature (Appendix A, N2-P9); `expected_total` must equal the recomputed total, else 409 `settlement_changed` | `test_changed_charges_change_nothing` [return]; `test_changed_charges_are_409_and_change_nothing` [api]; Vitest "a changed reading makes the customer see the settlement again" |
| **Return.Settle**: deduct the charges from the deposit, refund the balance (BR-14), record a due if the charges exceed it (Pay.Dues, BR-4) | `services._settle()`: `capture_charges()`, `issue_debit_note()`, `refund_deposit()`, `record_due()` of `B:payments/services.py` only (section 7) | `test_an_on_time_return_completes_and_refunds_the_whole_deposit`, `test_late_over_the_allowance_and_short_of_fuel_each_a_line_and_a_debit_note`, `test_charges_above_the_deposit_become_a_due` [return]; `test_charges_below_the_deposit_leave_a_balance_to_refund_br14` [settlement] |
| Pay.Idempotent: a double click on Settle never charges twice | one transaction under the booking row lock; a Completed booking with a return report returns that report; `capture_charges(idempotency_key=f"return-{booking.pk}")`; `refund_deposit()`'s own per-booking key; `record_due()` runs once inside the same transaction | `test_settling_twice_never_charges_twice` (one due, no new ledger entry) [return]; `test_a_double_click_on_settle_charges_once` [api] |
| Pay.Refund, UC 13: a refund above `REFUND_AUTO_APPROVAL_LIMIT` waits; the completed booking shows "Refund awaiting approval", not "Refunded" | `services.deposit_refund()`, `settlement_record()["refund_status"]`; e-mail text; UI `refundText()` in `ReturnPage.tsx` | `test_a_refund_above_the_approval_limit_waits_for_an_administrator` [return]; `test_the_settlement_shows_a_refund_awaiting_approval` [api]; Vitest "says the refund is awaiting approval, not refunded" |
| Pay.Refund, BR-9: a cash deposit is refunded in cash by a named staff member | `refund_deposit(…, initiated_by=staff)` issues a `CashPayment` naming them with the customer's acknowledgement time; `deposit_method`; `settlement_record()["refund_paid_out_by"]`; UI notice on the settle screen and "Refunded in cash by …" | `test_a_cash_deposit_is_paid_back_in_cash_by_the_staff_member` [return]; Vitest "a cash deposit is refunded in cash by the staff member, who is named", "names who paid a cash refund out" |
| R2: extended or modified bookings settle on their CURRENT return time, allowance and tariff; an extension already paid is shown as paid, never charged again | `_settlement()` passes `booking.return_datetime` and `booking.tariff`; rental is never a charge line; `services.rental_paid()` (the ledger's rental Charge entries) → `ReturnDetail.rental_paid` and "Already paid" in `SettlementSummary.tsx` | `test_the_allowance_and_lateness_follow_the_current_return_time` [settlement]; `test_an_extended_booking_returned_on_time_is_not_late_and_the_extension_is_paid`, `test_an_extended_booking_returned_late_is_late_from_the_extended_time` [return] (through R2's real `extend_booking()`) |
| **Return.Complete**: booking Completed, total distance recorded, vehicle Available, or Under Maintenance if flagged | `B:bookings/states.py` `complete_booking()` (added for N2, sets `returned_at` and `distance_travelled`); `B:fleet/services/status.py` `update_status()` (On Rent → Available / Under Maintenance; unchanged, both transitions already there); an Unsafe vehicle stays Unsafe (SA-2) | `TestCompleteBooking` (5), `test_an_on_time_return_completes_and_refunds_the_whole_deposit`, `test_an_unsafe_flag_raised_during_the_rental_stays`, `test_a_failure_after_the_money_rolls_everything_back` [return] |
| **Return.Flag**: flag during the return with the problem and its severity; a maintenance job created automatically (Maint.Create); Under Maintenance if unfit (UC 8 extension 3a) | `services._flag_vehicle()` → `B:maintenance/services.py` `report_job()` (Corrective, N2-P6); `ConditionReport.maintenance_job`; UI "Flag for maintenance" in `ReturnForm.tsx` | `test_flagging_raises_a_job_and_an_unfit_vehicle_goes_under_maintenance` (2), `test_a_flag_the_maintenance_service_refuses_stops_the_return` [return]; `test_flagging_needs_a_severity_and_whether_the_vehicle_is_fit`, `test_a_flagged_unfit_vehicle_goes_under_maintenance` [api]; Vitest "flags the vehicle for maintenance with the problem and severity" |
| Handover.Sign rules for the return report: signed, then never altered | the return is a second `ConditionReport` (report_type Return) through `capture_report()`; migration 0002's triggers and the model guards apply; migration `B:rentals/migrations/0003_return_settlement.py` adds `charges` (the signed settlement) and `maintenance_job` | `test_one_handover_and_one_return_report_per_booking`, `TestSignedReportIsFinal` [test_models]; [test_append_only] |
| Exp 5 "Send settlement and refund notification", "Receive settlement statement" | `queue_email(…, "return_settlement")` through Celery after commit (template in `B:rentals/notification_templates.py`); R1 e-mails the refund itself | `test_an_on_time_return_completes_and_refunds_the_whole_deposit` (Notification Sent, outbox), `test_the_settlement_e_mail_renders` [return] |
| SE-4, SE-5: a permission class on every endpoint, own branch only | `BRANCH_TEAM` (list, detail) and `IsBranchStaff` (quote, complete) in `B:rentals/views.py`; `scoped_bookings()` (`scope_queryset()`); the service checks the staff member's branch again | `test_endpoint_permission` (7 endpoints × 6 roles), `test_every_rentals_route_is_in_the_matrix` [test_permissions]; `test_a_booking_of_another_branch_is_not_found` [api]; `test_staff_of_another_branch_cannot_take_it_back` [return]; Vitest "a Branch Manager sees the rental read only" |
| SE-10: every step audited | "Condition Report Signed", "Odometer Override Approved", the payments entries (R1), "Odometer Recorded", "Vehicle Status Changed", "Booking Status Changed", maintenance "Create" | `test_an_on_time_return_completes_and_refunds_the_whole_deposit` (`verify_chain()`) [return] |

## 2. Exp 4 sequence diagram 2 (Return Vehicle), message by message

| # | Message | Implemented in | Tests |
|---|---|---|---|
| 1 | BranchStaff → :ConditionReport `capture_report()` | `services.return_vehicle()` → `capture_report(report_type=Return)` | `test_an_on_time_return_completes_and_refunds_the_whole_deposit` |
| 2 | alt [return odometer < handover odometer] "entry rejected, correction required" | `calculate_settlement()` `odometer_lower` → 400 on `odometer_reading`; nothing stored | `test_a_reading_below_the_handover_is_rejected_for_correction`, `test_a_reading_below_the_handover_is_400_on_the_field` |
| 3 | [odometer reading valid] "condition report stored" | the signed report, audited | `test_complete_returns_the_signed_settlement` |
| 4 | BranchStaff → :Tariff `calculate_price()` | `settlement.calculate_settlement()` at the booking's own tariff (BR-13), via `return_quote()` and again inside `return_vehicle()` | [settlement] |
| 5 | self "excess km, fuel, late return (BR-10 to BR-12)" | `late_return()`, `excess_km()`, `fuel_shortfall()` | `test_late_return_br10`, `test_excess_km_br11`, `test_fuel_shortfall_at_the_price_plus_20_percent_br12` |
| 6 | "itemised settlement" | `ReturnQuote` → `POST …/quote/`; `SettlementSummary.tsx` | `test_quote_itemises_the_settlement_and_saves_nothing` |
| 7 | BranchStaff → :Payment `refund()` | `services._settle()` → `capture_charges()` then `refund_deposit()` (→ R1's `refund_payment()`, Exp 3 `Payment.refund()`), or `record_due()` | `test_late_over_the_allowance_and_short_of_fuel_each_a_line_and_a_debit_note`, `test_charges_above_the_deposit_become_a_due` |
| 8 | "deposit balance refunded (BR-14)" | `RefundRequest` Issued (or Pending Approval, UC 13), `refund_due_by` 7 working days | `test_an_on_time_return_completes_and_refunds_the_whole_deposit`, `test_a_refund_above_the_approval_limit_waits_for_an_administrator` |
| 9 | opt [new damage or fault identified] BranchStaff → :MaintenanceJob `schedule_job()` | `_flag_vehicle()` → `report_job()` (Maint.Create, as the user asked for N2; the job is Reported, then scheduled in the maintenance screens as usual) | `test_flagging_raises_a_job_and_an_unfit_vehicle_goes_under_maintenance` |
| 10 | :MaintenanceJob → :Vehicle `update_status()`; "status = Under Maintenance" | `update_status(Under Maintenance)` when the flagged vehicle is unfit | same, unfit case |
| 11 | alt [vehicle not flagged] BranchStaff → :Vehicle `update_status()`; "status = Available" | `update_status(Available)` (also when flagged but fit) | `test_an_on_time_return_completes_and_refunds_the_whole_deposit`, fit case |
| 12 | BranchStaff → :Booking "status = Completed" | `complete_booking()` | `TestCompleteBooking` |
| 13 | "settlement recorded" | `ConditionReport.charges`, `settlement_record()`, `ReturnDetail.settlement` (201) | `test_complete_returns_the_signed_settlement` |

The job is raised before the report is signed (a signed report cannot
change, and it records the job), all in one transaction, so the order
inside it does not change the outcome.

## 3. Exp 5 activity diagram, Phases 4 and 5 (return), node by node

| Node | Implemented in | Tests |
|---|---|---|
| Return vehicle to branch → Open return checklist, record readings and photos | `ReturnPage.tsx`, `ReturnForm.tsx` | Vitest "records the return beside the handover photos, …" |
| Decision "Odometer valid?" [No] → Reject entry, require correction | 400 `odometer_lower` | `test_a_reading_below_the_handover_is_400_on_the_field` |
| Compute settlement: excess km, fuel, late return (BR-10..12) | `calculate_settlement()` | [settlement] |
| Acknowledge itemized settlement (Customer) | the customer's signature after the settlement table | Vitest "a changed reading makes the customer see the settlement again" |
| Fork: Receive settlement statement ∥ Record cash refund if paid in cash (BR-9) ∥ Deduct charges from deposit, set booking Completed ∥ Send settlement and refund notification | one POST `…/returns/{id}/complete/` → `return_vehicle()`: the `return_settlement` e-mail; the cash refund by the staff member (`refund_deposit()`); `_settle()` and `complete_booking()`; R1's refund e-mail | `test_an_on_time_return_completes_and_refunds_the_whole_deposit`, `test_a_cash_deposit_is_paid_back_in_cash_by_the_staff_member` |
| Join | the transaction commits as a whole; the e-mails go after commit | `test_a_failure_after_the_money_rolls_everything_back` |
| Decision "Damage found?" [Yes] → Flag vehicle, state problem and severity → Create maintenance job (Reported) | `_flag_vehicle()` → `report_job()` | `test_flagging_raises_a_job_…` |
| Refund above threshold? → Approve or reject refund (Administrator) → Refund deposit balance within 7 days (BR-14) | R1: `refund_payment()` above `REFUND_AUTO_APPROVAL_LIMIT`, `/app/refunds` | `test_a_refund_above_the_approval_limit_waits_for_an_administrator` |

## 4. Exp 3 class diagram

| Class / method | Implemented in | Tests |
|---|---|---|
| `BranchStaff.return_vehicle()` | `services.return_vehicle()` | `TestReturnVehicle` |
| `ConditionReport.capture_report()` | `services.capture_report(report_type=Return, …)` | `test_an_on_time_return_completes_…` |
| `Tariff.calculate_price()` (settlement under BR-10 to BR-12) | `settlement.calculate_settlement()` | [settlement] |
| `Payment.refund()` | R1 `refund_deposit()` → `refund_payment()` | `test_a_cash_deposit_is_paid_back_…`, `test_a_refund_above_…` |
| `Payment.capture()` | R1 `capture_charges()` | `test_late_over_the_allowance_…` |
| `MaintenanceJob` (created) | `report_job()` | `test_flagging_raises_a_job_…` |
| `Vehicle.update_status()` | `fleet/services/status.update_status()` | `test_flagging_raises_a_job_…` (2) |
| Booking ◆ ConditionReport (0..2) | the unique (booking, report_type) constraint | `test_one_handover_and_one_return_report_per_booking` |

## 5. DFD process 6 (Handle Vehicle Return and Settlement) and Level 2

| Process / flow | Implemented in |
|---|---|
| 6.1 Record Return Checklist: Branch Staff → readings, photos; → D6 Condition Report | `ReturnSerializer`; `capture_report()` |
| 6.2 Validate Odometer: D6 → handover reading; → valid | `calculate_settlement()` (`odometer_out` from the handover report), `_odometer_override()` |
| 6.3 Compute Settlement Charges (BR-10..12): D3 Tariff →; → charges | `calculate_settlement(tariff=booking.tariff)`; `FuelPrice` read for BR-12 |
| 6.4 Settle Deposit and Refund: ↔ Payment Gateway; → D5 Payment Ledger; → settled | `_settle()` → `capture_charges()`, `issue_debit_note()`, `refund_deposit()`, `record_due()` (mock gateway in tests) |
| 6.5 Flag Vehicle for Maintenance: settled →; → D7 Maintenance Job; → job raised | `_flag_vehicle()` → `report_job()` |
| 6.6 Close Booking and Update Status: Customer → acknowledgment; → D4 Booking | the customer's signature; `complete_booking()`; `update_status()` |
| 5 → 6 active rental (Level 1) | the Active booking and its handover report (N1) |
| 6 → 7 damage flag (Level 1) | `report_job()` |

## 6. Business rules

| Rule | Where | Tests |
|---|---|---|
| BR-10: 15 minutes' grace, then the hourly rate, capped at one day per 24 h, over 6 h a full day | `settlement.late_return()`; `LATE_RETURN_GRACE`, `LATE_RETURN_DAILY_CAP_PERIOD`, `LATE_RETURN_FULL_DAY_AFTER` (existing) | `test_late_return_br10` (11 cases), `test_late_hours_are_capped_at_one_days_rate` |
| BR-11: beyond the booking's free allowance at the excess-km rate | `settlement.excess_km()`; `free_km_allowance` × billed days (N2-P2) | `test_excess_km_br11` (4) |
| BR-12: shortfall at the prevailing price plus 20% | `settlement.fuel_shortfall()`; `FUEL_SHORTFALL_SERVICE_CHARGE_PERCENT` (existing); `FuelPrice` in force at the return | `test_fuel_shortfall_at_the_price_plus_20_percent_br12`, `test_a_missing_capacity_is_refused`, `test_a_missing_fuel_price_is_refused` |
| BR-14: the balance refunded to the original instrument within 7 working days | R1 `refund_deposit()` | `test_an_on_time_return_completes_and_refunds_the_whole_deposit` |
| BR-4 / Pay.Dues: charges above the deposit are a due that blocks new bookings | R1 `record_due()` | `test_charges_above_the_deposit_become_a_due` |
| BR-13: the tariff the booking was priced at | `booking.tariff` | `test_the_allowance_and_lateness_follow_the_current_return_time` |
| BR-6: "plus taxes" on usage-based charges (D14 rate) | the tax line (N2-P4) | `test_every_charge_is_a_separate_line_then_the_tax` |
| BR-1: the 60-minute turnaround buffer in Maint.Conflict | `B:maintenance/services.py` `conflicting_bookings()` now overlaps the booking's `blocked_period` (return + buffer) | `test_conflicts_honour_the_br1_turnaround_buffer` (2) [maintenance/test_services] |

## 7. How return charges use `capture_charges` and `issue_debit_note`

`services._settle()` calls only R1's documented functions
(`docs/payments-api.md`), inside the return's transaction:

1. **`capture_charges(booking, lines, staff_user, idempotency_key=f"return-{booking.pk}")`**
   with one `ChargeLine(description, amount)` per settlement line, tax
   included as its own line (Pay.Ledger: one Charge entry each). It captures
   the whole rental and deposit authorisation (the rental of an extension
   too); for a cash booking it writes the Charge entries only. The key is
   stable per booking, so a repeated Settle can never charge twice.
2. **`issue_debit_note(booking.invoice, settlement.total, reason, issued_by=staff_user)`**
   when the booking has an invoice and the total is above zero: the charges
   go on the invoice as a debit note DN-YYYY-NNNNNN referencing it, never an
   edit (Pay.Invoice). `amount` is the total including tax; R1 splits the
   tax at the invoice's own rate. The reason lists every line.
3. **`refund_deposit(booking, deposit - total, staff_user)`** when a balance
   is left (BR-14); its default key makes it once per booking. A cash
   deposit is paid back at once by the staff member settling.
4. **`record_due(customer, total - deposit, reason, initiated_by=staff_user)`**
   when the charges exceed the deposit (Pay.Dues); called once, inside the
   same transaction (a replay returns before reaching it).

No `apps/payments` code was changed. `issue_debit_note()`'s signature and
limits fit as they are. Bookings seeded without an invoice (the demos) get
no debit note, as in R2's extension.

## 8. Changes outside the module's own files, for review

| File | Change | Why |
|---|---|---|
| `B:bookings/states.py` | **`complete_booking(booking, by, *, request=None)`** next to `activate_booking()`: Active → Completed through `transition()`, saving `returned_at` and `distance_travelled` set by the caller; no bookings migration | Return.Complete (Rohan to review) |
| `B:maintenance/services.py` | `conflicting_bookings()` overlaps `blocked_period` | BR-1 buffer in Maint.Conflict (Nidhi's app) |
| `backend/config/settings/business_rules.py` | `ODOMETER_PLAUSIBILITY_KM_PER_DAY = 1000` (proposed) | Return.Odometer (N2-P7) |
| `backend/config/settings/base.py` | `ENUM_NAME_OVERRIDES["SeverityEnum"]` | the return form's `flag_severity` reuses the maintenance severity choices; without it `spectacular --fail-on-warn` fails |
| `B:core/management/commands/seed_demo.py` | calls `seed_demo_return_data()` and `delete_demo_return_data()` | the demo (additive) |
| `B:core/tests/test_seed_demo.py` | expected counts +2 cars, +1 customer, licence and category; 51 audited creates and deletes | the demo (additive) |

## 9. Proposed readings (the SRS is silent; awaiting team approval)

| # | Item | Where | Proposal |
|---|---|---|---|
| N2-P1 | Late-return hours | `settlement.late_return()` | After BR-10's grace, hours are counted as BR-6 counts them (PR2): whole hours, a part-hour billed only past the 15-minute grace (1 h 10 min late = 1 hour) |
| N2-P2 | Free kilometres | `calculate_settlement()` | `free_km_allowance` per rental day, days counted as for add-ons (PR8; under 24 h is one day), on the booking's current period |
| N2-P3 | Fuel shortfall quantity | `settlement.fuel_shortfall()` | The drop in percent of `Vehicle.fuel_capacity` (litres, kg or kWh), at the `FuelPrice` in force at the return time; refused (409) if the capacity or the price is missing |
| N2-P4 | Tax on return charges | `calculate_settlement()` | `TAX_RATE_PERCENT` (D14) on the charges, as its own line, as BR-6 adds taxes to usage-based charges |
| N2-P5 | Accessory not returned | `services._accessories()` | Charged at the cost the staff member enters (the SRS has no price list); only accessories issued at handover can be missing |
| N2-P6 | Return.Flag job | `services._flag_vehicle()` | A Corrective job; "unfit for use" (asked for, default yes) decides Under Maintenance or Available |
| N2-P7 | Plausibility limit and supervisor | `plausibility_limit()`, `_odometer_override()` | 1,000 km per started day out; the supervisor is a Branch Manager of the branch or an Administrator, signing in on the branch device. **This amends D16** ("no plausibility limit"), as asked for N2; `docs/decisions.md` is not edited here |
| N2-P8 | The actual return time | `_check_return_time()` | Entered by the staff member (defaults to now), not in the future and not before the handover |
| N2-P9 | Customer acknowledgement | `ReturnForm.tsx`, `ConditionReport.signature` | The customer signs the return report after seeing the settlement; that signature is Appendix A's "customer signature" for the return |
| N2-P10 | Settle idempotency | `return_vehicle()` | One return per booking: a repeated Settle returns the first result |

## 10. Demo data

`B:rentals/seed_return.py` (called by `seed_demo`): return@vrms.test
(password Demo@1234) with a verified car licence, and at Andheri two
hatchbacks with a 37 L tank, each On Rent in an Active one-day booking paid
by card and recorded as handed over by staff@vrms.test:

- MH02DT6001, due back two hours after `seed_demo` runs: return it on time.
- MH02DT6002, due back three hours before `seed_demo` ran, with a child seat
  issued. Return it with the odometer 400 km above the handover reading and
  the fuel at 75%: the settlement shows the late return (BR-10), the excess
  kilometres (BR-11), the fuel shortfall (BR-12) and the tax; untick the
  child seat to charge for it too.

Their handover reports are unsigned and have no photographs (a signed report
can never be deleted, so `--reset` could otherwise never remove them; team
decision, 18 Oct 2026). To see the photos side by side, hand over the
handover demo booking (handover@vrms.test, now collectable five minutes
before `seed_demo` runs) and return it. `--reset` refuses, like the other
demos, once a return has been recorded.

Tests: `test_two_active_rentals_are_ready_to_return_one_on_time_and_one_late`,
`test_the_late_rental_shows_the_br10_br11_and_br12_lines`,
`test_seeding_the_return_demo_again_adds_nothing` [seed]; counts in
`core/tests/test_seed_demo.py`.

## 11. Not built here

- Maint.Auto.Km (a Preventive job when the odometer reaches the BR-15
  interval "evaluated at every return"): built in N3, one call after
  `_record_odometer()` to `maintenance.services.raise_preventive_job_if_due()`
  (`docs/traceability-admin.md`).
- Notify overdue alerts (3.8.2 "A vehicle becomes overdue for return"):
  no Celery task was added to Beat in N2.
- An invoice for a booking that has none (the seeded demos): Pay.Invoice is
  issued at Book.Done; the return only adds a debit note.
