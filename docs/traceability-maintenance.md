# Traceability: Close Maintenance Job (Module 2)

Maps every message of Exp 4 sequence diagram 3 ("Close Maintenance Job"),
and every Exp 3 class-diagram method the module uses, to the code that
implements it and the tests that prove it. SRS:
`docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf` (3.6, Appendix B, BR-15,
BR-16). How the waiting clearance is stored is in `docs/model-mapping.md`;
proposed readings (M1–M14) are in `docs/decisions.md`.

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`. Test names are pytest functions or Vitest `it` titles.

## 1. Sequence diagram 3, message by message

| # | Message (Exp 4, seq. 3) | Requirement | Implemented in | Tests |
|---|---|---|---|---|
| 1 | MaintenanceTechnician → MaintenanceJob: `complete_job()` | Maint.Complete, BR-16 (who may close) | `B:maintenance/models.py` `MaintenanceJob.complete_job()` → `B:maintenance/services.py` `complete_job()`; API `POST /api/v1/maintenance/jobs/{id}/complete/` (`JobCompleteView`); UI "Complete job" in `F:features/maintenance/JobDetailPage.tsx` | `test_class_diagram_methods_delegate`, `test_other_technician_cannot_complete`, `test_administrator_may_complete_directly`, `test_complete_only_in_progress`; permission matrix `job-complete-*` in `test_permissions.py` |
| 2 | MaintenanceJob (self): validate recorded work, parts and cost | Maint.Record | `services.missing_work()` (service date, odometer, work, downtime, total = labour + parts); the record itself via `services.record_work()` / `PUT …/record/` / `RecordWorkForm.tsx` | `test_record_computes_total_and_replaces_parts`, `test_record_validation`, `test_record_only_while_in_progress`, `test_factory_job_has_no_record` |
| 3 | alt [recorded work incomplete]: "job cannot be closed, record work first" → technician | Maint.Record | `services.WorkIncompleteError` raised by `complete_job()`; API 400 `{code: "work_incomplete", missing: […]}`; UI alert (`aria-live`) | `test_complete_refused_when_work_not_recorded`, `test_complete_without_record_says_record_work_first`; Vitest "shows \"record work first\" when the server refuses to close the job" |
| 4 | alt [vehicle flagged Unsafe]: MaintenanceJob → Administrator: request clearance of Unsafe flag (BR-16) | BR-16, Maint.Unsafe, SA-3 | `complete_job()` sets `clearance_requested_at` (job stays In Progress, `awaiting_clearance`), audits "Clearance Requested", e-mails every active Administrator (`_notify_clearance_requested`, template `maintenance_clearance_requested`); queue `GET …/clearances/` (`ClearanceQueueView`); UI `ClearanceQueuePage.tsx` and the "Awaiting administrator clearance" notice | `test_complete_unsafe_vehicle_waits_for_clearance`, `test_unsafe_job_waits_then_admin_approves`; Vitest "shows the awaiting-clearance state and no Complete button" |
| 5 | Administrator → Vehicle: `update_status()` | BR-16, Fleet.Status | `services.approve_clearance()` → `fleet/services/status.py` `update_status(vehicle, Available, actor=admin)`; API `POST …/jobs/{id}/approve-clearance/` (`IsAdministrator`); UI "Clear Unsafe flag and complete" dialog | `test_administrator_approves_clearance`, `test_non_administrator_cannot_approve_clearance`, `test_br16_non_administrator_cannot_clear_unsafe`, `test_technician_cannot_clear_unsafe_through_the_status_service`; permission matrix `job-approve-clearance-*` |
| 6 | Vehicle → Administrator: status = Available | Appendix B (Unsafe → Available only via BR-16) | `status.py` `ALLOWED_TRANSITIONS`, `check_transition()` | `test_br16_administrator_clears_unsafe_and_is_recorded`, `test_every_legal_transition_is_saved_and_audited[Unsafe-Available]` |
| 7 | Administrator → MaintenanceJob: flag cleared, approver recorded | BR-16 ("the identity of that user is recorded"), SE-10 | `_finish()` sets `closed_by` = the Administrator and `closed_at`; the vehicle's audit entry has the same actor | `test_administrator_approves_clearance` (asserts `closed_by` and the audit actor), `test_unsafe_job_waits_then_admin_approves`; Vitest "reviews the job, vehicle and work, approves, and the queue empties" |
| 8 | [vehicle not flagged]: MaintenanceJob → Vehicle: `update_status()` | Maint.Complete | `complete_job()` → `_release_vehicle()` → `update_status(vehicle, Available)`; held Under Maintenance while another job is open (M7) | `test_complete_unflagged_vehicle_becomes_available`, `test_vehicle_stays_under_maintenance_while_another_job_is_open`, `test_clearance_with_another_open_job_leaves_vehicle_under_maintenance` |
| 9 | Vehicle → MaintenanceJob: status = Available | Appendix B (Under Maintenance → Available) | `status.py` | `test_every_legal_transition_is_saved_and_audited[Under Maintenance-Available]`, `test_technician_completes_a_normal_job` |
| 10 | MaintenanceJob (self): compute next service due (BR-15) | BR-15, Maint.Complete | `_finish()` updates `Vehicle.last_service_date` / `last_service_odometer`; `services.next_service_due()` computes km and date (`config/settings/business_rules.py` intervals); shown in the API (`next_service_due`) and on the job page | `test_br15_car_interval`, `test_br15_two_wheeler_interval`, `test_br15_unknown_without_a_service_record`, `test_older_service_date_does_not_overwrite_last_service`, `test_complete_unflagged_vehicle_becomes_available`; Vitest "records the work and parts, then completes; the vehicle is Available" |
| 11 | MaintenanceJob → MaintenanceTechnician: job status = Completed | Maint.Status, Appendix B | `_finish()` sets `status = Completed`, audits "Complete"; UI success message | `test_complete_unflagged_vehicle_becomes_available`, `test_technician_completes_a_normal_job`; Vitest "records the work and parts, then completes; the vehicle is Available" |

## 2. Class-diagram methods (Exp 3) used by the module

| Method | Implemented in | Behaviour | Tests |
|---|---|---|---|
| `MaintenanceJob.schedule_job()` | `B:maintenance/models.py` → `services.schedule_job()`; API `POST …/jobs/{id}/schedule/`; UI `ScheduleCard.tsx` | Reported → Scheduled with a technician and a period (Maint.Schedule); an Available vehicle goes Under Maintenance (Appendix B; Exp 4 seq. 2 `schedule_job() → update_status()`); overlapping Confirmed bookings need confirmation (Maint.Conflict, 409); the technician is e-mailed | `test_class_diagram_methods_delegate`, `test_schedule_assigns_and_takes_vehicle_off_the_road`, `test_schedule_keeps_an_unsafe_vehicle_unsafe`, `test_schedule_conflict_needs_confirmation`, `test_schedule_rejects_bad_period_inactive_technician_and_wrong_status`, `test_schedule_conflict_is_409_with_bookings`; Vitest "lists conflicting bookings and schedules anyway on confirmation" |
| `MaintenanceJob.complete_job()` | `B:maintenance/models.py` → `services.complete_job()` | Section 1, messages 1–11 | Section 1 |
| `Vehicle.update_status()` | `B:fleet/models.py` → `B:fleet/services/status.py` `update_status()` | Appendix B state machine; row lock (`select_for_update`); BR-16 (only an Administrator clears Unsafe); Fleet.Retire guards; every change audited | `test_model_method_delegates_to_the_service`, `test_every_legal_transition_is_saved_and_audited` (13), `test_every_illegal_transition_is_refused` (7), `test_row_is_locked_for_update`, `test_transition_is_checked_against_the_database_not_a_stale_instance`, BR-16 and retirement tests in `fleet/tests/test_status_service.py` |

## 3. Supporting requirements

| Requirement | Implemented in | Tests |
|---|---|---|
| Maint.Create (report a fault), Maint.Unsafe (flag at report) | `services.report_job()`; `POST …/jobs/`; `ReportFaultPage.tsx` | `test_report_creates_a_reported_job_and_leaves_the_vehicle_status`, `test_report_can_flag_the_vehicle_unsafe`, `test_cannot_report_on_a_retired_vehicle`; Vitest "validates the report form, then sends it and opens the new job" |
| Appendix B: Scheduled → In Progress | `services.start_job()`; `POST …/start/` | `test_only_the_assigned_technician_starts`, `test_start_refused_while_vehicle_is_on_rent`, `test_start_moves_an_available_vehicle_under_maintenance` |
| Appendix B: Cancelled from Reported or Scheduled only | `services.cancel_job()`; `POST …/cancel/`; cancel dialog | `test_cancel_scheduled_job_releases_the_vehicle`, `test_cancel_keeps_unsafe_flag`, `test_cannot_cancel_in_progress_or_without_reason`, `test_cancel_endpoint` |
| Maint.History | `GET …/vehicles/{id}/history/` | `test_technicians_list_and_vehicle_history` |
| Maint.Schedule (blocked from search) | `services.blocked_vehicle_ids()` (for Search.Available) | `test_blocked_vehicle_ids_for_search` |
| SE-4 (every endpoint, every role) | explicit `permission_classes` on every view in `B:maintenance/views.py` | `test_permissions.py`: 13 endpoints × 6 roles incl. anonymous, and `test_every_maintenance_route_is_in_the_matrix` |
| SE-5 (scoping: branch for staff, own jobs for a technician) | `views.scoped_jobs()`, `scoped_vehicles()`, `services._check_branch()`, `_check_assignee()` | `test_technician_sees_only_own_jobs`, `test_staff_scoped_to_their_branch`, `test_staff_cannot_report_on_another_branchs_vehicle`, `test_branch_manager_reports_on_own_branch` |
| SE-10 (audit) | `record_audit` in every service write; `update_status()` | `test_every_legal_transition_is_saved_and_audited`, `test_report_creates_a_reported_job_and_leaves_the_vehicle_status`, `test_complete_unflagged_vehicle_becomes_available` |
| SI-2.2 (notifications through Celery after commit) | `apps.notifications.services.queue_email` with templates in `B:maintenance/notification_templates.py` | `test_schedule_assigns_and_takes_vehicle_off_the_road`, `test_complete_unsafe_vehicle_waits_for_clearance` (both check the outbox) |
| Fleet.Status display, consistent vehicle status | `F:components/VehicleStatusBadge.tsx` | Vitest "names the %s status in text, not colour alone" |
| Demo data | `B:maintenance/seed.py`, called from `seed_demo` | `maintenance/tests/test_seed.py`, `core/tests/test_seed_demo.py` |
