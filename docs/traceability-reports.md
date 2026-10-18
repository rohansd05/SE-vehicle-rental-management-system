# Traceability: Reports, dashboards and booking notifications (Module R3)

Maps SRS 3.8 (Notify.Booking, Notify.Remind, Report.Dashboard,
Report.Utilisation, Report.Revenue, Report.Access and the 3.8.2 stimuli),
Book.Done.Customer, Book.Done.Branch, CI-5, CI-6 and SI-2 to the code and the
tests, with Exp 2 use case 14 "View Reports" and "Send Booking Notification",
the Exp 3 `BranchManager.view_branch_reports()`, the Exp 4 message it extends,
the Exp 5 report and notification lanes and Exp 6 process 8. SRS:
`docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf`.

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`. Test names are pytest functions (file in brackets) or
Vitest `it` titles (in quotes). Test files: `B:reports/tests/`
`test_services.py` [services], `test_api.py` [api], `test_seed.py` [seed];
`B:bookings/tests/test_notifications.py` [notify];
`B:notifications/tests/test_reminders.py` [remind],
`B:notifications/tests/test_delivery.py` [delivery];
`F:features/reports/reports.test.tsx` (Vitest).

Reports are computed on the fly in the database (annotate and aggregate; no
report tables or models). Money is `Decimal` and travels as decimal strings
(CO-6); a period is a range of local (IST) dates turned into UTC instants
(`services.Period`). Notifications are written as `Notification` rows in the
caller's transaction and sent by Celery after it commits
(`transaction.on_commit`), through the mock notification backend in
development and tests (SI-2.2).

## 1. Requirements

| Requirement | Implemented in | Tests |
|---|---|---|
| **Report.Dashboard** "the number of vehicles in each status, the collections and returns due today, the bookings and revenue for the current day, week and month, the overdue returns and the open maintenance jobs" | `B:reports/services.py` `dashboard()` (5 queries); `GET /api/v1/reports/summary/` (`DashboardView`); `F:features/reports/DashboardSummary.tsx` on the Administrator's and Branch Manager's home (`F:pages/DashboardPage.tsx`) | `test_the_dashboard_counts_everything_report_dashboard_asks_for`, `test_a_branch_manager_dashboard_covers_only_their_branch` [services]; "shows an Administrator today’s figures, bookings and revenue, and the fleet by status", "a Branch Manager’s summary names their branch", "is not shown to %s" (customer, staff, technician) |
| **Report.Utilisation** "the percentage of available hours during which a vehicle was on rent, by vehicle, category, branch and period, and … the least utilised vehicles" | `utilisation_report()`, `_vehicle_hours()`: hours on rent from the handover and return `ConditionReport.recorded_at` where they exist, the booked times otherwise (Active and Completed only); Under Maintenance hours from the job history; available = hours in the fleet less maintenance (R3-P1); rollups by category and branch in SQL; `LEAST_UTILISED` (5); `GET /api/v1/reports/utilisation/` | `test_utilisation_uses_the_actual_handover_and_return_times`, `test_utilisation_falls_back_to_the_booked_times`, `test_only_the_part_inside_the_period_counts`, `test_cancelled_no_show_and_uncollected_bookings_are_never_rented` (5 statuses), `test_an_overdue_rental_is_on_rent_until_the_end_of_the_period`, `test_under_maintenance_days_come_from_the_job_history_and_are_not_available`, `test_a_vehicle_counts_from_its_availability_date`, `test_the_future_part_of_a_period_is_left_out`, `test_a_retired_vehicle_is_left_out`, `test_utilisation_by_category_and_branch_and_the_least_utilised` [services]; "opens on utilisation for this month: figures, charts and the least utilised vehicles" |
| **Report.Revenue** "revenue, refunds and net revenue by period, branch, vehicle category and payment method, distinguishing rental income from add-on income, and excluding security deposits" | `revenue_report()`: from `Invoice` (and its `InvoiceLine`s), `InvoiceAdjustment` and `LedgerEntry` only; rental, add-ons, discounts, tax, debit notes (R2 modify and extend, N2 return charges) and credit notes (refunds) as separate lines; net = invoiced + debit notes − credit notes; by branch and category (correlated subqueries), by payment method from the ledger (Charge − Refund, a refund reversed by an Adjustment added back, R1-P12); deposits never counted (not on invoices; Deposit Hold/Release excluded); refunds awaiting approval (UC 13) shown apart, never counted; outstanding dues from `Customer.outstanding_due`; `GET /api/v1/reports/revenue/` | `test_revenue_shows_each_line_apart_and_nets_the_notes`, `test_revenue_by_branch_category_and_payment_method`, `test_a_refund_the_gateway_reversed_is_no_longer_a_refund`, `test_an_empty_period_reports_zero_not_none` [services]; "shows the revenue lines apart; refunds awaiting approval are not counted" |
| **Report.Access** "An Administrator shall be able to report on all branches and a Branch Manager only on their own branch. No other user class shall have access to revenue or cost reports." | `REPORT_READERS = IsAdministrator \| IsBranchManager` declared on all five views; every queryset through `apps/core/permissions.py` `scope_queryset()` (vehicles and jobs by `home_branch`, bookings, invoices, notes, ledger and refunds by the booking's `pickup_branch`), as N3's audit viewer; `scope_label()` | `test_only_administrators_and_branch_managers_read_reports` (5 endpoints × anonymous 401, customer, staff, technician 403, admin, manager 200), `test_every_report_view_declares_its_permission_class`, `test_a_branch_managers_report_names_their_branch` [api]; `test_a_branch_manager_sees_only_their_branchs_revenue`, `…_vehicles`, `…_maintenance_cost`, `test_a_branch_manager_sees_only_customers_who_booked_at_their_branch` [services]; "a Branch Manager’s report is limited to their branch (UC 14 extension 1a)"; guards "BRANCH_MANAGER reaches /app/reports" |
| UC 14 maintenance cost | `maintenance_report()`: labour (`MaintenanceJob.labour_cost`), parts (`PartUsed` quantity × unit cost) and the job total (`total_cost`, labour + parts, M12) per vehicle and per job type, every job type listed, the Preventive jobs the system raised counted (`automatic`, N3-P3); jobs by service date (R3-P7); `GET /api/v1/reports/maintenance/` | `test_maintenance_cost_per_vehicle_and_job_type` [services]; "shows maintenance cost per job type, including jobs the system raised" |
| UC 14 customers | `customer_report()`: new, active (R3-P5), the no-show count, the top 10 by net revenue (with their bookings and no-shows), every customer with a due and the total; `GET /api/v1/reports/customers/` | `test_customers_new_active_top_dues_and_no_shows`, `test_a_customers_no_shows_are_counted_in_the_top_list` [services]; "shows new, active and top customers, no-shows and dues" |
| Aggregation in the database, not Python loops | annotate/aggregate and correlated `Subquery`s; Python only formats the rows the database returns | `test_each_report_runs_a_fixed_number_of_queries` (summary 6, utilisation 5, revenue 9, maintenance 4, customers 6, with 2 and with 22 rentals) [api] |
| **Book.Done.Customer** "an e-mail message to the customer with the booking, price and collection details, and an SMS message with the pickup code"; **CI-6** (acceptance, price, collection instructions); **CI-5** (SMS with the reference and pickup code) | `B:bookings/services.py` `notify_booking_confirmed()` (price itemised as invoiced, UI-4; the deposit apart; the branch address and documents to bring), called at the end of `B:bookings/lifecycle.py` `_confirm()` for card, on-line and cash (`record_cash_payment()`); templates `booking_confirmed`, `booking_confirmed_sms` in `B:bookings/notification_templates.py` | `test_book_done_e_mails_and_texts_the_customer_and_tells_the_branch`, `test_cash_recorded_at_collection_confirms_and_notifies_the_same_way`, `test_a_repeated_payment_sends_nothing_twice`, `test_a_declined_payment_sends_nothing` [notify]; `test_every_template_renders` [delivery] |
| **Book.Done.Branch** "add the booking to the collection schedule of the pickup branch and notify the branch staff" | the Confirmed booking is on N1's collection list (`/app/branch-bookings`); `_notify(..., branches=[pickup_branch])` e-mails every active Branch Staff member there with the existing `booking_branch_update` (R3-P9) | `test_book_done_e_mails_and_texts_the_customer_and_tells_the_branch` (one e-mail to that branch's staff, none elsewhere) [notify]; R2's `test_cancelling_48_hours_ahead_refunds_everything` now sees two branch e-mails (Book.Done.Branch, then UC 4 step 6) |
| **Book.Done** (one transaction), **Book.Done.Failure** (roll back) | the rows are written inside `_confirm()`'s transaction; a failure leaves none and enqueues nothing | `test_a_failed_book_done_rolls_its_notifications_back` [notify] |
| **Notify.Booking** "by e-mail and SMS message on the confirmation, modification, extension, cancellation and no-show of a booking, stating the booking reference and the resulting status" | R2's e-mails unchanged; `_notify()` now also queues the SMS copy (`queue_sms()`, `<template>_sms`): `booking_modified_sms`, `booking_cancelled_sms`, `booking_extended_sms`, `booking_no_show_sms` (reference and status in each) | `test_a_cancellation_is_texted_once_with_its_reference_and_status`, `test_a_modification_is_texted_once`, `test_an_extension_is_texted_once`, `test_a_no_show_is_texted_once` [notify] |
| **Notify.Remind** (24 hours before collection) "stating the branch, the time, the pickup code and the documents to bring" | `B:notifications/services.py` `send_pickup_reminders()`: Confirmed bookings collected within `PICKUP_REMINDER_BEFORE` (24 h, `config/settings/business_rules.py`), no handover report, never reminded before (R3-P3), `SKIP LOCKED`; e-mail `pickup_reminder` and SMS `pickup_reminder_sms`; Celery task `B:notifications/tasks.py` `send_pickup_reminders`, a PeriodicTask registered by `B:notifications/migrations/0002_schedule_pickup_reminder.py` (every 5 minutes, R3-P4) | `test_a_booking_collected_within_24_hours_is_reminded_by_e_mail_and_sms`, `test_a_booking_is_never_reminded_twice`, `test_only_confirmed_bookings_are_reminded` (Cancelled, No-show, Active, Completed, Pending Payment, Draft), `test_a_booking_being_handed_over_is_not_reminded`, `test_the_window_is_the_next_24_hours` (4 boundaries), `test_a_booking_confirmed_inside_the_window_is_not_reminded`, `test_the_reminder_task_is_scheduled_every_5_minutes`, `test_the_reminder_lead_is_24_hours` [remind] |
| **SI-2.1** versioned templates, **SI-2.2** queued with the delivery status recorded per message | templates appended (version 1) to `B:bookings/notification_templates.py`; `queue_sms()` beside `queue_email()` (one `_queue()`); every row keeps channel, destination, template, version and status (Queued → Sent / Failed) | `test_queue_sms_writes_one_row_to_the_registered_mobile_and_sends_it` [remind]; the `sent()` row assertions [notify] |
| History.Privacy (staff never see the pickup code) | `deliver_notification()` reads the pickup code from the booking at send time; it is never in `Notification.context` (R3-P10) | the "never stored" assertions in `test_book_done_e_mails_and_texts_the_customer_and_tells_the_branch` [notify] and `test_a_booking_collected_within_24_hours_is_reminded_by_e_mail_and_sms` [remind] |
| **SE-4** explicit permission class; **CO-3** server-side rules | as Report.Access above; the screen only shows the server's answers | [api] |
| **CO-6** Decimal money, UTC storage, local presentation | `DecimalField`/`Decimal` throughout; `Period` turns IST dates into UTC instants; the API sends decimal strings; the CSV keeps them exact | `test_revenue_shows_each_line_apart_and_nets_the_notes` (every total a `Decimal`), `test_money_and_hours_are_decimal_strings`, `test_the_default_period_is_this_month_to_today` [api] |
| **UI-7** errors next to the field | the server's `date_to` / `date_from` errors under the "To" / "From" fields | `test_a_period_ending_before_it_starts_is_refused_on_its_field`, `test_a_date_that_is_not_a_date_is_refused` [api]; "shows the server’s refusal of a period on the To field" |
| **UI-8** progress for slow operations | "Computing the report…" with the submit button disabled while fetching; "Try again" on failure | "says so when a report cannot be computed, and tries again" |

## 2. Exp 2 use cases

### View Reports (UC 14)

| Step | Implemented in | Tests |
|---|---|---|
| Precondition: logged in as Administrator or Branch Manager | `REPORT_READERS`; `F:features/reports/routes.tsx` (`RequireRole`) | [api] permission matrix; guards test |
| 1 select a report type and a period | `F:features/reports/ReportsPage.tsx` form (Report, From, To; this month to today by default; kept in the address) | "shows the revenue lines apart; refunds awaiting approval are not counted" (choosing a report and dates) |
| 2 compute and display the report | the four services; figures, charts (`F:features/reports/chart.tsx`, Recharts) and tables (`parts.tsx`), defined per report in `views.tsx` | the four screen tests above |
| 3 optionally export the report to a file | "Export CSV": `F:features/reports/csv.ts` (`toCsv()`, `downloadCsv()`), the same sections as the tables, one file per report | "exports the report to a CSV file with the exact amounts (UC 14 step 3)", "quotes commas and quotes, keeps negative amounts, and defuses formulas in text" |
| 1a the actor is a Branch Manager: restrict to their own branch | `scope_queryset()` in every service; "<branch> branch only." on the screen | as Report.Access |
| Post-condition: displayed or exported | as steps 2 and 3 | — |

### Send Booking Notification

| Trigger | Customer (e-mail, SMS) | Branch | Tests |
|---|---|---|---|
| Confirmation (Book.Done) | `booking_confirmed`, `booking_confirmed_sms` | `booking_branch_update` to the pickup branch's staff | [notify] |
| Modification | R2's `booking_modified`, R3's `booking_modified_sms` | R2's `booking_branch_update` | `test_a_modification_is_texted_once` |
| Cancellation | R2's `booking_cancelled`, R3's `booking_cancelled_sms` | R2's `booking_branch_update` | `test_a_cancellation_is_texted_once_with_its_reference_and_status` |
| Extension | R2's `booking_extended`, R3's `booking_extended_sms` | — (R2-P10) | `test_an_extension_is_texted_once` |
| No-show | R2's `booking_no_show`, R3's `booking_no_show_sms` | — (R2-P10) | `test_a_no_show_is_texted_once` |
| 24 hours before collection | `pickup_reminder`, `pickup_reminder_sms` | — | [remind] |

Each trigger writes exactly one row per channel per recipient (the `sent()`
and `texts_after_confirmation()` assertions). Refund (R1), handover (N1),
settlement (N2) and maintenance (N3) messages are unchanged.

## 3. Exp 3 class diagram

| Exp 3 | Code |
|---|---|
| `BranchManager.view_branch_reports()` (`branch_id`) | the report services called with a Branch Manager: `scope_queryset()` limits them to `BranchManager.branch` (`branch_id_of()`) |
| `Administrator` (BranchManager's parent) | the same services, unscoped |
| `Booking`, `Vehicle`, `Branch`, `Invoice`, `Payment`, `ConditionReport`, `MaintenanceJob`, `Customer` | read only by the reports; `ConditionReport` and `MaintenanceJob` are N1's and N3's models, never written by R3 (the demo job goes through N3's services) |

## 4. Exp 4 message extended

The Exp 4 diagrams are images; as in `docs/traceability-booking.md`, the
messages follow their transcription in `docs/VRMS_Handoff.md` §4.

| Message (Exp 4, seq. 1) | Requirement | Implemented in | Tests |
|---|---|---|---|
| 8: status Confirmed, pickup code returned → Customer | Book.Done.Customer, Book.Done.Branch, CI-5, CI-6 | as before (`lifecycle._confirm()`), now followed by `notify_booking_confirmed()` in the same transaction | `test_book_done_e_mails_and_texts_the_customer_and_tells_the_branch`, `test_a_failed_book_done_rolls_its_notifications_back` [notify] |

## 5. Exp 5 activity diagram and Exp 6 DFD

| Item | Code |
|---|---|
| Exp 5 Book.Done fork: "Send e-mail and SMS with pickup code" | `notify_booking_confirmed()` inside `_confirm()` |
| Exp 5 "Send reminders 24 h and 2 h before pickup" | the 24-hour reminder (`send_pickup_reminders()`); the 2-hour one is not built (section 8) |
| Exp 5 Administrator lane "Daily, start of business → View dashboard" | `DashboardSummary` on the home page |
| Exp 5 "Reports scope? [Administrator] All-branch utilization and revenue reports / [Branch Manager] Own-branch reports only" | `scope_queryset()` in every report |
| Exp 6 Level 0: Branch Manager "report request / own-branch reports"; Notification Service "message payload / delivery status" | `/api/v1/reports/*`; `Notification` rows with their status |
| Exp 6 process 8 "Administer Fleet, Tariffs, Users and Reports" reading D4 Booking, D5 Payment Ledger, D6 Condition Report, D7 Maintenance Job | the report services read exactly these stores |

## 6. Screens

| Screen | File | Tests |
|---|---|---|
| `/app/reports` (Administrator, Branch Manager); the "Soon" flag removed from `F:app/navigation.ts` and the placeholder route replaced by `reportRoutes()` in `F:app/AppRoutes.tsx`; lazy-loaded so Recharts ships only with this page (PE-6) | `F:features/reports/ReportsPage.tsx`, `views.tsx`, `parts.tsx`, `chart.tsx`, `csv.ts`, `api.ts`, `routes.tsx`, `lazy.ts` | `F:features/reports/reports.test.tsx` (15) |
| Home page summary (Administrator, Branch Manager); R1's outstanding-due banner for customers unchanged | `F:features/reports/DashboardSummary.tsx`, one line in `F:pages/DashboardPage.tsx` | as above; `F:features/payment/due.test.tsx` unchanged |

Charts use only the chart tokens (`--chart-1`, and `--chart-4` for the second
series of the stacked cost chart) and pass `npm run check:design`. Most
charts are single-series (the identity is the axis label, never the colour);
the one two-series chart has a legend and a 2 px surface gap, and every chart
has a table of the same figures beside it. Bars are not animated (B6).

## 7. Demo (`seed_demo --reports`)

`B:reports/seed.py`, loaded by `seed_demo --reports` (one flag added to
`B:core/management/commands/seed_demo.py`): `reports@vrms.test` (password as
the other demo accounts) with ten past bookings over the last three months at
Andheri and Bandra (eight returned, one with return charges and a debit note,
one no-show with a credit note), their invoices and ledger entries (card,
on-line and cash, an add-on, a discount code), and one Preventive job with
parts at Bandra through N3's services. With the payments demo's pending refund
and due, every chart and table has data; `manager@vrms.test` (Andheri) sees
Andheri only. Plain `seed_demo` and its counts are unchanged (demo jobs 1 to 3,
N3's three-job expectation). Tests: [seed].

Why a flag (R3-P11): invoices, notes and ledger entries are append-only (a
PostgreSQL trigger refuses deletes), so this data can never be removed and
`seed_demo --reset` refuses once it is loaded, as it does after any demo that
moved money. Loading it by default would make every `--reset` fail, including
N3's seed tests.

## 8. Proposed readings (awaiting team approval)

| # | Item | Proposal |
|---|---|---|
| R3-P1 | Utilisation | Available hours: the hours of the period the vehicle was in the fleet (from its availability date, local midnight) up to now, less its Under Maintenance hours. On rent: Active and Completed bookings, from the handover report's time (else the pickup time) to the return report's (else the return time); an Active rental past its return time stays on rent. Under Maintenance: from a job's start (else its scheduled start) to its close or cancellation; Reported-only jobs do not count. A Retired vehicle is left out (no retirement time is stored). Least utilised: the five lowest percentages. |
| R3-P2 | Documents to bring | The driving licence on record (BR-2 and BR-3 are checked again at handover); the SRS lists no others |
| R3-P3 | Pickup reminder | Only Confirmed bookings (an unpaid cash booking has no pickup code yet), once per booking, and only for a booking confirmed at least 24 hours before its pickup; one booked later already got its confirmation e-mail and SMS |
| R3-P4 | Reminder schedule | Every 5 minutes |
| R3-P5 | Customers | New: registered in the period. Active: a Confirmed, Active or Completed booking collected in the period. Top: net revenue (invoices plus debit notes less credit notes issued in the period), ten. For a Branch Manager: the customers who ever booked at the branch |
| R3-P6 | Revenue | Invoices by issue date, notes by issue time, ledger entries by time, pending refunds by request time; amounts include tax (the tax line shows it); branch is the pickup branch, category the booked vehicle's; refunds awaiting approval only for rental payments |
| R3-P7 | Maintenance cost | A job counts by its service date (the work record), whatever its status except Cancelled, so work on a job awaiting clearance counts. There is no workshop-invoice amount in N3's model (the invoice is a file, N3-P6): the job total is labour plus parts (M12), and the number of attached invoices is shown |
| R3-P8 | Dashboard | Bookings counted by confirmation time; the week starts on Monday; revenue is net of notes; collections due today are Confirmed pickups today, returns due today Active returns today, overdue returns Active rentals past their return time |
| R3-P9 | Book.Done.Branch | An e-mail to every active Branch Staff member of the pickup branch, as R2 does for UC 4 step 6, with the existing `booking_branch_update` template |
| R3-P10 | Pickup code in messages | Read from the booking when the message is sent, never stored in the delivery log; e-mailed only in the reminder, texted at confirmation and in the reminder |
| R3-P11 | Reports demo | Behind `seed_demo --reports` (section 7) |
| R3-P12 | Export | CSV only, built in the browser from the figures the server sent (exact decimal strings); text cells starting with `=`, `+`, `-`, `@` are prefixed with `'` (formula injection) |
| R3-P13 | Period | Default this month to today; the end may not precede the start; any length |

## 9. Not built

- Notify.Remind's 2-hour reminder before collection and before the return
  (with the late return charge); the 3.8.2 overdue alert to the customer and
  the branch.
- Book.Done.Failure's message that the booking was unsuccessful; push
  notifications (CI-6); the 24-hour roadside assistance number on the
  confirmation (SA-4): no number is configured anywhere, and the SRS gives none.
- PDF export (optional); a revenue time series; an Administrator choosing one
  branch (the by-branch breakdowns show each).
- Notify.Payment beyond R1's refund messages.

## 10. Known limits

- `scope_label()` and the Branch Manager's profile check add queries for a
  Branch Manager; the counts above are for an Administrator. Both stay fixed
  as the data grows.
- A vehicle goes Under Maintenance when its job is scheduled, but the report
  counts from the job's start or scheduled start (the scheduling time is
  only in the audit log).
- The SRS's revenue and utilisation figures are not cached; each request
  computes them (no report tables, as asked).
