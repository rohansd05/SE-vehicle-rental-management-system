# Traceability: Production deployment, PWA and hardening (Module N4)

Maps Exp 7 WBS 1.6.1 (Server and Database Deployment) and 1.6.2 (Application
Deployment), decisions D1 (one Azure VM with Docker Compose) and D8 (a PWA for
OE-2), the operating environment OE-2, OE-3, OE-4 and OE-5, constraint CO-1 and
the security requirements of SRS 5.3 to the files and the tests. SRS:
`docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf`. The operator's guide is
`deploy/README-deploy.md`.

N4 has no use case of its own (Exp 2) and adds no message to the Exp 4
sequence diagrams. It touches two existing steps: the payment authorisation of
sequence 1 ("Book Vehicle"), whose SE-9 password re-check is now throttled
(N4-P3), and the "Send reminders 24 h" node of Exp 5, whose message now names a
doorstep delivery address (R4 follow-up, section 4). No business rule (BR-1 to
BR-16) changes. No model, migration or state transition is added; status
changes and the audit log are untouched.

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`. Test files: `B:core/tests/test_deploy.py` [deploy],
`B:core/tests/test_idor_sweep.py` [idor], `B:bookings/tests/test_api.py` [pay],
`B:rentals/tests/test_api.py` [rentals], `B:notifications/tests/test_reminders.py`
[reminders]; Vitest `F:pwa.test.ts` [pwa] and `F:features/handover/delivery.test.tsx`
[delivery]. Test names are pytest functions or Vitest `it` titles (in quotes).

## 1. Requirements

| Requirement | Implemented in | Tests |
|---|---|---|
| **WBS 1.6.1** Server and database deployment (OE-4, OE-5) | `docker-compose.prod.yml` (PostgreSQL 16 on the `postgres_data` volume, Valkey, health checks); `deploy/README-deploy.md` sections 1 to 5 (VM, Docker on Ubuntu 22.04, `.env`, start), 9 (nightly `pg_dump` with 7-day retention, restore), 10 (stop and start the VM); `deploy/backup.sh` | `test_the_stack_has_every_d1_service`, `test_postgres_valkey_and_django_have_health_checks`, `test_postgres_allows_200_connections_for_the_concurrency_tests` [deploy]; `docker compose config`, `caddy validate` and the image builds (section 6) |
| **WBS 1.6.2** Application deployment | `backend/Dockerfile` (runtime requirements only), `frontend/Dockerfile` (React build into the Caddy image), the `django` service command (`migrate`, `collectstatic`, gunicorn with `deploy/gunicorn.conf.py`), `worker` and `beat`; README sections 6 (`seed_demo`, `seed_demo --reports` once, `createsuperuser`), 7 (scheduled tasks), 8 (update after `git pull`). The user-training half of 1.6.2 (UD-1 to UD-4 manuals) is not part of N4 | `test_worker_and_beat_share_djangos_settings_and_wait_for_healthy_stores` (3 services), `test_beat_uses_the_database_scheduler`, `test_django_health_check_calls_the_health_endpoint` [deploy] |
| **D1** one VM: Postgres 16, Valkey, Django + gunicorn, Celery worker, Celery Beat, Caddy (serves the build, proxies `/api` and `/admin`, automatic HTTPS) | `docker-compose.prod.yml`; `deploy/Caddyfile` (`@django path /api/* /admin /admin/*` → `django:8000`; `/static/*` from the collected files; everything else from `/srv`, the React build); only Caddy publishes ports | `test_the_stack_has_every_d1_service`, `test_only_caddy_is_published_to_the_internet` [deploy] |
| D1 Beat on the database scheduler, so the PeriodicTasks of bookings 0003 and 0005, notifications 0002 and maintenance 0004 run | `beat` command `--scheduler django_celery_beat.schedulers:DatabaseScheduler` (and `CELERY_BEAT_SCHEDULER` in `config/settings/base.py`); the five tasks and their schedules in README section 7 | `test_beat_uses_the_database_scheduler`, `test_celery_beat_reads_the_schedules_the_migrations_register` [deploy]; existing `test_the_reminder_task_is_scheduled_every_5_minutes` [reminders] |
| D1 worker and Beat on Django's settings and `.env`, waiting for healthy Postgres and Valkey | `x-backend` anchor: `env_file: backend/.env`, `DJANGO_SETTINGS_MODULE=config.settings.production`, `depends_on` `service_healthy`; worker and Beat also wait for a healthy `django` (migrations done) | `test_worker_and_beat_share_djangos_settings_and_wait_for_healthy_stores` [deploy] |
| D1 health check: lightweight, no writes, no personal data | the existing `GET /api/v1/health/` (`B:core/views.py` `HealthView`, one `SELECT 1`), called by the `django` health check with the `SITE_HOSTNAME` host | `test_the_health_check_only_reads` [deploy]; existing `test_health_is_public_and_reports_database_agency_and_currency` (the payload is four fixed keys) |
| D1 production settings: DEBUG off, no debug toolbar, static files collected, migrations on deploy | `B:../config/settings/production.py` (`DEBUG = False`, `API_DOCS_PUBLIC = False`); the image installs `requirements.txt` only; `collectstatic` and `migrate` in the `django` command | `test_production_runs_without_debug_or_the_debug_toolbar` [deploy]; `manage.py check --deploy` clean (section 6) |
| SI-3 media only through signed links, never public files | named `media` volume on `django`, `worker`, `beat`; Caddy answers `404` for `/media/*` and never mounts the volume; files leave only through `/api/v1/files/<token>/` (`B:core/files.py`, unchanged) | `test_caddy_never_serves_uploaded_media_as_files` [deploy]; "never answers for /media/rentals/photos/front.jpg (no-cors), so it never caches personal data", "never answers for /api/v1/files/signed-token/ (no-cors), …" [pwa] |
| **D8, OE-2** a PWA installable on Android 9+ and iOS 14+ | `frontend/public/manifest.webmanifest` (name "Veyora - Your Ride, Your Rules", short name, standalone, theme `--primary`, background `--canvas`, icons 192, 512, maskable 512); `frontend/public/icons/` (rendered from `icon.svg`); `frontend/index.html` (manifest link, `theme-color`, `apple-touch-icon` 180, `apple-mobile-web-app-*`); registration in `F:main.tsx` (production builds only); README section 11 | "names Veyora with its tagline and opens standalone", "takes its colours from the design tokens", "has 192 and 512 icons and a maskable one", "is linked from the page, with the tags iOS needs to install it" [pwa] |
| D8 service worker: app shell and static files only, never `/api`, `/admin` or `/media`; offline page | `frontend/public/sw.js` (shell cache: offline page and icons; asset cache: `/assets/`, `/images/`, `/icons/`, cache-first, trimmed to 120 entries; pages from the network, the offline page when that fails; `/api/`, `/admin`, `/media/`, `/static/` never handled); `frontend/public/offline.html` | "never answers for %s (%s), so it never caches personal data" (6 paths), "leaves other origins and other methods alone", "caches the hashed bundles, photos and icons after the first load", "does not cache a failed static response", "loads pages from the network, never from the cache", "shows the offline page when a page cannot be loaded", "precaches only the offline page and the icons, and drops old caches" [pwa] |
| **OE-3** usable from 360 px to 1920 px | The Statutory documents table on the vehicle page (N3) scrolls inside its card instead of widening the page (`F:features/admin/VehiclePage.tsx`); the branch bookings delivery line wraps (no `nowrap`). Static review only (N4-P9) | existing `F:features/admin/fleet.test.tsx`; [delivery] |
| WCAG 2.1 AA (2.4.7 focus visible) on the screens added since 16 Oct | The Rate Vehicle score buttons (R4) hide the radio, so the label now shows the focus outline (`has-focus-visible:outline-*`, `F:features/rating/RatingSection.tsx`). A scan found no unlabelled control and no icon-only button without a name | existing `F:features/rating/rating.test.tsx` (keyboard selection unchanged) |
| PE-6 (page load) / the main bundle under 500 kB | `lazy()` modules for the administration, maintenance and handover screens (`F:features/admin/lazy.ts`, `F:features/maintenance/lazy.ts`, `F:features/handover/lazy.ts`, as R3's `reports/lazy.ts`), one `Suspense` around the shell's outlet (`F:components/layout/AppShell.tsx`). Main chunk 791 kB → 367 kB | the full Vitest suite (every screen test renders through the lazy routes) |
| **OE-4** Ubuntu Server 22.04+, containers, 4 vCPU / 8 GB | README section 1 (image and size); gunicorn workers from the CPU count; deviation for a smaller VM recorded as N4-P1 | — (deployment check) |
| **OE-5** PostgreSQL as the sole system of record | `postgres:16` with `max_connections=200` (dev and production) so R2's two 100-way Reliability-1 tests run instead of skipping | `test_postgres_allows_200_connections_for_the_concurrency_tests` (2 files) [deploy]; `B:bookings/tests/test_concurrency.py` now runs |
| **CO-1** HTTPS with TLS 1.2 or higher everywhere | Caddy's automatic certificate for `{$SITE_HOSTNAME}` (Let's Encrypt), HTTP → HTTPS redirect, TLS 1.2 minimum by default; HSTS from Caddy (React app) and Django (`SECURE_HSTS_SECONDS`); the gateway and notification mocks make no outbound call | `test_production_cookies_are_https_only_and_hsts_is_on` [deploy]; `caddy validate` (section 6) |

## 2. SRS 5.3 security requirements

| Requirement | Implemented in | Tests |
|---|---|---|
| SE-1 encrypted in transit | CO-1 row above; `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, the refresh cookie Secure (D21); `SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST` so Django knows the request was HTTPS and signed links read `https://<host>`. "Encrypted at rest": see N4-P2 | `test_production_cookies_are_https_only_and_hsts_is_on`, `test_production_trusts_caddys_forwarded_headers` [deploy] |
| SE-2 passwords never logged | gunicorn's access log format has no query string and no body (`deploy/gunicorn.conf.py`) | — (configuration) |
| SE-4, SE-11 role-based access on the server; no IDOR | Every detail endpoint with another user's (or another branch's) id answers 404: customer booking endpoints (R1, R2, R4), branch staff and managers on bookings, cash, capture, payment refunds, pay-out, handovers and returns (N1, N2), jobs and vehicle history (N3), technicians on jobs assigned to others, an Administrator on a booking under the wrong customer (UC 12 2a). A guard test fails when a new `<int:pk>` endpoint is not swept | `test_every_id_endpoint_is_swept`, `test_a_customer_gets_404_for_another_customers_booking` (12), `test_branch_users_get_404_for_another_branchs_records` (23), `test_a_technician_gets_404_for_a_job_assigned_to_someone_else` (5), `test_an_administrator_gets_404_for_a_booking_under_the_wrong_customer` (2) [idor]; the per-role permission matrices of each module (unchanged) |
| SE-5 a customer sees only their own bookings, invoices and reports | as SE-4 (the customer half of the sweep) | [idor] |
| SE-8 lockout behind the proxy | `AXES_CLIENT_IP_CALLABLE = "apps.core.audit.client_ip"` (`config/settings/base.py`): the same `NUM_PROXIES` rule as throttling and the audit log, so the recorded address is the one Caddy saw, not Caddy's and not a client-sent entry; the lock stays per account (`AXES_LOCKOUT_PARAMETERS = ["username"]`), so one user's lock never blocks others behind the same address | `test_axes_records_the_address_caddy_saw_not_a_spoofed_one`, `test_a_lockout_from_one_address_never_locks_other_users_there` [deploy]; existing `test_lockout.py` |
| SE-9 re-authentication before a payment or refund, throttled | `B:payments/reauth.py` `require_password()`: after `LOGIN_FAILURE_LIMIT` (5) wrong passwords in a row the re-check answers 429 for `LOGIN_LOCKOUT_DURATION` (15 min) without checking the password; a right one resets the count; per user (N4-P3). Covers every money endpoint that calls it (pay, cash, cancel, modify, extend, due, capture, refund, approve, reject, pay-out, and an Administrator cancelling a blacklisted customer's booking) | `test_wrong_passwords_in_a_row_stop_the_re_check_for_15_minutes`, `test_a_right_password_resets_the_wrong_password_count`, `test_another_users_wrong_passwords_do_not_throttle_mine` [pay]; existing `test_a_wrong_password_moves_no_money_and_is_audited` (7 endpoints) |
| SE-11 OWASP: CSRF, XSS, clickjacking, sniffing | `CSRF_TRUSTED_ORIGINS` from the environment; CORS closed (N4-P4); Caddy headers: HSTS, `X-Content-Type-Options`, `X-Frame-Options DENY`, `Referrer-Policy same-origin`, `Permissions-Policy`, and a Content Security Policy on the React app (`script-src 'self'`, `frame-ancestors 'none'`, no other origin); Django: `X_FRAME_OPTIONS`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY` | `test_production_hosts_and_csrf_origins_come_from_the_environment`, `test_production_cookies_are_https_only_and_hsts_is_on` [deploy]; `caddy validate` |

## 3. Settings read from the environment

Every setting that is read from the environment is in `backend/.env.example`
with a safe placeholder, and listed with its production value in README
section 4. N4 adds only `SITE_HOSTNAME`, `POSTGRES_DB`, `POSTGRES_USER` and
`POSTGRES_PASSWORD` (read by Caddy, the health check and the postgres
container). The modules R1 to R4 and N1 to N3 added one variable,
`PAYMENT_WEBHOOK_SECRET` (R1, SI-1.4), already in the example.
`REFUND_AUTO_APPROVAL_LIMIT` and the other business rules are constants in
`config/settings/business_rules.py` with no environment lookup, so they need
no entry. No secret is committed: the example holds placeholders only, and
`backend/.dockerignore` keeps `.env` out of the image.

## 4. R4 follow-ups (Book.Deliver.Location)

| Item | Implemented in | Tests |
|---|---|---|
| The branch bookings list shows a delivered booking's address | `"delivery_address"` in `BranchBookingSerializer.Meta.fields` (`B:rentals/serializers.py`); `docs/api/openapi.yaml` and `F:api/schema.d.ts` regenerated; "Doorstep delivery: <address>" in the row (`F:features/handover/CollectionsPage.tsx`) | `test_branch_bookings_show_the_doorstep_delivery_address` [rentals]; "shows the delivery address on the delivered booking only" [delivery] |
| Notify.Remind no longer says "collect at the branch" for a delivered booking | new template versions `("pickup_reminder", 2)` and `("pickup_reminder_sms", 2)` (`B:bookings/notification_templates.py`; version 1 unchanged); `{collection}` from `bookings.services.collection_details()`, the text the confirmation already used (moved out of `notify_booking_confirmed()`, same output); `B:notifications/services.py` `send_pickup_reminders()` sends version 2 | `test_the_reminder_is_template_version_2`, `test_a_delivered_booking_is_reminded_of_its_delivery_address` [reminders]; existing `test_a_booking_collected_within_24_hours_is_reminded_by_e_mail_and_sms` (branch, time, code and documents still present) |

## 5. Seed data

README section 6 runs `migrate` (automatic), `seed_demo`, then
`seed_demo --reports` exactly once, and explains that the append-only rows mean
the database can only be started over by deleting the Postgres volume.

So the R4 follow-ups can be demonstrated, `seed_demo` now adds (in
`B:rentals/seed.py`, `seed_demo_handover_data()`) a second demo car at Andheri,
MH02DH3002, booked by handover@vrms.test (password `Demo@1234`) for a week with
the "Doorstep delivery" add-on to 21 Demo Lane, Andheri (W), 400053, collected
24 hours and 10 minutes after the seed runs, pickup code 975310. It goes through
the booking state machine and the mock gateway like the handover booking, is
listed in Branch bookings, "Upcoming collections", with its delivery address,
and Celery Beat sends its version-2 reminder about ten minutes after seeding.
`--reset` removes it with the handover car. The other demo accounts and the
maintenance jobs 1 to 3 are unchanged.

| Test | File |
|---|---|
| `test_a_delivered_booking_is_upcoming_with_its_address_and_gets_its_reminder` | `B:rentals/tests/test_seed.py` |
| `test_seed_creates_the_expected_demo_data`, `test_seed_twice_changes_nothing`, `test_reset_reloads_the_same_data` (35 vehicles, 42 documents, 140 photos, 57 audited creations) | `B:core/tests/test_seed_demo.py` |
| `test_the_demo_vehicles_show_in_an_andheri_search` (unchanged: the week-long booking keeps the car out of the search) | `B:bookings/tests/test_seed.py` |

## 6. Checks run for this module

`docker compose -f docker-compose.prod.yml config --quiet` (valid);
`caddy validate` on `deploy/Caddyfile` (valid configuration);
`manage.py check --deploy` with the production settings (no issues; W008 and
W021 silenced on purpose, see `production.py`); the production images built
with `docker compose -f docker-compose.prod.yml build`. A browser pass of the
whole system is planned at the end (team decision), so the PWA install and the
360/1920 px layouts were not checked on devices.

## 7. Proposed items (awaiting team approval)

| # | Item | Proposal |
|---|---|---|
| N4-P1 | VM size (OE-4) | OE-4 asks for 4 vCPU and 8 GB. If the Azure credit forces a smaller size (for example `Standard_B2s`, 2 vCPU and 4 GB), that is a deviation from OE-4, accepted for the course demo only; gunicorn then runs 5 workers instead of 9. Record the size actually used here. |
| N4-P2 | SE-1 "documents encrypted at rest" | The database and media volumes live on the VM's managed disk, which Azure encrypts at rest by default (platform-managed keys). No application-level encryption of the files is added. |
| N4-P3 | Throttling the SE-9 re-check | The SE-8 numbers are reused (`LOGIN_FAILURE_LIMIT` = 5 wrong passwords in a row, `LOGIN_LOCKOUT_DURATION` = 15 minutes), counted per user in the shared cache, answered with 429 before the password is checked; a right password resets the count. The SRS sets no value. |
| N4-P4 | CORS | No CORS package and no allowed origins: the browser sees one origin behind Caddy (D1), so Django sends no `Access-Control-Allow-Origin` and every other origin is refused. A `CORS_ALLOWED_ORIGINS` setting would only be needed for a second front end. `CSRF_TRUSTED_ORIGINS` is read from the environment. |
| N4-P5 | Offline behaviour of the PWA | Nothing personal is ever cached, so offline the app shows its offline page instead of stale bookings; `index.html` and the manifest are not cached, so a deploy reaches installed apps on their next start. |
| N4-P6 | The offline page's text | New copy (B1 freezes existing strings only): "You are offline", "Veyora needs an internet connection to show vehicles, bookings and payments. Check your connection, then try again.", "Try again". |
| N4-P7 | Backups | Nightly at 02:15 UTC, `pg_dump` plus a tar of the media volume (without the media a restored database would point at missing photos), 7 days, on the same VM. Copying them off the VM (for example to Azure Blob Storage) is not built. |
| N4-P8 | Content Security Policy scope | Only on the React app. The Django admin and Swagger UI (administrators only, D12) keep Django's own headers, because Swagger UI uses inline scripts. |
| N4-P9 | OE-3 and WCAG check | A static review (scans for unlabelled controls, icon buttons without a name, tables that cannot scroll, fixed widths) fixed the two gaps found; the measured check at 360 px and 1920 px is the planned manual pass. |
| N4-P10 | Demo accounts on a public server | The `@vrms.test` accounts and `Demo@1234` are public in `README.md`; they stay for the course demo, and README-deploy says to change their passwords if the site stays up afterwards. |

## 8. Not built

- An off-VM copy of the backups (N4-P7) and monitoring or alerting.
- Push notifications from the PWA (the SRS lists push as a channel of the
  notification service; the mock records it).
- The UD-1 to UD-4 manuals (WBS 1.6.2's user-training half).
- Flushing expired JWT blacklist rows (`flushexpiredtokens`); the table grows
  slowly and can be flushed by hand.
