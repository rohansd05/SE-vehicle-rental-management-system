# VRMS — Model Mapping (Phase 1A)

How the Exp 3 class diagram and the SRS (`docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf`)
map onto the Django models. Use this with the traceability matrix: every
field the diagram does not name is either cited to an SRS requirement or
listed under **Proposed - awaiting team approval**.

Conventions used everywhere:

- **Money:** `DecimalField(max_digits=12, decimal_places=2)`. No `FloatField`
  exists in the schema; `apps/core/tests/test_no_float_fields.py` enforces it (CO-6).
- **Time:** events are `DateTimeField`, stored in UTC (`USE_TZ=True`). Calendar
  dates with no time of day (date of birth, licence and document expiry,
  service date) are `DateField`. The diagram's `Date` attributes are mapped
  accordingly.
- **Statuses:** `TextChoices` whose stored values are exactly the handoff
  state-machine names (for example `"Pending Payment"`, `"No-show"`).
  Transitions are enforced in later phases, not in the models.
- **on_delete:** `PROTECT` for anything financial or historical (bookings,
  payments, invoices, ledger, tariffs, condition reports, maintenance jobs,
  and every user reference on them). `CASCADE` only for true composition
  (profile → user, licence → customer, serviceable area → branch, document
  and photo → vehicle, add-on line → booking, part → job, photo → report).
- **Thresholds:** BR-1 to BR-16 and the fixed values (hold, cut-off,
  no-show, reference format) are named constants in
  `backend/config/settings/business_rules.py`, each citing its rule.
- **Files:** licence images, photos, signatures and documents are
  `FileField`s, which store only the object key (SI-3).

---

## 1. Where the 20 Exp 3 classes live

| Exp 3 class | Model | App | Shape |
|---|---|---|---|
| «interface» User | `User` | accounts | Custom user (AbstractBaseUser + PermissionsMixin) |
| Customer | `Customer` | accounts | Profile, OneToOne → User |
| BranchStaff | `BranchStaff` | accounts | Profile, OneToOne → User |
| MaintenanceTechnician | `MaintenanceTechnician` | accounts | Profile, OneToOne → User |
| Administrator | `Administrator` | accounts | Profile, OneToOne → User |
| BranchManager | `BranchManager` | accounts | Multi-table child of Administrator |
| Licence | `Licence` | accounts | OneToOne → Customer, CASCADE (composition) |
| Booking | `Booking` | bookings | Concrete |
| «interface» Vehicle | `Vehicle` | fleet | Concrete base |
| Car | `Car` | fleet | Multi-table child of Vehicle |
| TwoWheeler | `TwoWheeler` | fleet | Multi-table child of Vehicle |
| Branch | `Branch` | fleet | Concrete |
| Tariff | `Tariff` | pricing | Concrete; never edited once in effect (BR-13) |
| «interface» Payment | `Payment` | payments | Concrete base |
| CardPayment | `CardPayment` | payments | Multi-table child of Payment |
| CashPayment | `CashPayment` | payments | Multi-table child of Payment |
| OnlinePayment | `OnlinePayment` | payments | Multi-table child of Payment |
| Invoice | `Invoice` | payments | OneToOne → Booking, PROTECT; append-only |
| ConditionReport | `ConditionReport` | rentals | FK → Booking, PROTECT; frozen once signed |
| MaintenanceJob | `MaintenanceJob` | maintenance | Concrete |

Relationships: Customer ◆ Licence → `Licence.customer` (OneToOne, CASCADE).
Booking ◆ Invoice → `Invoice.booking` (OneToOne, PROTECT). Booking ◆
ConditionReport (0..2) → `ConditionReport.booking` plus a unique
(booking, report_type) constraint. Branch ◇ Vehicle → `Vehicle.home_branch`
(PROTECT). Branch ◇ BranchStaff → `BranchStaff.branch` (PROTECT). The
associations are FKs: `Booking.customer`, `Booking.vehicle`,
`Booking.pickup_branch`, `Payment.booking`, `ConditionReport.recorded_by`,
`MaintenanceJob.vehicle`, `MaintenanceJob.technician` and
`Tariff.defined_by`. The dependencies Booking ⇢ Licence and Vehicle ⇢ Tariff
are not FKs. They are resolved through Customer → Licence and
Vehicle → VehicleCategory → Tariff. A booking also stores the tariff it was
priced at (`Booking.tariff`, BR-13).

## 2. Attribute mapping (diagram → model)

Unchanged names are not repeated here. Only attributes whose type or shape
changed are listed.

| Class.attribute (Exp 3 type) | Model field | Why |
|---|---|---|
| User.password (String) | `User.password` (AbstractBaseUser) | Django's field; bcrypt-SHA256, 12 rounds (SE-2, D4) |
| User.mobile_no (int) | `User.mobile_no` CharField(15) | Keeps `+` and leading zeros |
| Customer.customer_id (int) | `Customer.customer_id` BigAutoField PK | Diagram id kept as the primary key |
| Customer.outstanding_due (double) | DecimalField(12,2), check ≥ 0 | CO-6; BR-4 |
| BranchStaff.staff_id (int) | `staff_id` BigAutoField PK | |
| BranchStaff.branch_id (int) | FK `branch` (column `branch_id`) | Referential integrity (CO-5) |
| MaintenanceTechnician.technician_id (int) | `technician_id` BigAutoField PK | |
| Administrator.admin_id (int) | `admin_id` BigAutoField PK | |
| **Administrator.admin_pass (String)** | **mapped to `User.password`** — no separate field | One bcrypt credential per person; a second password column would be a second secret to protect (SE-2) |
| BranchManager.branch_id (int) | FK `branch` (column `branch_id`) | |
| Licence.category (String) | `LicenceCategory` rows (`licence.categories`) | Appendix A: 1:m licence category |
| Licence.expiry_date (Date) | DateField, nullable | Not known while status is Not Submitted |
| Licence.status (String) | TextChoices | Not Submitted, Pending Verification, Verified, Rejected, Expired |
| Booking.pickup_datetime / return_datetime (Date) | DateTimeField (UTC) | |
| Booking.status (String) | TextChoices | Draft, Pending Payment, Confirmed, Active, Completed, Cancelled, No-show |
| Booking.pickup_code (int) | CharField(6), check `^[0-9]{6}$` | Six digits with leading zeros (Book.Done.Store) |
| Booking.booking_reference (String) | CharField(18), unique when set, check `^VRMS-[0-9]{8}-[0-9]{4}$` | Blank until confirmation (Appendix A) |
| Booking.total_amount (double) | DecimalField(12,2) | Appendix A "quoted amount" |
| Vehicle.odometer (int) | PositiveIntegerField | Whole km, never negative (Appendix A) |
| Vehicle.status (String) | TextChoices | Available, On Rent, Under Maintenance, Unsafe, Retired |
| Branch.branch_id (int) | `branch_id` BigAutoField PK | |
| Branch.serviceable_areas (String) | `BranchServiceableArea` rows, related name `serviceable_areas` | One row per pincode/locality keeps 3NF (CO-5) |
| Tariff.hourly_rate, daily_rate, security_deposit (double) | DecimalField(12,2) | CO-6 |
| Tariff.effective_from (Date) | DateTimeField (UTC) | Exact switch-over instant, no midnight time-zone ambiguity |
| Payment.transaction_id (String) | CharField(64), unique | |
| Payment.amount (double) | DecimalField(12,2), check > 0 | |
| Payment.status (String) | TextChoices | Initiated, Processing, Succeeded, Failed, Reversed |
| CashPayment.received_by (String) | FK → BranchStaff, PROTECT | BR-9: a named staff member |
| OnlinePayment.upi_id (String) | CharField, blank allowed | Blank (not NULL) per Django convention; only set for UPI |
| Invoice.issue_date (Date) | DateTimeField (UTC) | |
| Invoice.tax_amount, total_amount (double) | DecimalField(12,2) | |
| ConditionReport.odometer_reading (int) | PositiveIntegerField | |
| ConditionReport.fuel_level (double) | DecimalField(5,2), 0–100 | Fixed point (CO-6); unit is a percentage (proposed) |
| ConditionReport.signature (String) | FileField (object key) | SI-3 |
| MaintenanceJob.job_id (int) | `job_id` BigAutoField PK | |
| MaintenanceJob.total_cost (double) | DecimalField(12,2) | |
| MaintenanceJob.status (String) | TextChoices | Reported, Scheduled, In Progress, Completed, Cancelled |

The diagram's methods (`register()`, `calculate_price()`, `authorize()`,
`complete_job()`, and the rest) are behaviour, not columns. They are
implemented in each app's `services.py` from Phase 1B onward, following the
Exp 4 call order.

**Booking time range.** The handoff says `tsrange`. Our timestamps are
timezone-aware, so `Booking.blocked_period` is a `DateTimeRangeField`,
which is PostgreSQL `tstzrange`. `tsrange` would drop the offset and compare
local wall-clock times.

## 3. Additions required by the SRS

### accounts
| Field / model | SRS source |
|---|---|
| `User.role` (Customer, Branch Staff, Maintenance Technician, Administrator, Branch Manager) | SRS 2.2, UI-1 (Phase 0) |
| `Customer.date_of_birth` | BR-2 (minimum age), Appendix A |
| `Customer.is_blacklisted` | BR-4, SRS 3.7 |
| `Customer.emergency_contact_name`, `emergency_contact_mobile` (required) | SA-4 |
| `Licence.licence_number` (diagram), `issuing_authority`, `issue_date`, `front_image`, `back_image` | Appendix A licence |
| `Licence.verified_by`, `verified_at` | Licence.verify(); SE-10 audits verification decisions |
| `LicenceCategory` | Appendix A 1:m licence category; BR-3 |
| `OneTimePassword` (purpose, destination, `code_hash`, expiry, attempts, consumed) | SE-7; only a hash of the code is stored |
| `Licence.rejection_reason` (Phase 1B) | SE-10 licence verification decision; a rejection always states why |

### fleet
| Field / model | SRS source |
|---|---|
| `VehicleCategory` (name, vehicle_type) | Appendix A "vehicle category"; Fleet.Tariff is per category; Search.Filter; Report.* by category |
| `Vehicle.category`, `home_branch`, `year`, `colour`, `fuel_type`, `chassis_number`, `available_from` | Fleet.Add |
| `Vehicle.last_service_date`, `last_service_odometer` | Maint.Complete, Search.Detail, BR-15 |
| `Vehicle.vehicle_type` (property via category) | Appendix A "vehicle type" |
| `VehicleDocument` (Insurance, Pollution Certificate, Fitness Certificate, Road Tax; expiry date) | Fleet.Add, SA-3, Handover.Refuse |
| `VehiclePhoto` | Fleet.Add, Search.Detail (at least four photographs) |

**Why VehicleCategory is a table.** The SRS needs a category that is
separate from the vehicle type. Tariffs are defined per category
(Fleet.Tariff), searches filter by it (Search.Filter), reports group by it
(Report.Utilisation, Report.Revenue), and maintenance offers "a vehicle of
the same category" (Maint.Conflict). The SRS never lists the categories, so
fixed choices would invent values. A table makes them Administrator-managed
master data, and lets Tariff reference the category with an FK.

### pricing
| Field / model | SRS source |
|---|---|
| `Tariff.vehicle_category` | Fleet.Tariff (per category) |
| `Tariff.weekly_rate` | Fleet.Tariff |
| `Tariff.free_km_allowance` | Fleet.Tariff, Book.Quote.Terms, BR-11 |
| `Tariff.excess_km_rate` | Fleet.Tariff, BR-11 |
| `Tariff.defined_by` → Administrator | Exp 3 Administrator–Tariff association; BR-13 |
| No edit or delete once `effective_from` has passed | BR-13, Fleet.Tariff.History |
| `AddOn` (name, `daily_rate`, active) | Book.Addons, BR-7 |
| `FuelPrice` (fuel type, price per unit, effective from, defined by) | BR-12 "prevailing fuel or electricity price" |
| `DiscountCode` (case-insensitive code, Percent/Fixed value, validity, usage limit) (Phase 1B) | BR-6 "less any discount"; D17 |

### bookings
| Field / model | SRS source |
|---|---|
| `Booking.customer`, `vehicle`, `pickup_branch` | Exp 3 associations; Appendix A |
| `Booking.tariff` | Fleet.Tariff.History, BR-13 |
| `Booking.security_deposit` | Appendix A; Pay.Deposit |
| `Booking.delivery_address`, `delivery_pincode` | Book.Deliver.Location |
| `Booking.hold_expires_at` | Book.Hold, Book.Hold.Expire |
| `Booking.confirmed_at` | Book.Done.Store; BR-13 "when the booking was confirmed" |
| `Booking.terms_accepted_at` | Book.Quote.Terms |
| `Booking.safety_notice_acknowledged_at` | SA-1 (stored with the booking) |
| `Booking.handed_over_at` | Handover.Activate |
| `Booking.returned_at` | Return.Checklist (actual return time) |
| `Booking.distance_travelled` | Return.Complete |
| `Booking.blocked_period` + ExclusionConstraint | Book.NoDouble, Book.Concurrent, Book.Done.Block, BR-1, Reliability-1 |
| `BookingAddOn` (quantity, `daily_rate` snapshot, detail) | Book.Addons, BR-7, BR-13 |
| `Booking.discount_code`, `discount_amount` (Phase 1B) | BR-6, D17 |
| `Rating` (OneToOne booking, vehicle and service 1–5, comment) (Phase 1B) | Search.Detail, Search.Filter; D13 |

The exclusion constraint covers (`vehicle` =, `blocked_period` &&) for
status in (Pending Payment, Confirmed, Active). Pending Payment is
included because the 15-minute hold must keep the vehicle from other
customers (Book.Hold). `blocked_period` = `[pickup, return + 60 min)`.

### payments
| Field / model | SRS source |
|---|---|
| `Payment.booking` | Exp 3 Booking–Payment association |
| `Payment.transaction_type` (Authorize, Capture, Refund) | Appendix A; SI-1.1 to SI-1.3 |
| `Payment.purpose` (Rental, Security Deposit, Due) | Pay.Deposit (deposit held separately), Pay.Dues |
| `Payment.idempotency_key` (unique) | Pay.Idempotent, SI-1.3 |
| `Payment.gateway_reference`, `initiated_by` | Appendix A payment transaction |
| `Payment.original_payment` | Pay.Refund, BR-14 (refund to the original instrument) |
| `Payment.failure_reason` | SRS 3.4.2 (display the reason for a rejection) |
| `CardPayment` keeps only `card_token`, `card_brand` | CO-2 |
| `CashPayment.customer_acknowledged_at` | Pay.Refund (cash refund acknowledged by the customer) |
| `OnlinePayment.channel` (UPI, Net Banking, Wallet) | Pay.Method; D6 |
| `Invoice.agency_name`, `agency_tax_registration` (copied at issue) | Pay.Invoice; D7 |
| `Invoice.issued_by` | Pay.Ledger (user who initiated) |
| `InvoiceLine` (line type, quantity, unit price, amount, justification) | Pay.Invoice itemised list; UI-4; Return.Charges |
| `InvoiceAdjustment` (credit or debit note on the original) | Pay.Invoice, History.Immutable |
| `LedgerEntry` (Charge, Capture, Refund, Deposit Hold, Deposit Release, Adjustment) | Pay.Ledger |
| Append-only trigger and model guard on Invoice, InvoiceLine, InvoiceAdjustment, LedgerEntry | Pay.Invoice, Pay.Ledger |

### rentals
| Field / model | SRS source |
|---|---|
| `ConditionReport.booking`, unique (booking, report_type) | Exp 3 composition 0..2 |
| `ConditionReport.recorded_by` → BranchStaff, `recorded_at` | Exp 3 association; Appendix A |
| `ConditionReport.signed_at`; frozen once signed | Handover.Sign |
| `ConditionReport.accessories` | Handover.Checklist, Return.Checklist |
| `ConditionReport.damage_marks` | Appendix A 0:m damage mark; Handover.Checklist |
| `ConditionReport.odometer_override_by`, `odometer_override_reason` | Return.Odometer |
| `ConditionPhoto` | Handover.Checklist, Return.Checklist (at least four photographs) |

### maintenance
| Field / model | SRS source |
|---|---|
| `MaintenanceJob.job_type` (Preventive, Corrective, Inspection, Cleaning, Documentation) | Maint.Create |
| `MaintenanceJob.vehicle`, `technician` | Exp 3 associations; Appendix A "assigned to" |
| `MaintenanceJob.reported_problem`, `reported_by` | Maint.Create |
| `MaintenanceJob.scheduled_from`, `scheduled_to` | Maint.Schedule, Appendix A |
| `service_date`, `odometer_at_service`, `work_description`, `labour_cost`, `workshop_invoice` | Maint.Record |
| `closed_by`, `closed_at` | BR-16, Maint.Unsafe |
| `PartUsed` (part, quantity, unit cost) | Maint.Record; SRS Fig. 2 "each consuming many Parts" |

### notifications
| Field / model | SRS source |
|---|---|
| `Notification` (recipient, channel, destination, template, version, context, status, provider id, timestamps, booking) | Notify.*, SI-2.1 (versioned templates), SI-2.2 (delivery status) |

### core
| Field / model | SRS source |
|---|---|
| `AuditLog` (actor, action, entity type/id, before/after JSON, IP, timestamp) | Fleet.Audit, SE-10 |
| `AuditLog.prev_hash`, `entry_hash` (SHA-256 chain; `prev_hash` unique) | SE-10 tamper evidence |
| Append-only trigger and model guard on AuditLog | SE-10, Fleet.Audit |
| `TimeStampedModel` (created_at, updated_at) | Shared base |

---

## 4. Interpretations to confirm

These follow from the SRS but involve a reading the team should confirm.

1. **Licence categories are the vehicle types. Confirmed (D18).** BR-3 says a customer may
   rent "only those vehicle categories for which the licence is endorsed",
   and BR-2 and BR-3 distinguish only two-wheelers and cars. So
   `LicenceCategory.category` is Car or Two-Wheeler, and the BR-3 check
   compares it with `vehicle.category.vehicle_type`. `VehicleCategory`
   (Hatchback, SUV, ...) is the tariff category.
2. **PROTECT on two compositions.** The diagram draws Booking ◆ Invoice and
   Booking ◆ ConditionReport as compositions, which would normally cascade.
   Both are financial or historical records, so the session rules make them
   PROTECT. A booking that has either can never be deleted.
3. **When the invoice is issued.** Pay.Invoice says "for every completed
   booking"; the Exp 4 sequence generates it at confirmation. The model
   allows exactly one invoice per booking either way; Phase 3 decides when.
4. **Ownership exception.** As instructed for this session, all apps'
   models (including Nidhi's pricing, rentals and maintenance) were laid
   down together so later migrations don't collide. From now on the
   CLAUDE.md Ownership rule applies again.

## 5. Proposed - awaiting team approval

The SRS is silent on these, but the models could not be built without
choosing something. Each needs a yes/no or a correction from the team.

| # | Item | Where | Proposal |
|---|---|---|---|
| P1 | Fuel type values | `core.choices.FuelType` (Vehicle, FuelPrice) | Petrol, Diesel, CNG, Electric |
| P2 | Transmission values | `Car.transmission` | Manual, Automatic |
| P3 | Severity scale | `MaintenanceJob.severity` | Low, Medium, High, Critical |
| P4 | Notification status values | `Notification.status` | Queued, Sent, Delivered, Failed |
| P5 | Unit of the free-km allowance | `Tariff.free_km_allowance` | Kilometres per rental day |
| P6 | Fuel or battery capacity | `Vehicle.fuel_capacity` (nullable) | Needed to turn a fuel-level shortfall into litres/kWh for BR-12 |
| P7 | Fuel level unit | `ConditionReport.fuel_level` | Percentage 0–100 |
| P8 | Accessories and damage marks shape | `ConditionReport.accessories`, `damage_marks` | JSON lists (names; marks with position and note) rather than child tables |
| P9 | Add-on restricted to a vehicle type | `AddOn.vehicle_type` (blank = any) | Helmet → two-wheeler, child seat → car |
| P10 | Licence numbers unique | `Licence` partial unique constraint | Unique when not blank |
| P11 | Pincode format | `BranchServiceableArea.pincode` | Six digits (Indian PIN code) |
| P12 | Vehicle year range | `Vehicle.year` validator | 1990–2100 |
| P13 | OTP ties to an existing user | `OneTimePassword.user` (required) | Registration creates an inactive user first, activated after the OTP |
| P14 | One Branch Manager per branch | `BranchManager.branch` | Not enforced (FK, not unique); SRS 2.2 describes headcount, not a rule |
| P15 | Technician optional on a job | `MaintenanceJob.technician` (nullable) | A job is reported before it is assigned |
| P16 | Invoice tax registration source | `settings.AGENCY_TAX_REGISTRATION` (env) | Copied onto each invoice at issue |
| P17 | Field lengths | all `max_length` values | Chosen for Indian formats (e.g. registration 16, mobile 15) |

Proposed values for authentication, OTPs and licence uploads (Phase 1B)
are listed in `docs/decisions.md`, D20 (A1–A16).

### Gaps (all closed in Phase 1B)

| # | Gap | SRS reference | Resolution |
|---|---|---|---|
| G1 | **Vehicle ratings.** The SRS shows an average rating and filters by it, but has no requirement that captures a rating. | Search.Detail, Search.Filter | D13: `bookings.Rating` per Completed booking; average computed, never stored |
| G2 | **Tax rate.** BR-6 adds "taxes" but gives no rate. | BR-6, Pay.Invoice | D14: `TAX_RATE_PERCENT = 18.00`, **a placeholder awaiting confirmation** |
| G3 | **OTP lifetime and attempt limit.** | SE-7 | D15: 10 minutes, 5 attempts |
| G4 | **Odometer plausibility limit.** | Return.Odometer | D16: none beyond "not lower than at handover" (AS-4) |
| G5 | **Discounts.** BR-6 subtracts "any discount" but no source is defined. | BR-6 | D17: `pricing.DiscountCode`; Booking records the code and amount |
