# Traceability: Handover Vehicle (Module N1)

Maps every requirement of SRS 3.3 that covers the handover (Handover.Refuse,
Handover.Checklist, Handover.Sign, Handover.Activate), Exp 2 use case 7 with
its include "Verify Licence Eligibility", the Exp 3 methods
`BranchStaff.handover_vehicle()` and `ConditionReport.capture_report()`, the
Exp 5 handover fork/join, DFD process 5 and the business rules involved to
the code and the tests. SRS: `docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf`
(3.3, SA-2, SA-3, Appendix B). Proposed readings P18 to P24 are in
`docs/model-mapping.md`, section 5.

Exp 4 has no Handover sequence diagram (its three diagrams are Book Vehicle,
Return Vehicle and Close Maintenance Job), so section 2 follows the Exp 5
activity diagram instead.

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`. Test names are pytest functions or Vitest `it` titles.

## 1. Requirements

| Requirement | Implemented in | Tests |
|---|---|---|
| UC 7 step 1: retrieve the booking by reference, pickup code or customer mobile | `B:rentals/services.py` `branch_collections()`; API `GET /api/v1/rentals/branch-bookings/?when=today\|upcoming&q=` (`BranchBookingListView`, `IsBranchStaff \| IsBranchManager`, scoped with `scope_queryset()`); UI `F:features/handover/CollectionsPage.tsx` (`/app/handover`, `/app/branch-bookings`) | `test_today_and_upcoming_are_split_by_the_pickup_date`, `test_find_by_reference_pickup_code_or_mobile`, `test_a_search_never_finds_a_booking_that_is_not_confirmed` [test_services]; `test_branch_bookings_lists_only_the_callers_branch_and_hides_the_pickup_code`, `test_a_branch_manager_sees_their_branch_too`, `test_find_by_pickup_code_stays_inside_the_branch` [test_api]; Vitest "shows today’s and upcoming collections at the branch, each opening its handover", "finds a booking by its pickup code, and clears the search", "says when no booking matches" |
| UC 7 step 2, include Verify Licence Eligibility; BR-2 (valid for the whole rental), BR-3 (endorsed category) | `services._licence_refusal()` → `B:bookings/eligibility.py` `licence_is_valid()` (Exp 3 `Licence.is_valid()`), staff-facing messages in `LICENCE_REFUSALS` | `test_an_expired_licence_is_refused`, `test_a_licence_expiring_during_the_rental_is_refused_br2`, `test_a_licence_without_the_category_is_refused_br3`, `test_an_unverified_licence_is_refused` |
| Handover.Refuse: insurance, pollution and fitness certificate (and road tax, SA-3) valid for the whole period; the document at fault is named | `services._document_refusals()`, `HANDOVER_REQUIRED_DOCUMENTS` in `backend/config/settings/business_rules.py` | `test_each_statutory_document_must_cover_the_whole_rental_sa3` (4 cases), `test_a_missing_document_is_named`, `test_a_document_not_yet_valid_on_the_pickup_date_is_refused` |
| Handover.Refuse, SA-2: a vehicle flagged Unsafe | `services._vehicle_refusal()` (also any status other than Available, which Appendix B cannot move to On Rent) | `test_a_vehicle_flagged_unsafe_is_refused_sa2`, `test_a_vehicle_under_maintenance_is_refused`, `test_detail_states_which_condition_failed` |
| A cash booking not yet paid (BR-9; Appendix B: Confirmed means paid) | `services._is_paid()` (P24: a Succeeded deposit payment, until R1's service exists) | `test_an_unpaid_booking_is_refused_until_cash_is_recorded`, `test_a_refused_handover_is_409_with_every_failed_condition` |
| UC 7 precondition: Confirmed, and the pickup time has arrived (P20) | `services.handover_refusals()` codes `booking_not_confirmed`, `already_handed_over`, `pickup_not_arrived` | `test_only_a_confirmed_booking_can_be_handed_over` (4), `test_an_active_booking_is_already_handed_over`, `test_before_the_pickup_time_the_handover_waits`, `test_a_second_handover_is_refused` |
| Handover.Refuse: "state which condition was not met" | `HandoverDetailSerializer.refusals` / `can_hand_over`; 409 `{code: "handover_refused", refusals}`; UI `Refusals` in `F:features/handover/HandoverPage.tsx` | `test_every_failed_condition_is_listed`, `test_detail_states_which_condition_failed`; Vitest "states every condition that was not met and offers no checklist", "shows the server’s refusal when a condition fails while the form is open" |
| Handover.Checklist: odometer, fuel or charge level, accessories issued (BR-7 helmet, booked add-ons), at least four photos covering all sides (P18), damage marked on a diagram (P21) | `services.capture_report()`, `expected_accessories()`; `B:rentals/serializers.py` `HandoverSerializer` (photo_front/rear/left/right required, validated with `validate_image_upload`, D3); UI `F:features/handover/HandoverForm.tsx`, `VehicleDiagram.tsx` | `test_expected_accessories_are_the_add_ons`, `test_a_two_wheeler_comes_with_br7s_free_helmet`, `test_an_incomplete_checklist_is_400` (9 cases), `test_a_corrupt_photo_is_refused`, `test_extra_photos_are_kept`; Vitest "asks for every side and the signature before sending anything", "refuses a photo that is not a JPG or PNG" |
| Handover.Sign: the report and the rental agreement presented for a digital signature | `HandoverDetailSerializer.terms` (`pricing.services.quote_terms()`); UI `TermsList` and `F:features/handover/SignaturePad.tsx` (canvas, PNG) | `test_detail_shows_the_checklist_and_no_refusal_when_ready`; Vitest "records the checklist, the customer signs, and the booking becomes Active" |
| Handover.Sign: stored as a document that cannot be altered | `B:rentals/models.py` `ConditionReport.save()/delete()/refresh_from_db()`, `ConditionPhoto` guards; migration `B:rentals/migrations/0002_signed_report_append_only.py` (triggers on reports and photos); admin view-only and no add | `test_raw_update_of_a_signed_report_is_refused`, `test_raw_delete_of_a_signed_report_is_refused`, `test_raw_unsigning_is_refused`, `test_raw_change_of_a_signed_reports_photo_is_refused` (2), `test_raw_insert_of_a_photo_on_a_signed_report_is_refused`, `test_an_unsigned_report_can_still_be_filled_in_and_signed`, `test_photos_of_an_unsigned_report_can_change` [test_append_only]; `TestSignedReportIsFinal` [test_models]; `test_signed_condition_report_is_view_only` [core/test_admin] |
| Handover.Sign: e-mail a copy to the customer | `queue_email(..., "handover_report")` → Celery `deliver_notification` after commit; template in `B:rentals/notification_templates.py` | `test_records_signs_and_activates_atomically` (Notification Sent, outbox), `test_the_handover_e_mail_renders`, `test_a_refusal_changes_nothing` (no e-mail) |
| Handover.Activate: booking Active, vehicle On Rent, actual handover time, one transaction, audited | `services.handover_vehicle()` under the booking row lock: `B:bookings/states.py` `activate_booking()` (added for N1, Rohan to review), `B:fleet/services/status.py` `update_status(..., On Rent)`, `record_audit("Condition Report Signed")` | `test_records_signs_and_activates_atomically`, `test_a_failure_after_the_report_rolls_everything_back`, `test_confirmed_becomes_active_with_the_handover_time`, `test_only_from_confirmed` (4), `test_complete_hands_the_vehicle_over_and_returns_the_signed_report` |
| SI-3: stored photos and signature only through signed, expiring links | `ConditionReportSerializer` (`signed_file_url()`) | `test_complete_hands_the_vehicle_over_and_returns_the_signed_report` (link works without a session) |
| SE-4 / SE-5: a permission class on every endpoint; own branch only | `BRANCH_TEAM` and `IsBranchStaff` in `B:rentals/views.py`; `scoped_bookings()` with `scope_queryset(branch_lookup="pickup_branch_id")` | `test_endpoint_permission` (3 endpoints × 6 roles), `test_every_rentals_route_is_in_the_matrix` [test_permissions]; `test_a_booking_of_another_branch_is_not_found`, `test_staff_of_another_branch_cannot_hand_over`; Vitest "a Branch Manager sees the booking read only"; guard tests in `F:app/guards.test.tsx` |
| Book.Done.Store: the pickup code is the customer's to present | `BranchBookingSerializer` has no pickup code | `test_branch_bookings_lists_only_the_callers_branch_and_hides_the_pickup_code` |

## 2. Exp 5 activity diagram, Phase 3 (handover), node by node

| # | Node | Implemented in | Tests |
|---|---|---|---|
| 1 | Re-verify licence and statutory documents | `services.handover_refusals()` | section 1, Handover.Refuse rows |
| 2 | Decision "Handover permitted?" [No] → Refuse handover, state failed condition | `HandoverRefusedError`; 409; `Refusals` | `test_a_refusal_changes_nothing`, `test_a_refused_handover_is_409_with_every_failed_condition` |
| 3 | Fork: Record odometer, fuel, accessories, 4+ photos ∥ Sign condition report on branch device | `HandoverForm.tsx` (checklist and `SignaturePad` on one screen) | Vitest "records the checklist, the customer signs, and the booking becomes Active" |
| 4 | Join → Store signed report, set Active / On Rent | one POST `…/handovers/{id}/complete/` → `services.handover_vehicle()` in one transaction | `test_records_signs_and_activates_atomically`, `test_a_failure_after_the_report_rolls_everything_back` |

## 3. Exp 3 class diagram

| Class / method | Implemented in | Tests |
|---|---|---|
| `BranchStaff.handover_vehicle()` | `services.handover_vehicle()` (the staff member's branch must be the pickup branch) | `TestHandoverVehicle` |
| `ConditionReport.capture_report()` | `services.capture_report()` | `test_records_signs_and_activates_atomically` |
| `ConditionReport` (report_type, odometer_reading, fuel_level, signature) | `B:rentals/models.py` | `test_models.py` |
| `Licence.is_valid()` | `bookings/eligibility.licence_is_valid()` (reused) | licence rows above |
| `Vehicle.update_status()` | `fleet/services/status.update_status()` (Available → On Rent, Appendix B) | `test_records_signs_and_activates_atomically`; `fleet/tests/test_status_service.py` |
| BranchStaff 1 — 0..* ConditionReport | `ConditionReport.recorded_by` | `test_records_signs_and_activates_atomically` |

## 4. DFD process 5 (Handle Vehicle Handover)

| Flow | Implemented in |
|---|---|
| Branch Staff → 5: checklist | `POST /api/v1/rentals/handovers/{id}/complete/` |
| 5 ↔ D1 User and License | `licence_is_valid()` reads the licence |
| 5 ↔ D2 Vehicle and Fleet | documents and status read; `update_status(On Rent)` |
| 5 ↔ D4 Booking | `activate_booking()` |
| 5 → D6 Condition Report | `capture_report()` |
| 5 → D8 Audit Log | "Condition Report Signed", "Booking Status Changed", "Vehicle Status Changed" |
| 5 → 6 active rental | the Active booking and its handover report feed the return (Module N2) |
| 5 → Notification Service | `handover_report` e-mail through Celery |

## 5. Business rules

| Rule | Where | Tests |
|---|---|---|
| BR-2 licence valid for the whole rental | `licence_is_valid()` | `test_a_licence_expiring_during_the_rental_is_refused_br2` |
| BR-3 endorsed categories | `licence_is_valid()` | `test_a_licence_without_the_category_is_refused_br3` |
| BR-7 one free helmet per rider | `expected_accessories()` (`FREE_HELMETS_PER_RIDER`) | `test_a_two_wheeler_comes_with_br7s_free_helmet` |
| BR-9 cash recorded before the handover | `_is_paid()` | `test_an_unpaid_booking_is_refused_until_cash_is_recorded` |

## 6. Demo data

`B:rentals/seed.py` (called by `seed_demo`): car MH02DH3001 at Andheri with all
four SA-3 documents; handover@vrms.test (password Demo@1234), a customer
with a verified car licence; and that customer's paid, Confirmed one-week
booking collected from five minutes before `seed_demo` runs (shown in IST),
pickup code 246810, with a child seat to issue. customer@vrms.test keeps an
empty history for the Book Vehicle demo.

The pickup used to be fixed at 07:00 IST. Handover is refused before the
pickup time, and R2's no-show task (Celery Beat, every minute) marks a
booking not collected two hours after its pickup No-show, so with Beat
running the demo booking was a No-show by 09:00. Now it can be handed over
as soon as the seed has run, for the next 1 hour 55 minutes; after that,
running `seed_demo` again adds a fresh booking (a No-show no longer holds the
car). Tests: `test_one_paid_confirmed_booking_today_at_andheri_with_nothing_blocking_it`,
`test_beat_no_longer_spoils_the_handover_demo`,
`test_after_a_no_show_the_next_seed_adds_a_fresh_booking`,
`test_it_appears_in_todays_collections_and_by_its_pickup_code`,
`test_seeding_again_the_same_day_adds_nothing`,
`test_a_later_day_gets_a_booking_once_the_last_one_is_over`,
`test_the_maintenance_demo_jobs_are_untouched`, `test_reset_removes_and_reloads_it`
[rentals/test_seed]; counts in `core/tests/test_seed_demo.py`.
