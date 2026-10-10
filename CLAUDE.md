# CLAUDE.md — Project Rules for Claude Code

This file is read automatically at the start of every Claude Code session
in this repository. Follow it exactly. If any instruction here conflicts
with a request in chat, ask before proceeding rather than silently
picking one.

## What this project is

Vehicle Rental Management System (VRMS) — a Django REST Framework backend
+ React/TypeScript frontend, built from a fixed academic SRS. This is not
a greenfield app where you can invent requirements. Every business rule,
status, and field name already exists in `docs/experiments/` and must be
matched exactly, not reinterpreted.

## Non-negotiable source of truth

- `docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf` is the
  authoritative specification. If code and SRS disagree, the SRS wins —
  flag the conflict, don't silently resolve it.
- Business rules are BR-1 through BR-16 (Section 5.5 of the SRS). Never
  invent a business rule or a numeric threshold (grace periods, deposit
  amounts, cancellation percentages, service intervals) — look it up.
- Requirement IDs (e.g. `Book.Done.Store`, `Handover.Refuse`,
  `Search.Available`) should appear as comments or docstrings next to the
  code that implements them, so the traceability matrix stays honest.
- The 20 classes and their attributes/methods in Exp 3 (Class Diagram) are
  the starting model shape. Extend them where the SRS requires fields the
  diagram omitted (e.g. `VehicleDocument`, `PartUsed`, `AddOn`, `Ledger`,
  `AuditLog`) — don't rename or drop existing ones.

## Hard technical constraints

- **Money:** always `DecimalField` / `Decimal`. Never `float` for any
  monetary value, anywhere, including in tests and fixtures (CO-6).
- **Time:** store everything in UTC. Convert to local time only at the
  presentation layer (CO-6).
- **Booking overlap:** must be enforced at the database level via a
  PostgreSQL exclusion constraint on the booking time range, not just in
  application code. This is what makes Reliability-1 (100 concurrent
  confirmations, exactly one succeeds) actually pass.
- **Security:**
  - All business logic (availability, pricing, eligibility) is enforced
    server-side. Client-side checks are UX only, never the sole control
    (CO-3).
  - Every endpoint needs an explicit DRF permission class. Never rely on
    hiding a button in the UI to restrict access (SE-4).
  - Passwords: bcrypt, work factor ≥ 12. Never log, email, or display a
    password or card detail (SE-2, CO-2).
  - No card numbers, expiry, or CVV touch our backend or logs — payment
    gateway hosted fields/tokens only.
- **External services:** Payment Gateway and Notification Service must
  each sit behind an interface in `integrations/` with at least a
  sandbox/mock implementation, so tests never hit a real network call.
- **Audit log:** any create/update/delete of vehicle, tariff, branch,
  user, or blacklist data must write an audit entry. Audit entries are
  append-only — no update or delete endpoint should ever touch them.
- **Invoices and ledger entries** are immutable once created. Corrections
  are new records (credit notes / adjustments) that reference the
  original, never edits.

## Workflow expectations

- Before implementing a feature, state which SRS section and requirement
  IDs it covers, in one or two lines, before writing code.
- Write tests alongside the code, not after — especially anything
  touching pricing, availability, or settlement (target: 100% coverage
  on those per Maintainability-2).
- Prefer small, reviewable commits scoped to one app or one feature.
  Don't bundle backend and frontend changes for unrelated features in
  one commit.
- Don't add new dependencies without checking they're MIT/Apache 2.0/BSD
  licensed, or covered by the CO-7 amendment (see Decisions, D2).
- Ask before running destructive commands (`migrate --fake`, dropping a
  database, force-pushing, deleting migrations).
- Run Python tools through `backend\venv\Scripts\python.exe` (Python 3.12).
- After any API change, run `npm run api:schema` and `npm run api:types` in
  `frontend/` and commit `docs/api/openapi.yaml` and `src/api/schema.d.ts`.
- Frontend tokens: the access token stays in memory only; never use
  localStorage or sessionStorage for tokens (D21).
- Celery on Windows needs `--pool=solo`
  (`celery -A config worker -l info --pool=solo`); the default prefork pool
  does not work there.

## Decisions

Settled before Phase 0; full rationale in `docs/decisions.md`. These
supersede section 7 ("Open decisions") of `docs/VRMS_Handoff.md`.

- **D1 Deployment:** one Azure VM (Ubuntu) running docker-compose with
  Postgres 16, Valkey, Django + gunicorn, Celery worker, Celery Beat and
  Caddy (serves the React build, reverse-proxies `/api` and `/admin`,
  automatic HTTPS). Nothing may block this layout.
- **D2 CO-7 amended:** "LGPL libraries used unmodified as dependencies
  (psycopg) and HPND (Pillow) are permitted." Valkey (BSD) replaces the
  Redis server, whose current licences fail CO-7; the `redis` Python
  client (MIT) is still used.
- **D3 Local dev:** Postgres and Valkey run in Docker; Django runs natively
  in a Windows venv. reportlab replaces weasyprint. python-magic is removed;
  uploads are validated by extension, size and Pillow `verify()`.
- **D4 Hashing:** argon2-cffi removed. The first `PASSWORD_HASHERS` entry is
  a `BCryptSHA256PasswordHasher` subclass with `rounds = 12` (SE-2).
- **D5 Configuration:** django-environ only; python-decouple and
  dj-database-url removed.
- **D6 Online payments:** UPI, net banking and wallet are channels of
  `OnlinePayment` (a `channel` field, Phase 1; `upi_id` kept). No separate
  wallet class.
- **D7 Currency and name:** currency is INR. The agency name comes only
  from settings `AGENCY_NAME` (default placeholder `"[Agency Name]"`).
  Never hardcode the name in the backend or the frontend.
- **D8 Mobile:** a responsive PWA meets OE-2 for Release 1.0.
- **D9 Scope:** every feature in the SRS and Experiments 1-7, deployed by
  12 Oct 2026, built by two developers in parallel.
- **D10 CO-7 amended further:** ISC (MIT-equivalent) is permitted. MPL-2.0
  and LGPL are permitted for dependencies used unmodified. Build-time tools
  that never ship in the deployed app (lightningcss, caniuse-lite) are
  outside CO-7. Geist stays removed.
- **D11 Lockout and results:** django-axes (MIT) is kept for SE-8 lockout and
  configured in Phase 1B. django-celery-results is removed; Celery results
  stay in Valkey.
- **D12 API docs:** `/api/schema/` and `/api/docs/` are public in
  development (`API_DOCS_PUBLIC = True`) and restricted to administrators
  in production.
- **D13 Ratings (G1):** `bookings.Rating`, one per Completed booking,
  vehicle_rating and service_rating 1-5, optional comment. A vehicle's
  average rating is computed from these, never stored.
- **D14 Tax rate (G2):** `TAX_RATE_PERCENT = Decimal("18.00")` is a
  PLACEHOLDER awaiting confirmation.
- **D15 OTP (G3):** `OTP_LIFETIME` = 10 minutes, `OTP_MAX_ATTEMPTS` = 5 (SE-7).
- **D16 Odometer (G4):** no plausibility limit beyond Return.Odometer
  (a return reading may not be lower than the handover reading); AS-4
  assumes staff enter readings honestly.
- **D17 Discounts (G5):** a `pricing.DiscountCode` model managed by admins.
- **D18 Categories:** licence categories are Car and Two-Wheeler (BR-2,
  BR-3); `VehicleCategory` (Hatchback, SUV, ...) is the tariff category.
  Both confirmed.
- **D19 Tokens (SE-9):** access 5 min, refresh 30 min with rotation and
  blacklisting; the frontend refreshes only on user activity.
- **D20 Proposed auth values:** throttle rates, OTP length and resend
  cooldown, mobile format, licence image limits and related behaviours
  (A1-A16) await team approval; password reset is not built.
- **D21 Cookie:** the refresh token lives only in the httpOnly,
  SameSite=Strict `vrms_refresh` cookie (path /api/v1/auth/, Secure except
  in development); login/refresh bodies hold only `{access, user}`; logout
  clears the cookie. The frontend keeps the access token in memory only,
  never in localStorage or sessionStorage.

## Ownership

Nidhi is building every app until she hands over to Rohan. The split and
rule below apply from that handoff.

- **Rohan:** accounts, fleet (except availability), bookings, payments,
  notifications, reports, core (WBS 1.4.1, 1.4.3, 1.4.5).
- **Nidhi:** pricing, `fleet/services/availability.py` plus the search
  API/UI, rentals, maintenance (WBS 1.4.2, 1.4.4).
- **Rule:** only an app's owner edits its `models.py` or migrations;
  anyone else asks the owner.

## Things to never do

- Never invent a UI flow, field, or role that isn't in the SRS or use
  case descriptions without flagging it as a proposed addition first.
- Never silently change a requirement ID, business rule number, or model
  field name that's already used elsewhere in the codebase or docs —
  these are cross-referenced in the traceability matrix.
- Never commit `.env`, credentials, or real payment gateway keys.