# VRMS — Architecture and Scope Decisions

These decisions were settled before Phase 0 and supersede section 7 ("Open
decisions") of `docs/VRMS_Handoff.md`. CLAUDE.md carries a one-line summary
of each. The SRS is `docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf`.

---

## D1 — Deployment

**Decision.** One Azure VM running Ubuntu, with docker-compose running
PostgreSQL 16, Valkey, Django + gunicorn, a Celery worker, Celery Beat and
Caddy. Caddy serves the React production build, reverse-proxies `/api` and
`/admin` to gunicorn, and obtains and renews HTTPS certificates
automatically.

**Rationale.** OE-4 requires Ubuntu Server 22.04 LTS or later with the
application server and database deployed as containers on a 4 vCPU / 8 GB
host. A single VM meets that literally and avoids the free-tier limits of
PaaS offerings, where a Celery worker and Beat process are rarely free. With
Caddy in front, the browser sees one origin, so no CORS configuration is
needed. Caddy's automatic TLS satisfies CO-1 (HTTPS with TLS 1.2 or higher)
without manual certificate handling. The production settings
(`config.settings.production`) trust Caddy's `X-Forwarded-Proto` header,
use secure cookies and HSTS, and read `ALLOWED_HOSTS` and
`CSRF_TRUSTED_ORIGINS` from the environment. The production compose file and
Caddyfile are built in the deployment phase (WBS 1.6.1).

## D2 — CO-7 amendment and Valkey

**Decision.** CO-7 is amended to read: *Only third-party components under
the MIT, Apache 2.0 or BSD licences shall be used. LGPL libraries used
unmodified as dependencies (psycopg) and HPND (Pillow) are permitted.*
Valkey (BSD) replaces the Redis server. The `redis` Python client (MIT) is
still used, because Valkey speaks the Redis protocol.

**Rationale.** Every mainstream PostgreSQL driver for Django is LGPL.
Linking an unmodified LGPL library as a dependency places no obligation on
the VRMS source, so it doesn't undermine CO-7's aim of keeping the code
freely distributable. Pillow's HPND licence is a permissive,
MIT-style licence; it simply isn't one of the three names listed. Current
Redis server releases are under RSALv2/SSPLv1/AGPLv3, which fail CO-7.
Valkey is the Linux Foundation fork of Redis 7.2 under BSD-3-Clause and is a
drop-in replacement as broker and result backend for Celery.

## D3 — Local development environment

**Decision.** PostgreSQL and Valkey run in Docker (`docker-compose.yml` at
the repository root). Django runs natively in a Windows venv
(`backend\venv`, Python 3.12). reportlab replaces weasyprint for PDF
generation. python-magic is removed; uploads are validated by file
extension, size limit and Pillow `Image.verify()`.

**Rationale.** Both developers work on Windows. weasyprint needs GTK/Pango
and python-magic needs libmagic, and both commonly fail to install there.
reportlab (BSD) is pure Python with C speed-ups shipped as wheels, and it
produces invoices, rental agreements and condition reports without system
libraries. Running only the stateful services in Docker keeps debugging and
hot reload native while matching the production PostgreSQL major version.
Pillow's `verify()` catches truncated or non-image files that an extension
check alone would accept. The Docker PostgreSQL host port can be overridden
with `POSTGRES_HOST_PORT` in a root `.env` when 5432 is already taken, for
example by a native Windows PostgreSQL service.

## D4 — Password hashing

**Decision.** argon2-cffi is removed. The first `PASSWORD_HASHERS` entry is
`apps.accounts.hashers.BCryptSHA256Rounds12PasswordHasher`, a
`BCryptSHA256PasswordHasher` subclass with `rounds = 12`.

**Rationale.** SE-2 requires salted bcrypt hashes with a work factor of at
least 12. Pinning `rounds` in our own subclass means a Django upgrade can
never silently change the work factor, and a unit test asserts it. The
SHA-256 pre-hash avoids bcrypt's 72-byte input truncation. Keeping Argon2
installed would have invited it being configured first, which would breach
the letter of SE-2.

## D5 — Configuration library

**Decision.** django-environ is the only configuration library.
python-decouple and dj-database-url are removed.

**Rationale.** The three libraries overlap: django-environ already reads
`.env` files and parses `DATABASE_URL` and lists. One library means one way
to read a variable and one place (`backend/.env.example`) that documents all
of them. `backend/.env` takes precedence over variables already set in the
OS environment, so a machine-wide `SECRET_KEY` or `DATABASE_URL` left by
another project cannot leak in.

## D6 — Online payment channels

**Decision.** UPI, net banking and wallet are channels of `OnlinePayment`,
recorded in a `channel` field added in Phase 1. `upi_id` is kept. There is
no separate wallet class.

**Rationale.** The Exp 3 class diagram has exactly three `Payment`
implementations: `CardPayment`, `CashPayment` and `OnlinePayment`. CLAUDE.md
forbids renaming or dropping classes, and adding a wallet class would put
the code out of step with the submitted diagram. A `channel` field covers
the payment methods the SRS lists (`Pay.Method`) while keeping the class
model intact.

## D7 — Currency and agency name

**Decision.** The currency is INR. The agency name comes only from the
`AGENCY_NAME` setting, whose default is the placeholder `"[Agency Name]"`.
The name is never hardcoded in the backend or the frontend; the frontend
reads it, with the currency, from `GET /api/v1/health/`.

**Rationale.** The SRS describes a single, unnamed agency and puts
multi-currency out of scope. A single source for the name lets the
deployment be branded without code changes and keeps screenshots, invoices
and the UI consistent. Exposing it through the public health endpoint means
the home page can show it before anyone signs in.

## D8 — Mobile application

**Decision.** A responsive Progressive Web App meets OE-2 for Release 1.0.

**Rationale.** OE-2 asks for a mobile application on Android 9+ and iOS 14+.
Within the delivery window, a PWA served from the same React code base
installs to the home screen on both platforms and shares one API (CO-4).
OE-3 already requires the web client to work from 360 px to 1920 px. The
final report will state that the PWA fulfils OE-2 for this release. The PWA
manifest and service worker are marked as a TODO in the frontend.

## D9 — Scope and schedule

**Decision.** Release 1.0 contains every feature in the SRS and Experiments
1–7, deployed by 12 Oct 2026, built by two developers in parallel.

**Rationale.** The project's end goal is a fully deployed website, not a
single vertical slice. Work is split along the Exp 7 WBS development
packages (1.4.1–1.4.5); CLAUDE.md records the ownership of each Django app
so the two developers rarely edit the same models or migrations. The
`pricing` app is separate from `fleet` so the 100% coverage target on the
charge engine (BR-6, BR-7, BR-10 to BR-12) can be measured on one package.

## D10 — CO-7 amended further

**Decision.** In addition to D2:

- ISC (MIT-equivalent) is permitted.
- MPL-2.0 and LGPL are permitted for dependencies used unmodified.
- Build-time tools that never ship in the deployed app (for example
  lightningcss and caniuse-lite) are outside CO-7.
- The Geist font stays removed.

**Rationale.** The Phase 0 licence scan found permissive or weak-copyleft
licences in packages we cannot reasonably avoid. ISC is the licence of
`lucide-react` (shadcn/ui's icon set) and of the d3 modules under Recharts,
and is functionally identical to MIT. MPL-2.0 (certifi, pathspec) and LGPL
(python-crontab) are file-level or library-level copyleft: using them
unmodified as dependencies places no obligation on the VRMS source, which is
the same reasoning D2 applied to psycopg. lightningcss and caniuse-lite run
only while Tailwind builds the CSS and are not part of the deployed
artefact, so they never reach a user. Geist (SIL OFL 1.1) is a font asset
that would ship to the browser, so it stays out.

Still outside the amended list, for the team to note: `typing_extensions`
and `aiohappyeyeballs` (PSF-2.0, runtime) and `tslib` (0BSD, runtime; a
BSD-family licence).

## D11 — django-axes kept, django-celery-results removed

**Decision.** django-axes (MIT) stays in the requirements for the SE-8
account lockout; it is configured in Phase 1B. django-celery-results is
removed. Celery task results stay in Valkey (`CELERY_RESULT_BACKEND =
REDIS_URL`).

**Rationale.** SE-8 requires locking an account for 15 minutes after five
consecutive failed logins. django-axes implements exactly that, records the
attempts in the database, and is MIT-licensed. django-celery-results would
only duplicate a result backend we already have in Valkey and was never
enabled, so it is dead weight.

## D12 — API documentation access

**Decision.** The OpenAPI schema (`/api/schema/`) and Swagger UI
(`/api/docs/`) are public in development and restricted to administrators
in production. The switch is the `API_DOCS_PUBLIC` setting: `True` in
`config.settings.development`, `False` in base, production and test. When
restricted, the views accept a Django admin session or a JWT, and require
`IsAdminUser`.

**Rationale.** In development the docs are the main tool for the frontend
developer. In production the schema lists every endpoint and parameter,
which is useful reconnaissance for an attacker (SE-11, OWASP Top Ten:
broken access control). Session authentication on these two views lets an
administrator who is signed in to `/admin/` open the docs in a browser,
which a JWT-only view would not allow.

## D13 — Ratings (closes G1)

**Decision.** A `bookings.Rating` model: one per Completed booking
(OneToOne to Booking, PROTECT), with `vehicle_rating` and `service_rating`
each 1–5 (database check constraints) and an optional comment. A vehicle's
average rating is computed from its ratings when needed, never stored.
"Only for Completed bookings" is enforced by the rating service.

**Rationale.** Search.Detail displays and Search.Filter filters on an
average customer rating, but the SRS defines no requirement that captures
one. Tying a rating to a completed booking means only real renters rate,
and at most once. Computing the average avoids a denormalised column that
could drift (CO-5).

## D14 — Tax rate (closes G2, placeholder)

**Decision.** `TAX_RATE_PERCENT = Decimal("18.00")` in
`config/settings/business_rules.py`. **This is a placeholder awaiting
confirmation** by the team; the comment next to the setting says so.

**Rationale.** BR-6 adds "taxes" and Pay.Invoice requires the taxes applied
on every invoice, but the SRS gives no rate. 18% is the GST rate commonly
quoted for vehicle rental in India; it must be confirmed before go-live.
Keeping it a single setting means the confirmation changes one line.

## D15 — OTP lifetime and attempts (closes G3)

**Decision.** `OTP_LIFETIME = timedelta(minutes=10)` and
`OTP_MAX_ATTEMPTS = 5` (SE-7).

**Rationale.** SE-7 requires OTP verification but gives no lifetime or
attempt limit. Ten minutes covers SMS delays (CI-5 allows 30 seconds for
delivery) without leaving a code usable for long. Five attempts against a
six-digit code gives an attacker a 1-in-200,000 chance per code, and
matches the five-failure threshold of SE-8.

## D16 — Odometer plausibility (closes G4)

**Decision.** No plausibility limit beyond Return.Odometer itself: a
return reading lower than the handover reading is rejected.

**Rationale.** Return.Odometer mentions "the configured plausibility limit"
but never configures one, and AS-4 assumes staff enter readings honestly.
The supervisor-override fields on ConditionReport stay available if a limit
is introduced later.

## D17 — Discount codes (closes G5)

**Decision.** A `pricing.DiscountCode` model managed by administrators:
code (unique, case-insensitive), Percent or Fixed type with a Decimal value
(a Percent value must be between 0 and 100), validity window, active flag,
optional usage limit and a usage count. A booking records the code applied
and the discount amount.

**Rationale.** BR-6 subtracts "any discount" but the SRS defines no source
for one. Admin-managed codes are the smallest model that gives BR-6 a
concrete discount, are auditable, and can be switched off.

## D18 — Licence categories and vehicle categories

**Decision.** Licence categories are Car and Two-Wheeler (BR-2, BR-3).
`VehicleCategory` (Hatchback, Sedan, SUV, Scooter, Motorcycle, ...) is the
tariff category. Both confirmed by the team.

**Rationale.** BR-2 and BR-3 distinguish only two-wheelers and cars, so the
BR-3 endorsement check compares a licence category with
`vehicle.category.vehicle_type`. Tariffs, search filters and reports work
on the finer `VehicleCategory`.

## D19 — Session and token lifetimes (SE-9)

**Decision.** SimpleJWT access tokens live 5 minutes and refresh tokens 30
minutes. Refresh tokens rotate: each refresh returns a new pair and the
used refresh token is blacklisted. Sign-out blacklists the refresh token;
a password change blacklists all of the user's refresh tokens. A disabled
account is refused on every request and on refresh.

**Rationale.** SE-9 requires a session to expire after 30 minutes of
inactivity. With JWTs the refresh token is the session: the client
exchanges it whenever the user is active, and each exchange starts a fresh
30-minute window. If the user does nothing for 30 minutes, the last
refresh token expires and they must sign in again. A client may use an
access token for up to 5 minutes without refreshing, so the effective idle
limit is 25–30 minutes, never longer than SE-9 allows. The short access
lifetime also limits how long a stolen access token is useful, and lets
Fleet.Users ("disabling an account shall immediately end that user's
sessions") take effect within one request. **Frontend obligation:** refresh
only in response to user activity, never on a background timer, or the
session would never go idle. The second half of SE-9 (re-authentication
before a payment or refund) is enforced in the payment phase.

## D20 — Proposed authentication values (awaiting team approval)

The SRS does not specify these. They are implemented as listed and stay
**Proposed** until the team confirms or changes them.

| # | Item | Proposal |
|---|---|---|
| A1 | Throttle rates | register 10/hour per IP; sign-in 10/minute per IP; verify OTP 10/minute; resend OTP 5/hour; refresh and sign-out 30/minute; password change 5/hour per user; profile 30/minute; licence submission 10/hour. SE-8 lockout (per account) is separate. |
| A2 | OTP code length | 6 digits (`OTP_CODE_LENGTH`) |
| A3 | OTP resend cooldown | 60 seconds (`OTP_RESEND_COOLDOWN`), keyed by the e-mail typed, so it applies whether or not the account exists |
| A4 | Mobile number format | 10–15 digits with an optional leading `+` |
| A5 | Licence image types and size | JPG, JPEG, PNG (HI-1 speaks only of camera images, so no PDF); at most 5 MB each (`LICENCE_IMAGE_MAX_BYTES`) |
| A6 | Both licence images required | Appendix A lists front and back image without parentheses, which the data dictionary uses for optional items |
| A7 | Password reset by OTP | **Not built**: the SRS has no password-reset requirement. Proposal: OTP to the registered mobile, then a new password, then every session ends |
| A8 | Duplicate e-mail at registration | Answers 400 "already exists", which shows that the address is registered. SE-8 forbids that only for failed sign-in. Alternative: always answer 201 and e-mail the owner instead |
| A9 | Sign-in before verification | The same generic 401 as a wrong password; the UI takes a new registrant straight to the verification step |
| A10 | Where the mobile-change OTP goes | To the new number, proving possession of it (SE-7); the change applies only after the code is confirmed |
| A11 | Password change ends every session | Including the current one; the user signs in again |
| A12 | Licence verification queue | Not branch-scoped: licences belong to customers, not branches, so all branch staff and administrators see every pending licence |
| A13 | Licence resubmission | Allowed in any state (for example after a renewal); the licence returns to Pending Verification |
| A14 | Lockout response | HTTP 403 with `code: account_locked`; the same response for unknown accounts |
| A15 | Lockout e-mail | Sent once per lock, even if more attempts arrive during it |
| A16 | Licence numbers | Stored in upper case so the uniqueness check ignores case |

## D21 — Refresh token in an httpOnly cookie; access token in memory

**Decision.**

- The refresh token moves out of response bodies into the cookie
  `vrms_refresh`: httpOnly, SameSite=Strict, Path=/api/v1/auth/, Max-Age
  30 minutes, and Secure everywhere except development (plain
  http://localhost).
- `auth/login/` and `auth/refresh/` set the cookie and return only
  `{access, user}`. `auth/refresh/` takes no body; it reads the cookie.
- `auth/logout/` blacklists the cookie's token and always clears the
  cookie; `auth/password/change/` clears it too (every token was already
  blacklisted, A11).
- Rotation and blacklisting are unchanged (D19).
- The frontend keeps the access token in memory only; it never touches
  localStorage or sessionStorage.
- `auth/logout/` no longer needs an access token (AllowAny, no
  authentication). After 30 idle minutes the access token has expired, but
  the browser must still be able to drop a cookie that page scripts cannot
  read or delete.

**Rationale.** A token in a response body ends up in JavaScript memory and
often in web storage, where any XSS bug can read it. An httpOnly cookie
cannot be read by scripts at all. SameSite=Strict means the browser never
attaches it to a request started by another site, which is the CSRF
defence for the two endpoints that accept it (refresh and logout); the
narrow path means it is never sent to the rest of the API, which still
authenticates by the short-lived `Authorization: Bearer` access token.
Because the page is served same-origin behind Caddy (D1) and through the
Vite proxy in development, no CORS or cross-site cookie settings are
needed. Keeping the access token in memory means a reload loses it; the
frontend restores the session by calling `auth/refresh/` on page load,
which the cookie makes possible.

**Known limitation.** Two tabs that refresh at the same instant race on
rotation: the second presents a just-blacklisted token and is signed out.
Coordinating tabs (for example with a BroadcastChannel) is proposed as F1
below.

## Phase 1C frontend: proposed items (awaiting team approval)

The SRS does not settle these; the frontend implements them as listed.

| # | Item | Proposal |
|---|---|---|
| F1 | Several tabs open at once | Not coordinated yet: two tabs refreshing at the same instant can sign one of them out (D21). Proposal: share refreshes between tabs with a BroadcastChannel. |
| F2 | When the access token is refreshed | One minute before it expires, and only if the user did something since the last refresh (pointer, keyboard, touch, or returning to the tab). Coming back after the token lapsed refreshes at once. |
| F3 | OTP error wording | The server answers every failure the same way. The verify screen knows when the code was sent and how many tries were made on this screen, so it says "wrong (n tries left)", "expired" or "too many attempts". After a page reload it falls back to the server's generic message. |
| F4 | Licence review screen | There is no `GET licences/{id}/`; the review screen uses the licence passed from the queue, or finds it in the queue's first page (20 oldest). Proposal: add the detail endpoint. |
| F5 | Mobile-change resend | A visible 60-second countdown on the client, matching A3; the server applies only the profile throttle (A1) to mobile-change codes. |
| F6 | Accent colour | `oklch(0.47 0.12 240)` in light mode and `oklch(0.76 0.11 235)` in dark mode, as the `--brand` token; light and dark follow the OS. |
| F7 | Help link (UI-2) | Present on every screen; it leads to a short help page until the online help system (UD-1) is built. |
| F8 | Planned features in the menu | Shown with a "Soon" label and an honest "not available yet" page; no sample data. |
| F9 | Registration fields | Date of birth (BR-2) and an emergency contact (SA-4) are asked at registration, because the backend requires them. |

---

## Third-party packages and licences

Checked against CO-7 as amended by D2 and D10. Versions are the pins in
`backend/requirements*.txt` and `frontend/package.json`.

### Backend runtime (`backend/requirements.txt`)

| Package | Version | Licence | CO-7 |
|---|---|---|---|
| Django | 5.2.17 | BSD-3-Clause | OK |
| djangorestframework | 3.16.0 | BSD-3-Clause | OK |
| django-filter | 25.1 | BSD-3-Clause | OK |
| djangorestframework-simplejwt | 5.5.0 | MIT | OK |
| drf-spectacular | 0.28.0 | BSD-3-Clause | OK |
| drf-spectacular-sidecar | 2025.6.1 | BSD-3-Clause (bundles Swagger UI, Apache-2.0, and ReDoc, MIT) | OK |
| psycopg[binary] | 3.2.9 | LGPL-3.0 (wheel bundles libpq, PostgreSQL Licence) | OK under D2 |
| celery | 5.5.2 | BSD-3-Clause | OK |
| redis (client) | 5.2.1 | MIT | OK |
| django-celery-beat | 2.8.1 | BSD-3-Clause | OK |
| bcrypt | 4.2.1 | Apache-2.0 | OK |
| django-axes | 7.0.2 | MIT | OK (SE-8 lockout, configured in Phase 1B; D11) |
| Pillow | 11.1.0 | MIT-CMU (HPND) | OK under D2 |
| reportlab | 4.4.10 | BSD | OK |
| qrcode | 8.0 | BSD | OK |
| razorpay | 1.4.2 | MIT | OK |
| twilio | 9.4.1 | MIT | OK |
| requests | 2.32.5 | Apache-2.0 | OK |
| django-environ | 0.12.0 | MIT | OK |
| gunicorn | 23.0.0 | MIT | OK |
| whitenoise | 6.8.2 | MIT | OK |

### Backend development (`backend/requirements-dev.txt`)

| Package | Version | Licence | CO-7 |
|---|---|---|---|
| pytest | 8.3.4 | MIT | OK |
| pytest-django | 4.9.0 | BSD-3-Clause | OK |
| pytest-cov | 6.0.0 | MIT | OK |
| pytest-xdist | 3.6.1 | MIT | OK |
| factory-boy | 3.3.1 | MIT | OK |
| Faker | 33.3.0 | MIT | OK |
| freezegun | 1.5.1 | Apache-2.0 | OK |
| model-bakery | 1.20.1 | Apache-2.0 | OK |
| ruff | 0.9.2 | MIT | OK |
| black | 24.10.0 | MIT | OK |
| django-debug-toolbar | 5.2.0 | BSD-3-Clause | OK |
| django-extensions | 3.2.3 | MIT | OK |
| ipython | 8.31.0 | BSD-3-Clause | OK |

### Backend transitive dependencies outside MIT / Apache / BSD

Every other transitive dependency is MIT, BSD or Apache-2.0.

| Package | Licence | Pulled in by | Scope | CO-7 |
|---|---|---|---|---|
| certifi | MPL-2.0 | requests (razorpay, twilio) | runtime | OK under D10 (unmodified) |
| python-crontab | LGPL-3.0 | django-celery-beat | runtime | OK under D10 (unmodified) |
| pathspec | MPL-2.0 | black | development only | OK under D10 |
| typing_extensions | PSF-2.0 | many | runtime | **Not covered** — noted in D10 |
| aiohappyeyeballs | PSF-2.0 | aiohttp (twilio) | runtime | **Not covered** — noted in D10 |

### Removed

| Package | Licence | Reason |
|---|---|---|
| argon2-cffi | MIT | D4 — bcrypt only (SE-2) |
| weasyprint | BSD-3-Clause | D3 — needs GTK/Pango on Windows; replaced by reportlab |
| python-magic | MIT | D3 — needs libmagic; uploads validated by extension, size and Pillow |
| python-decouple | MIT | D5 — django-environ only |
| dj-database-url | BSD-3-Clause | D5 — django-environ parses `DATABASE_URL` |
| django-cors-headers | MIT | D1 — same-origin behind Caddy; the Vite dev server proxies `/api` and `/admin` |
| django-celery-results | BSD-3-Clause | D11 — never enabled; Celery results stay in Valkey |

### Frontend runtime (`frontend/package.json` dependencies)

React is pinned to 18 because current Vite templates default to React 19
(handoff tech stack: React 18).

| Package | Version | Licence | CO-7 |
|---|---|---|---|
| react / react-dom | 18.3.1 | MIT | OK |
| react-is | 18.3.1 | MIT | OK (peer dependency of recharts) |
| react-router-dom | 7.18.4 | MIT | OK — **addition**: not in the handoff stack, needed for client-side routing |
| @tanstack/react-query | 5.104.1 | MIT | OK |
| react-hook-form | 7.89.0 | MIT | OK |
| zod | 4.6.5 | MIT | OK |
| recharts | 3.10.1 | MIT | OK |
| radix-ui | 1.6.7 | MIT | OK (shadcn/ui primitives) |
| class-variance-authority | 0.7.1 | Apache-2.0 | OK (shadcn/ui) |
| cn | 0.4.0 | MIT | OK (shadcn/ui; shadcn's replacement for clsx + tailwind-merge) |
| tw-animate-css | 1.4.0 | MIT | OK (shadcn/ui; CSS only) |
| lucide-react | 1.52.0 | ISC | OK under D10 (shadcn/ui's icon set) |

### Frontend development (`frontend/package.json` devDependencies)

| Package | Version | Licence | CO-7 |
|---|---|---|---|
| vite | 8.3.2 | MIT | OK |
| @vitejs/plugin-react | 6.1.2 | MIT | OK |
| typescript | 6.0.3 | Apache-2.0 | OK |
| tailwindcss / @tailwindcss/vite | 4.3.3 | MIT | OK |
| shadcn (CLI; also provides `shadcn/tailwind.css`) | 4.21.2 | MIT | OK |
| vitest | 5.0.3 | MIT | OK |
| @testing-library/react | 16.3.3 | MIT | OK |
| @testing-library/dom | 10.4.2 | MIT | OK |
| @testing-library/jest-dom | 7.0.1 | MIT | OK |
| jsdom | 30.1.2 | MIT | OK |
| oxlint | 1.87.0 | MIT | OK (the Vite template's linter; `npm run lint`) |
| @types/react, @types/react-dom, @types/node | 18.3.31, 18.3.7, 22.20.5 | MIT | OK |

Removed: `@fontsource-variable/geist` (added by `shadcn init`). The Geist font
is under the SIL Open Font Licence 1.1, which fails CO-7; the UI uses the
system font stack instead.

### Frontend transitive dependencies outside MIT / Apache / BSD

| Licence | Packages | Scope | CO-7 |
|---|---|---|---|
| ISC | d3-* and internmap (recharts), victory-vendor (MIT AND ISC) | runtime (shipped to the browser) | OK under D10 |
| 0BSD | tslib | runtime | **Not covered** — BSD-family; noted in D10 |
| ISC, BlueOak-1.0.0, MIT-0, CC0-1.0 | build and test tooling (semver, lru-cache, minimatch, ...) | development only | Outside CO-7 under D10 (never shipped) |
| MPL-2.0 | lightningcss (required by Tailwind CSS 4) | build only | Outside CO-7 under D10 |
| CC-BY-4.0 | caniuse-lite (browser-support data) | build only | Outside CO-7 under D10 |

D10 names build-time tools explicitly; this table reads it as covering all
development-only tooling (test runners, linters), which never ships either.

`npm audit` reports a high-severity advisory in `braces` (via fast-glob),
reachable only through the shadcn CLI, for which no fixed version exists.
`npm audit --omit=dev` reports 0 vulnerabilities.

### Services (Docker images)

| Image | Licence | CO-7 |
|---|---|---|
| postgres:16 | PostgreSQL Licence (permissive, BSD/MIT-style) | OK — the SRS itself names PostgreSQL as the system of record |
| valkey/valkey:8 | BSD-3-Clause | OK |
| caddy (D1, not yet built) | Apache-2.0 | OK |
