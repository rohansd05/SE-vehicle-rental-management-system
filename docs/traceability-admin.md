# Traceability: Administration and maintenance completion (Module N3)

Maps SRS 3.7 (Fleet.Add, Fleet.Status, Fleet.Retire, Fleet.Tariff,
Fleet.Tariff.History, Fleet.Users, Fleet.Audit), BR-4 (blacklist), BR-13,
BR-15, BR-16, SA-2 and SA-3, the 3.6 requirements N3 completes
(Maint.Auto.Km, Maint.Auto.Time, Maint.Record's invoice, Maint.History,
Maint.Status), Exp 2 use cases 9 (extension 2a), 10 (extension 1a), 11
and 12, the "Send Maintenance Alert" and document expiry alerts, Exp 3
`Administrator.manage_fleet()` and `define_tariff()`, Exp 4 sequence
diagram 3 where N3 changes it, and the Exp 5 and Exp 6 nodes to the code
and the tests. SRS: `docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf`.
Proposed readings N3-P1 to N3-P10 are in `docs/decisions.md` ("Module N3")
and `docs/model-mapping.md` (P35 to P42).

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`. Test names are pytest functions or Vitest `it`
titles. `[fleet]` = `B:fleet/tests/test_admin_api.py`, `[pricing]` =
`B:pricing/tests/test_admin_api.py`, `[users]` =
`B:accounts/tests/test_admin_api.py`, `[audit]` =
`B:core/tests/test_audit_viewer.py`, `[maint]` =
`B:maintenance/tests/test_n3.py`, `[rentals]` = `B:rentals/tests/test_n3.py`,
`[admin]` = `B:core/tests/test_admin.py`.

## 1. SRS 3.7 and the business rules

| Requirement | Implemented in | Tests |
|---|---|---|
| **Fleet.Add**: registration, type, category, brand, model, year, colour, fuel type, transmission, seating, chassis, home branch, odometer, availability date, at least four photographs, each statutory document's expiry date | `B:fleet/services/admin.py` `create_vehicle()` (Car or TwoWheeler by the category's type; `fuel_capacity` required, BR-12/N2-P3); `B:fleet/admin_serializers.py` `VehicleCreateSerializer` (multipart, `photos` ×4+, `documents` JSON); `POST /api/v1/fleet/admin/vehicles/`; UI `F:features/admin/VehicleFormPage.tsx` (`/app/fleet/new`) | `test_an_administrator_adds_a_car_with_photos_and_documents`, `test_a_two_wheeler_needs_its_engine_capacity`, `test_a_car_needs_its_transmission_and_seats`, `test_fewer_than_four_photos_are_refused`, `test_every_statutory_document_needs_an_expiry_date`, `test_the_tank_or_battery_capacity_is_required`, `test_a_file_that_is_not_an_image_is_refused` [fleet]; Vitest "adds a vehicle with its photos and the expiry of each statutory document" |
| UC 11 extension 1a: an existing registration or chassis number is rejected | `fleet_admin._check_unique()` (case and spaces ignored) on create and edit | `test_an_existing_registration_or_chassis_number_is_rejected_uc11_1a`, `test_an_edit_cannot_take_another_vehicles_registration` [fleet]; Vitest "shows the server’s refusal of a registration already on record next to the field" |
| UC 11 step 1 "edits": master data; the type never changes; the odometer never decreases (Appendix A) | `fleet_admin.update_vehicle()`; `PATCH …/admin/vehicles/{id}/` (`VehicleUpdateSerializer`, no status field); UI `F:features/admin/VehiclePage.tsx` sends only changed fields | `test_an_edit_is_audited_with_the_previous_and_new_values`, `test_the_odometer_never_goes_down_and_the_type_never_changes` [fleet]; Vitest "sends only the fields that changed" |
| **Fleet.Status**: every vehicle's current status on the fleet display | `AdminVehicleListView` (`GET …/admin/vehicles/?status=&q=`), `AdminVehicleSerializer`; UI `F:features/admin/FleetPage.tsx` (`/app/fleet`) with `VehicleStatusBadge` | `test_the_fleet_lists_every_vehicle_with_status_and_document_alerts` [fleet]; Vitest "lists every vehicle with its status and document alerts, and filters by status" |
| **Fleet.Retire**: Administrator only; refused while a booking is not over; history kept | `fleet_admin.retire_vehicle()` → `B:fleet/services/status.py` `update_status(…, Retired)` (the state machine's guards, M4); 409 with the reason; UI "Retire vehicle" (`ReasonDialog`) | `test_a_vehicle_with_a_future_booking_is_not_retired`, `test_retiring_goes_through_the_state_machine_and_is_audited` [fleet]; Vitest "states why a vehicle with a future booking cannot be retired" |
| Fleet.Add / SA-3: statutory documents with expiry dates; a renewal is a new row | `fleet_admin.add_document()`, `remove_document()`; `AdminDocumentSerializer` (`state`, `current`); UI "Statutory documents" | `test_the_detail_marks_the_current_document_of_each_type`, `test_a_renewal_is_a_new_document_and_a_mistake_can_be_removed` [fleet]; Vitest "records a document renewal and refuses to drop below four photographs" |
| Fleet.Add: at least four photographs stay | `fleet_admin.add_photo()`, `remove_photo()` (`VEHICLE_PHOTOS_MINIMUM`) | `test_photos_are_added_and_removed_but_four_always_stay` [fleet]; Vitest same as above |
| UC 11 "branches"; Book.Deliver.Location serviceable areas | `fleet_admin.create_branch()`, `update_branch()`, `add_area()`, `remove_area()`; `…/admin/branches/…`; UI `F:features/admin/BranchesPage.tsx` (`/app/fleet/branches`) | `test_branches_are_added_edited_and_their_areas_managed` [fleet]; Vitest "adds a serviceable area to a branch" |
| **Fleet.Tariff**, **BR-13**: only an Administrator defines a tariff, from its effective date | `B:pricing/admin_services.py` `define_tariff()` (now or a future date; never past; deposit from BR-3, N3-P7); `POST /api/v1/pricing/admin/tariffs/`; UI `F:features/admin/TariffsPage.tsx` (`/app/tariffs`) | `test_a_new_tariff_takes_effect_and_the_old_one_stays`, `test_a_past_effective_date_or_a_second_tariff_at_the_same_moment_is_refused`, `test_the_security_deposit_is_br3s_never_an_input`, `test_negative_rates_are_refused`, `test_a_branch_manager_cannot_define_a_tariff_even_in_the_service` [pricing]; Vitest "defines a tariff that starts now when no date is given", "shows the server’s refusal of a past effective date next to the field" |
| **Fleet.Tariff.History**, UC 11 extension 2a: the previous tariff stays; confirmed bookings and invoices are never repriced | Tariffs are new rows (`pricing/models.py`, unchanged); `admin_services.tariff_state()` (In force / Scheduled / Superseded); `booking_count`; `withdraw_tariff()` only before it takes effect. No pricing or repricing code was changed: new bookings and R2's modifications pick the tariff in force as before | `test_a_confirmed_booking_keeps_the_tariff_it_was_priced_at`, `test_a_future_tariff_is_scheduled_and_can_be_withdrawn_before_it_starts` [pricing]; Vitest "shows the history with which tariff is in force and how many bookings keep each" |
| Book.Addons (BR-7) and D17 discount codes managed by the Administrator | `save_add_on()`, `save_discount_code()` (code unique whatever the case, never changed; value, window and limit checked); `…/admin/add-ons/`, `…/admin/discount-codes/` | `test_add_ons_are_created_and_changed_without_repricing_bookings`, `test_a_discount_code_is_created_once_whatever_the_case`, `test_an_invalid_discount_is_refused`, `test_a_discount_code_changes_but_its_text_and_use_count_do_not` [pricing]; Vitest "stops offering an add-on and switches a discount code off" |
| **Fleet.Users**: create, edit, disable and re-enable Branch Staff, Technician and Branch Manager accounts, each assigned to a branch | `B:accounts/admin_services.py` `create_staff_account()` (profile per role; Django password validators), `update_staff_account()` (role never changes), `set_account_active()`; `…/api/v1/admin/users/…`; UI `F:features/admin/UsersPage.tsx`, `StaffPages.tsx` (`/app/users`, `/app/users/new`, `/app/users/{id}`) | `test_an_administrator_creates_each_staff_account_with_its_profile` (3), `test_the_new_account_signs_in`, `test_an_incomplete_account_is_refused` (7), `test_an_e_mail_already_used_is_refused_whatever_the_case`, `test_an_account_is_edited_and_moved_to_another_branch`, `test_only_staff_accounts_are_managed_here`, `test_the_staff_list_filters_by_role_status_and_text` [users]; Vitest "lists the accounts with their role, branch and state", "creates a technician with a workshop instead of a branch" |
| Fleet.Users: disabling ends every session at once and refuses sign-in; past actions untouched | `set_account_active()` → `blacklist_all_refresh_tokens()`; an inactive user's access token is refused (SimpleJWT); the user row is never deleted | `test_disabling_ends_every_session_at_once_and_re_enabling_restores_sign_in` [users]; Vitest "disables an account with a reason, and authorises a technician (BR-16)" |
| Accounts made on /app/users work in the other modules, own branch only: handover (N1), return (N2), cash desk (R1), branch bookings | the same profiles the other modules read (`BranchStaff.branch`, `BranchManager.branch`), so `scope_queryset()` scopes them | `test_new_branch_staff_work_on_their_own_branch_only` [users] |
| A Branch Manager made there approves N2's odometer override | `BranchManager` with its Administrator row; `rentals.services._odometer_override()` unchanged | `test_a_new_branch_manager_approves_the_odometer_override`, `test_a_new_branch_manager_of_another_branch_cannot_approve` [users] |
| **BR-4**, UC 12 step 2: blacklist a customer with the reason | `blacklist_customer()`, `lift_blacklist()`; the reason in the "Customer Blacklisted" audit entry (N3-P2), read back by `customers_with_blacklist()`; new bookings refused by `bookings/eligibility.py` (unchanged); UI `F:features/admin/CustomerPage.tsx` (`/app/users/customers/{id}`) | `test_blacklisting_records_the_reason_and_lists_confirmed_and_active_bookings`, `test_a_blacklisted_customer_cannot_book`, `test_lifting_the_blacklist_is_audited_with_its_reason`, `test_customers_are_found_by_name_e_mail_or_mobile` [users]; Vitest "blacklists with a reason, then lists the Confirmed booking to decide on and the rental as return pending" |
| UC 12 extension 2a: list the Confirmed bookings so the actor decides on each; Active ones "return pending", never cancelled | `open_bookings()`; `OpenBookingSerializer.return_pending`; `CustomerBookingCancelView` GET quote and POST cancel → `cancel_for_blacklist()` → **R2's `bookings.services.cancel_booking()`** (and `cancellation_quote()`), never a copy; SE-9 password (`payments.reauth.require_password`); the Administrator's decision audited "Booking Cancelled For Blacklist" besides R2's entries | `test_a_confirmed_booking_is_cancelled_through_r2_and_audited_twice`, `test_a_changed_refund_must_be_seen_again`, `test_an_active_booking_is_never_cancelled_here`, `test_only_a_blacklisted_customers_booking_is_cancelled_here` [users]; Vitest "cancels a Confirmed booking through R2 with the refund shown and the password" |
| **Fleet.Audit**, SE-10: the log is readable, filterable and never editable | `B:core/services.py` `audit_entries_for()`, `filter_audit_entries()` (actor name/e-mail or "system", action, entity type and id, local dates), `audit_filter_options()` (every action and entity type present, so every module's events, including later ones, can be chosen); `GET /api/v1/audit/`, `GET /api/v1/audit/filters/` (no write method); UI `F:features/admin/AuditPage.tsx` (`/app/audit`, filters in the URL) | `test_the_log_cannot_be_written_through_the_api` (4), `test_an_administrator_reads_every_entry_newest_first_with_both_values`, `test_filters_by_actor_action_entity_and_date`, `test_a_reversed_date_range_is_refused`, `test_the_filter_lists_hold_every_action_and_entity_type` [audit]; Vitest "shows who did what, when, with the previous and new values; the system too", "filters by actor, action, entity and date", "opens pre-filtered on one booking from the blacklist screen" |
| Fleet.Audit for a Branch Manager: their own branch (N3-P1) | `core.services._branch_entries()` | `test_a_branch_manager_sees_their_branchs_records_only` (10 entity types), `test_a_branch_manager_sees_what_their_branchs_people_did` [audit]; Vitest "is open to a Branch Manager, for their own branch", "is refused to Branch Staff" |
| The viewer shows every module's events: R1 (cash recorded, refund approved/rejected = "Refund Approved"/"Refund Status Changed", due paid), R2 (modify, cancel, extend, no-show = "Booking Modified", "Booking Status Changed", "Booking Extended"), N1 handover, N2 return, settlement, Return.Flag and the odometer override | the viewer is generic over `AuditLog`; the scoping covers each entity type those modules record against | `test_a_return_with_override_and_flag_is_in_both_audit_views` (N2 and R1's capture/ledger/due, real services), `test_a_cash_payment_and_a_handover_are_in_the_branch_managers_view` (R1 cash, N1 handover), `test_a_confirmed_booking_is_cancelled_through_r2_and_audited_twice` (R2 cancel) |
| **BR-15**, **Maint.Auto.Km** (evaluated at every return) | `B:maintenance/services.py` `raise_preventive_job_if_due()`, called by one line after `_record_odometer()` in `B:rentals/services.py` `return_vehicle()` | `test_a_return_reaching_the_service_distance_raises_the_preventive_job_at_once`, `test_a_return_short_of_the_interval_raises_nothing` [rentals] |
| **BR-15**, **Maint.Auto.Time** (evaluated daily) | `raise_due_preventive_jobs()` → the same function; `B:maintenance/tasks.py` `raise_preventive_jobs`; PeriodicTask in `B:maintenance/migrations/0004_schedule_daily_alerts.py` | `test_the_daily_sweep_raises_by_time_and_distance`, `test_both_daily_tasks_are_scheduled_by_migration_0004` [maint] |
| BR-15 thresholds: 5,000 km / 6 months (car), 3,000 km / 4 months (two-wheeler), whichever first | `service_due()` on `next_service_due()` (Module 2), constants in `business_rules.py` | `test_a_car_is_due_at_5000_km_or_6_months_whichever_first`, `test_a_two_wheeler_is_due_at_3000_km_or_4_months`, `test_without_a_service_on_record_nothing_is_due`, `test_due_text_names_both_points` [maint] |
| UC 9 extension 2a: the automatic job is pre-filled as Preventive with the due distance or date | `MaintenanceJob.due_odometer`, `due_date` (migration 0003); `reported_by` empty (the system); UI "Service due (BR-15)" and "Raised by the system (BR-15)" on `F:features/maintenance/JobDetailPage.tsx` | `test_a_due_vehicle_gets_a_preventive_job_from_the_system_with_the_alert`, `test_an_open_preventive_job_is_not_raised_twice`, `test_a_corrective_job_does_not_stop_the_preventive_one`, `test_nothing_is_raised_for_a_vehicle_not_due_or_retired`, `test_job_and_vehicle_fields_for_the_screens` [maint]; Vitest "shows a Preventive job the system raised with its BR-15 due point and the overdue warning" |
| **Send Maintenance Alert** (SRS 3.6.2, DFD 7.3): service-due alert | `_notify_service_due()` → `queue_email("maintenance_service_due")` (Celery after commit) to every active technician and Administrator | `test_a_due_vehicle_gets_a_preventive_job_from_the_system_with_the_alert` (outbox) [maint] |
| Context diagram "document expiry alert" (SA-3) | `expiring_documents()`, `alert_expiring_documents()` → `queue_email("vehicle_documents_expiring")`; `tasks.alert_expiring_documents`, daily (migration 0004); `DOCUMENT_EXPIRY_ALERT_WINDOW` (N3-P4) | `test_the_document_alert_lists_the_latest_expired_or_expiring_documents`, `test_no_alert_when_every_document_is_valid` [maint] |
| **SA-2**: no handover of a vehicle "overdue for a mandatory safety service" | `rentals.services._service_refusal()` (code `service_overdue`, its own reason) in `handover_refusals()`; overdue warning `ServiceOverdueNote` on the job and history pages; `service_overdue` in `MaintenanceVehicleSerializer` | `test_a_vehicle_past_its_service_distance_is_refused_with_its_own_reason`, `test_a_vehicle_past_its_service_date_is_refused`, `test_a_vehicle_serviced_recently_or_never_is_handed_over`, `test_the_overdue_service_is_shown_to_the_staff_and_stops_the_handover` [rentals] |
| **BR-16**, SA-3, SE-6: an Administrator marks a technician "authorised to clear Unsafe" | `maintenance.UnsafeClearanceAuthorisation` (migration 0003); `authorise_technician()`, `revoke_authorisation()` (audited); `PUT/DELETE /api/v1/maintenance/technicians/{id}/authorisation/`; UI "Authorise to clear Unsafe" on the staff page | `test_an_administrator_authorises_and_revokes_a_technician_with_audit`, `test_only_an_administrator_authorises_and_never_a_disabled_technician`, `test_authorisation_endpoint_grants_and_revokes` [maint]; `test_a_new_technician_is_authorised_on_the_users_screen` [users]; Vitest "disables an account with a reason, and authorises a technician (BR-16)" |
| BR-16, UC 10 extension 1a: that technician clears the flag while closing the job; their identity recorded | `fleet/services/status.py` `may_clear_unsafe()` in `check_transition()` (the state machine); `complete_job(…, clear_unsafe=True)` → `_clear_and_finish()`; `can_clear_unsafe` in the job API; UI tick "Clear the Unsafe flag as I close the job" | `test_an_authorised_technician_clears_unsafe_while_closing_and_is_recorded`, `test_an_unauthorised_technician_cannot_clear_unsafe`, `test_an_authorised_technician_may_still_ask_an_administrator`, `test_a_revoked_technician_is_refused_by_the_state_machine`, `test_an_administrator_clears_while_completing_directly`, `test_clear_unsafe_on_a_vehicle_not_flagged_simply_completes`, `test_complete_endpoint_takes_clear_unsafe`, `test_can_clear_unsafe_is_false_for_an_unauthorised_technician` [maint]; `test_the_unsafe_refusal_names_the_authorised_technician_too` [rentals]; Vitest "offers the clearance only to an authorised technician, and sends it", "an unauthorised technician sees no such option and asks an Administrator" |
| **Maint.Record**: "permit the workshop invoice to be attached" (UC 9 step 3) | `attach_invoice()`; `WorkshopInvoiceSerializer` (PDF header or Pillow image check, 5 MB); `PUT …/jobs/{id}/invoice/`; `workshop_invoice_url` (signed, SI-3); UI "Workshop invoice" in `RecordWorkForm.tsx`, link in "Work recorded" | `test_the_assigned_technician_attaches_a_workshop_invoice`, `test_an_invalid_invoice_is_refused` (3), `test_an_invoice_only_while_in_progress_and_by_the_assignee` [maint]; Vitest "attaches the workshop invoice and links to it" |
| Maint.Record odometer field: typing must not append to a prefilled value | `RecordWorkForm.tsx` `defaults()`: empty until recorded; the hint gives the last reading | Vitest "starts the odometer empty, so typing never appends to the last reading" |
| **Maint.History**: every job with date, type, odometer, work, parts, cost and downtime | `GET …/vehicles/{id}/history/` (Module 2); UI `F:features/maintenance/VehicleHistoryPage.tsx` (`/app/maintenance/vehicles/{id}/history`, `/app/jobs/vehicles/{id}/history`), linked from the job page and the fleet vehicle page | Vitest "lists every job on the vehicle with its date, type, odometer, work, parts, cost and downtime" |
| Maint.Status / Appendix B Cancelled: the cancel reason and canceller shown | `MaintenanceJob.cancelled_by`, `cancelled_at`, `cancel_reason` set by `cancel_job()` | `test_a_cancelled_job_records_who_cancelled_it_when_and_why` [maint]; Vitest "shows who cancelled a job, when and why" |
| Status fields never edited in the Django admin (Booking, Vehicle, Car, TwoWheeler, MaintenanceJob) | `B:core/admin.py` `AuditedModelAdmin.get_readonly_fields()` with `STATE_MACHINE_MODELS` (no edit of `bookings/admin.py`) | `test_a_state_machine_status_is_read_only_in_admin` (5), `test_other_statuses_stay_editable` [admin] |
| Append-only rows view-only in the Django admin: ConditionReport (handover and return) and its photos, RefundRequest, LedgerEntry, Invoice, InvoiceAdjustment | `B:rentals/admin.py` now `ReadOnlyModelAdmin`; payments' were already (`B:payments/admin.py`, unchanged) | `test_a_condition_report_is_view_only_signed_or_not` (2), `test_append_only_tables_cannot_be_added_in_admin` (now 8) [admin] |
| SE-4: a permission class on every endpoint, every role tested | `IsAdministrator` on every fleet, pricing and users admin view; `IsAdministrator | IsBranchManager` on the audit views; maintenance's new views | `test_endpoint_permission` × 6 roles in [fleet] (14 endpoints), [pricing] (9), [users] (12), [audit] (2), `B:maintenance/tests/test_permissions.py` (+3); `test_every_*_route_is_in_the_matrix` in each |
| SE-10: every admin write audited | `record_audit` in every admin service (Create/Update/Delete with before and after) | the audit assertions in each test above |

## 2. Exp 2 use cases

| Use case step | Implemented in | Tests |
|---|---|---|
| UC 11 step 1: add, edit or retire a vehicle (registration, category, specification, documents) | Section 1, Fleet.Add, edits, Fleet.Retire | [fleet] |
| UC 11 step 2: define or change a tariff with an effective date | `define_tariff()` | [pricing] |
| UC 11 step 3: the change is stored and audited | `record_audit` | [fleet], [pricing] |
| UC 11 extension 1a: registration or chassis exists → rejected | `_check_unique()` | `test_an_existing_registration_or_chassis_number_is_rejected_uc11_1a` |
| UC 11 extension 2a: previous tariff retained | new rows only | `test_a_confirmed_booking_keeps_the_tariff_it_was_priced_at` |
| UC 12 step 1: create, edit, disable, re-enable staff accounts | `accounts/admin_services.py` | [users] |
| UC 12 step 2: blacklist with the reason | `blacklist_customer()` | `test_blacklisting_records_the_reason_and_lists_confirmed_and_active_bookings` |
| UC 12 step 3: applied at once and audited | sessions end at once; BR-4 at the next booking | `test_disabling_ends_every_session_at_once_and_re_enabling_restores_sign_in`, `test_a_blacklisted_customer_cannot_book` |
| UC 12 extension 2a: Confirmed bookings listed, decided one by one | `open_bookings()`, R2's `cancel_booking()` | `test_a_confirmed_booking_is_cancelled_through_r2_and_audited_twice` |
| UC 9 extension 2a: Preventive and the due point pre-filled | `due_odometer`, `due_date` | `test_a_due_vehicle_gets_a_preventive_job_from_the_system_with_the_alert` |
| UC 9 step 3: attach the workshop invoice | `attach_invoice()` | `test_the_assigned_technician_attaches_a_workshop_invoice` |
| UC 10 extension 1a: only an Administrator or authorised technician clears Unsafe while closing | `complete_job(clear_unsafe=True)`, `may_clear_unsafe()` | section 1, BR-16 |

## 3. Exp 4 sequence diagram 3 (Close Maintenance Job), as N3 changes it

Messages 1 to 11 stay as in `docs/traceability-maintenance.md`. N3 adds a
second branch to message 4 for an authorised technician:

| # | Message | Implemented in | Tests |
|---|---|---|---|
| 4 | alt [vehicle flagged Unsafe] request clearance (BR-16) | unchanged without `clear_unsafe` | `test_an_authorised_technician_may_still_ask_an_administrator`, `test_an_unauthorised_technician_cannot_clear_unsafe` |
| 4' | [Unsafe, the closer may clear it] `Vehicle.update_status()` → Available, the closer recorded | `complete_job(clear_unsafe=True)` → `_clear_and_finish()` (shared with message 5's `approve_clearance()`) → `update_status(actor=the technician)`, `closed_by` = the technician | `test_an_authorised_technician_clears_unsafe_while_closing_and_is_recorded` |
| 5-7 | Administrator → `update_status()`; flag cleared, approver recorded | `approve_clearance()` → the same `_clear_and_finish()` | the Module 2 tests, unchanged and passing |
| 10 | compute next service due (BR-15) | `_finish()`; next due shown; the next automatic job comes from `raise_preventive_job_if_due()` | section 1, BR-15 |

## 4. Exp 3 class diagram

| Class / method | Implemented in | Tests |
|---|---|---|
| `Administrator.manage_fleet()` | `B:fleet/services/admin.py` (vehicles, documents, photos, branches, areas) through `F:features/admin/FleetPage.tsx`, `VehiclePage.tsx`, `BranchesPage.tsx` | [fleet] |
| `Administrator.define_tariff()` | `B:pricing/admin_services.py` `define_tariff()` | [pricing] |
| `MaintenanceJob.complete_job()` | `services.complete_job(…, clear_unsafe)` | [maint] |
| `Vehicle.update_status()` | `fleet/services/status.py` (BR-16 rule now `may_clear_unsafe()`) | [maint], `B:fleet/tests/test_status_service.py` |
| `Customer.is_blacklisted` (Exp 3) | `blacklist_customer()`, `lift_blacklist()` | [users] |

## 5. Exp 5 activity diagram and Exp 6 DFD

| Node | Implemented in | Tests |
|---|---|---|
| Exp 5 Phase 5 "Manage fleet, tariffs, users and blacklist" (Administrator) | `/app/fleet`, `/app/tariffs`, `/app/users` | [fleet], [pricing], [users] |
| Exp 5 Phase 5 "Create preventive job" (Maintenance) | `raise_preventive_job_if_due()` | [maint], [rentals] |
| DFD Level 2, process 7.2 "Raise Preventive Job (BR-15)" from the service interval | `raise_preventive_job_if_due()`, `raise_due_preventive_jobs()` | [maint] |
| DFD process 7.3 "service alert" → Maintenance Technician | `_notify_service_due()` | [maint] |
| Context diagram "document expiry alert" → Administrator | `alert_expiring_documents()` | [maint] |
| DFD process "Administer Fleet, Tariffs, Users" with D2 Vehicle and Fleet, D3 Tariff, D1 User and Licence, D8 Audit Log | the admin services, each writing D8 | all of section 1 |
| D8 Audit Log → "fleet status, audit log" to the Administrator | `/app/audit` | [audit] |

## 6. Demo data (seed_demo)

`B:maintenance/seed_n3.py`: **tech2@vrms.test** (Demo Technician
(authorised), password Demo@1234), authorised to clear Unsafe (BR-16); and
**MH02DN7001** at Bandra, past its BR-15 service distance (25,120 km, due
at 25,100), with its insurance expiring ten days after seeding: the daily
Beat tasks raise its Preventive job (with the service-due alert) and list
the document in the expiry alert, and SA-2 refuses its handover. No job is
seeded, so jobs 1 to 3 and every module's job count stay as they were.
`B:core/seed_admin.py`: **blacklist@vrms.test** with **MH02DB8001**
Confirmed three days ahead (paid by card) and **MH02DB8002** On Rent in an
Active rental due back in two days. `B:core/management/commands/seed_demo.py`
now also gives every demo vehicle a `fuel_capacity` (litres, kg for CNG,
kWh for the Tiago EV), filling vehicles seeded before (audited "Update").

To demo: as admin@vrms.test open /app/users → the blacklist customer →
Blacklist (reason) → cancel the Confirmed booking (password) while the
Active one shows "Return pending"; open /app/users → tech2 to see the
BR-16 authorisation; /app/fleet, /app/tariffs (define a tariff now or
scheduled, see the history), /app/audit (filter by action or entity);
manager@vrms.test sees /app/audit for Andheri only. For BR-16 by a
technician: staff@vrms.test reports a fault with "flag as Unsafe" and
schedules it to tech2, who starts it, records the work and ticks "Clear
the Unsafe flag as I close the job".

Tests: `test_n3_demo_has_an_authorised_technician_and_a_car_due_for_service`,
`test_n3_reset_removes_untouched_system_jobs_and_their_alerts`
(`B:maintenance/tests/test_seed.py`);
`test_the_customer_has_a_paid_confirmed_booking_and_an_active_rental`,
`test_seeding_again_adds_nothing_and_reset_reloads`
(`B:core/tests/test_seed_admin.py`); counts, `test_every_demo_vehicle_has_its_fuel_capacity`,
`test_fuel_capacity_is_filled_on_vehicles_seeded_before_it_was_set`
(`B:core/tests/test_seed_demo.py`).

## 7. Ownership notes

Endpoints in apps Rohan owns sit in separate files, with their logic in
separate service files: `B:fleet/admin_views.py`, `admin_serializers.py`,
`services/admin.py`; `B:pricing/admin_views.py`, `admin_serializers.py`,
`admin_services.py`; `B:accounts/admin_views.py`, `admin_serializers.py`,
`admin_services.py`; their `urls.py` gained one additive block each. No
migration was added to fleet, pricing, accounts, bookings or rentals; N3's
migrations are maintenance 0003 (fields and the authorisation model) and
0004 (the two PeriodicTasks).

## 8. Not built here

- SA-2 for search and booking (hiding a vehicle overdue for service): the
  catalogue and booking code are Rohan's; handover refuses it.
- An Administrator or staff booking detail screen: blacklist bookings link
  to their audit history (N3-P10).
- Vehicle categories and fuel prices have no screen (Django admin only).
- Forcing a new staff member to change the first password (N3-P8).
