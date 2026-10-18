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
`AGENCY_NAME` setting, whose default is `"Veyora"`, with the tagline "Your
Ride, Your Rules" (D24).
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

**Built in Module N4 (19 Oct 2026):** `frontend/public/manifest.webmanifest`,
`frontend/public/icons/`, `frontend/public/sw.js` (app shell and static files
only, never an API response) and `frontend/public/offline.html`; traceability
in `docs/traceability-deploy.md`.

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

## D16 — Odometer plausibility (closes G4; amended 18 Oct 2026, Module N3)

**Decision (as amended).** A return reading lower than the handover reading
is rejected (Return.Odometer, UC 8 extension 2a). In addition, a distance
above the plausibility limit, `ODOMETER_PLAUSIBILITY_KM_PER_DAY` (default
1,000 km) for every started day the vehicle was out, needs a supervisor
override with a recorded reason: a Branch Manager of the branch or an
Administrator signs in on the branch device and gives the reason, which is
stored on the return condition report (`odometer_override_by`,
`odometer_override_reason`) and audited ("Odometer Override Approved",
with the supervisor as actor). This was proposed in Module N2 as N2-P7
(`docs/traceability-return.md`, section 9; model-mapping P31) and built in
`rentals/settlement.py` `plausibility_limit()` and `rentals/services.py`
`_odometer_override()`.

**Rationale.** Return.Odometer itself asks for "a supervisor override with
a recorded reason if the distance travelled exceeds the configured
plausibility limit"; the original D16 left that limit unconfigured. A
per-day figure scales with the rental's length, and one setting in
`config/settings/business_rules.py` lets the team change it. The value is
still proposed; the SRS gives none.

*Originally (before N3):* no plausibility limit beyond Return.Odometer
itself, since AS-4 assumes staff enter readings honestly; the supervisor
override fields on ConditionReport were kept for a later limit.

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

## D22 — Self-hosted Fontsource fonts (SIL OFL 1.1), no CDN

**Decision.** CO-7 is amended further: fonts under the SIL Open Font
Licence 1.1 are permitted when used unmodified and self-hosted through
Fontsource npm packages. The frontend uses three (type system C, chosen
12 Oct 2026; Fraunces and Archivo, used briefly on 11 Oct, were removed):

| Package | Font | Licence | Role |
|---|---|---|---|
| `@fontsource-variable/schibsted-grotesk` | Schibsted Grotesk | OFL-1.1 | Hero and all headings |
| `@fontsource-variable/ibm-plex-sans` | IBM Plex Sans | OFL-1.1 | Body and UI |
| `@fontsource/ibm-plex-mono` | IBM Plex Mono | OFL-1.1 | Numbers, prices, dates, IDs, plates |

The font files are bundled by Vite and served by Caddy with the React build
(D1). No CDN, no Google Fonts link and no other third-party font request:
the lab network may have no internet access. Each package's full axis or
weight file is imported, because the rupee sign (U+20B9) is in the Latin
Extended subset; every subset is declared with a `unicode-range`, so the
browser downloads only the subsets a page actually uses (Latin and Latin
Extended in practice).

**Rationale.** The UI redesign (`docs/design/ui-brief.md`) needs a heading
face, a legible body face and a tabular face for money and IDs; the
choice between three candidate systems is recorded in
`docs/design/type-options.md`; the system
font stack gives none of these consistently across Windows, Android and iOS.
The OFL lets a font be used, bundled and redistributed with software
freely; its conditions (keep the licence and copyright notice, do not sell
the font on its own, rename modified versions) are met by shipping the
unmodified Fontsource files, which include the licence. Self-hosting keeps
the app working offline and sends no visitor data to a font host.

This reverses the reasoning in D10 that kept Geist out because OFL 1.1 was
not on the CO-7 list. Geist itself stays removed: it is not one of the three
fonts chosen.

## D23 — Photographs: licensed sources only, self-hosted, credited

**Decision.** Photographs in the frontend come only from:

- **Unsplash** under the Unsplash License (never an "Unsplash+" image);
- **Pexels** under the Pexels License;
- **Wikimedia Commons**, only files under CC0, Public Domain, CC BY or
  CC BY-SA (never NC, ND or "fair use" files).

Never an image, illustration or icon from a reference site, a vehicle
manufacturer (including a manufacturer's own account on Unsplash or
Pexels), a dealer or a rental company. Each photo's page is opened and its
photographer, source URL and exact licence recorded before use
(`frontend/scripts/image-sources.json`). Originals are downloaded by hand
into the git-ignored `frontend/.image-src/` and optimised by
`frontend/scripts/optimise-images.mjs` (sharp, a development dependency) to
AVIF, WebP and JPEG in `frontend/public/images/` (static files; the manifest
of sizes and credits is `frontend/src/assets/images/manifest.json`); only those outputs are
committed. Readable number plates are blurred in that script; no famous
landmark is a photo's subject; no AI-generated images. Every photo is
self-hosted: no hotlinking and no image CDN. Every photo in use is credited
in `docs/design/image-credits.md` and on the public "Photo credits" page
(`/credits`), rendered from the same data file, including the changes made
(crop, colour grade, plate blur), as CC BY and CC BY-SA require.

**Rationale.** The redesign uses real photography (landing page, auth
panel, vehicle listings, page bands; `docs/design/imagery-brief.md`). These
three sources allow free use in a project like this one; the excluded
licences either forbid derivatives (ND), restrict use (NC), or give no
licence at all (fair use). Brand and rental-company imagery carries
trademark and endorsement problems even when a platform hosts it.
Self-hosting keeps the app working on an offline lab network.

## D24 — Product name Veyora and tagline "Your Ride, Your Rules"

**Decision.** The product is named **Veyora**, with the tagline **"Your
Ride, Your Rules"**. The name is set through `AGENCY_NAME` in
`backend/.env` (`AGENCY_NAME=Veyora`), which the health endpoint returns as
`agency_name` (D7). The frontend falls back to "Veyora" while the setting is
unset or still the bracketed default placeholder. The tagline is a frontend
constant. The wordmark is the name set in Schibsted Grotesk 800 (one shared
`Brand` component, no logo mark); the tagline is set in IBM Plex Sans's own
italic (one shared `Tagline` component). Page titles read "<Page> - Veyora",
and the landing page "Veyora - Your Ride, Your Rules".

**Rationale.** The team named the product on 12 Oct 2026. Keeping the name
in `AGENCY_NAME` leaves D7 intact (one configurable name, read from the
API), and the frontend fallback means the UI shows the right name before
the backend setting is changed.

## Phase 1C frontend: proposed items (awaiting team approval)

The SRS does not settle these; the frontend implements them as listed.

| # | Item | Proposal |
|---|---|---|
| F1 | Several tabs open at once | Not coordinated yet: two tabs refreshing at the same instant can sign one of them out (D21). Proposal: share refreshes between tabs with a BroadcastChannel. |
| F2 | When the access token is refreshed | One minute before it expires, and only if the user did something since the last refresh (pointer, keyboard, touch, or returning to the tab). Coming back after the token lapsed refreshes at once. |
| F3 | OTP error wording | The server answers every failure the same way. The verify screen knows when the code was sent and how many tries were made on this screen, so it says "wrong (n tries left)", "expired" or "too many attempts". After a page reload it falls back to the server's generic message. |
| F4 | Licence review screen | There is no `GET licences/{id}/`; the review screen uses the licence passed from the queue, or finds it in the queue's first page (20 oldest). Proposal: add the detail endpoint. |
| F5 | Mobile-change resend | A visible 60-second countdown on the client, matching A3; the server applies only the profile throttle (A1) to mobile-change codes. |
| F6 | Accent colour | **Superseded by the UI redesign (light only, docs/design/ui-brief.md).** Was: `oklch(0.47 0.12 240)` in light mode and `oklch(0.76 0.11 235)` in dark mode, as the `--brand` token; light and dark follow the OS. |
| F7 | Help link (UI-2) | Present on every screen; it leads to a short help page until the online help system (UD-1) is built. |
| F8 | Planned features in the menu | Shown with a "Soon" label and an honest "not available yet" page; no sample data. |
| F9 | Registration fields | Date of birth (BR-2) and an emergency contact (SA-4) are asked at registration, because the backend requires them. |

## Maintenance module: proposed items (awaiting team approval)

The SRS does not settle these; `apps/fleet/services/status.py` and
`apps/maintenance` implement them as listed.

| # | Item | Proposal |
|---|---|---|
| M1 | Who clears an Unsafe flag | **Settled in Module N3:** an Administrator, or a technician an Administrator has marked "authorised to clear Unsafe" on the Users screen (`maintenance.UnsafeClearanceAuthorisation`; granting and revoking are audited). The authorised technician clears the flag while closing their own job (UC 10 extension 1a) and is recorded as `closed_by` and as the actor of the status change (BR-16); they may still ask an Administrator instead. Exp 4 sequence 3's Administrator path is unchanged. Was: Administrator only, because nothing marked a technician as authorised. |
| M2 | Retired is terminal | No transition leaves Retired, including to Unsafe. Appendix B's "any status → Unsafe" read literally would let a retired vehicle be flagged and then cleared back to Available. |
| M3 | Branch Manager and the status rules | A Branch Manager is not treated as an Administrator for clearing an Unsafe flag (BR-16) or retiring a vehicle (Fleet.Retire); both name the Administrator. |
| M4 | "Future booking" for Fleet.Retire | A booking that is Active (even if overdue), or Pending Payment or Confirmed with a return time still ahead. |
| M5 | Same-status request | Asking for the status a vehicle already has is a no-op: no error and no audit entry, since nothing changed. |
| M6 | Downtime | Entered by the technician in hours with the work record, and required before the job can close. The SRS lists downtime in Maint.History but not how it is measured. |
| M7 | Several open jobs on one vehicle | Completing or cancelling a job releases the vehicle to Available only if no other Scheduled or In Progress job holds it. If an Unsafe clearance is approved while another job is open, the vehicle goes Available and then straight back to Under Maintenance. |
| M8 | Cancelling a job | Releases a vehicle that the job had put Under Maintenance (rule M7 applies). An Unsafe flag stays until an Administrator clears it. |
| M9 | Which jobs count as a service | Every completed job updates the last service date and distance, as Maint.Complete says literally, whatever its type. A record with a service date older than the vehicle's last service does not overwrite it. The team may prefer that only Preventive jobs reset BR-15. |
| M10 | Who works a job | Only the assigned technician starts it, records work and completes it; an Administrator may also complete it (BR-16). Maint.Create also lets a technician report a job; the API does not expose that yet (Branch Staff, Branch Managers and Administrators report). |
| M11 | Branch Manager | Reports, schedules and cancels jobs on their own branch's vehicles, like Branch Staff. |
| M12 | Work record rules | The service date cannot be in the future; the odometer at service cannot be below the vehicle's reading (Appendix A); each record replaces the previous one in full; the total cost is labour plus parts, computed by the server; the record is locked once clearance is requested. |
| M13 | Starting a job | Refused while the vehicle is On Rent or Retired. |
| M14 | Maint.History for technicians | A technician can read the history of any vehicle, not only those of their own jobs. |

**Built in Module N3:** Maint.Auto.Km (at every return) and Maint.Auto.Time
(daily) through one function, `raise_preventive_job_if_due()`; the
workshop invoice (Maint.Record "permit"); Maint.History as a screen; the
cancellation record; BR-16's authorised technician (M1).

**Not built yet:** the Maint.Conflict offer to notify affected customers and
propose an alternative vehicle (the warning, the list and the explicit
confirmation are built); an Administrator declining a clearance.

## Module N3 (administration): proposed items (awaiting team approval)

| # | Item | Proposal |
|---|---|---|
| N3-P1 | Branch Manager and the audit log | Fleet.Audit says the log is "readable only by Administrators"; SRS 2.2 makes the Branch Manager a restricted Administrator, so they read their own branch's entries: about its bookings, vehicles, jobs, condition reports, payments, refunds, invoices and ledger, about the branch itself, and what its staff and manager did. Customer-level entries (a due paid on-line, a licence) stay with Administrators. |
| N3-P2 | Where the blacklist reason is kept | In the append-only "Customer Blacklisted" audit entry, read back for the screens, so no accounts migration is needed (the app is Rohan's). Proposal for later: a `Customer.blacklist_reason` field. |
| N3-P3 | Automatic Preventive jobs | Severity Medium (`PREVENTIVE_JOB_SEVERITY`); reported by the system; none while an open Preventive job exists, before any service is on record, or on a retired vehicle; the alert goes to every active technician and Administrator. |
| N3-P4 | Document expiry alert | Daily, to every active Administrator, listing each vehicle's latest document of each type that has expired or expires within 30 days (`DOCUMENT_EXPIRY_ALERT_WINDOW`). |
| N3-P5 | Vehicle photographs | JPG or PNG up to 5 MB, as the licence images (D20); at least four, always (Fleet.Add). |
| N3-P6 | Workshop invoice | A PDF (checked by its header) or a JPG/PNG photo of it, up to 5 MB; a new upload replaces the previous one, and the audit keeps the old key. |
| N3-P7 | Security deposit on a tariff | Fleet.Tariff lists the deposit among the tariff's values, but BR-3 fixes it per vehicle type, so a new tariff takes BR-3's amount and the form does not ask for it. |
| N3-P8 | First staff password | The Administrator sets it when creating the account and passes it on in person; it is never shown or e-mailed (SE-2), and the user can change it after signing in. Forcing a change at first sign-in is not built. |
| N3-P9 | "Next service overdue" (SA-2) | Due when the odometer has reached the BR-15 distance, or the date its time interval gives has come, from the last service on record; unknown (never overdue) before any service is recorded. Handover is refused with its own reason (`service_overdue`). Search and booking (SA-2's other two) are the catalogue's, Rohan's. |
| N3-P10 | Booking links on the blacklist screen | There is no staff or Administrator booking detail screen yet, so each booking links to its audit history (`/app/audit?entity_type=bookings.Booking&entity_id=…`). |

## Module R4 (catalogue, rating, delivery): proposed items (awaiting team approval)

R4-P1 to R4-P7 are listed with their reasons in
`docs/traceability-catalogue-rating.md`, section 6: the "nearest" alternatives
(±3 days, at most 3 dates), no delivery change through Modify, generated demo
photo cards, the serviceable area matched by pincode, 409 for a refused rating,
SA-2 judged today, and search priced at the pickup date's tariff while the
quote still prices at today's. D13 stands: the average rating and count are
computed on every query, never stored.

## Module N4 (deployment, PWA, hardening): proposed items (awaiting team approval)

N4-P1 to N4-P10 are listed with their reasons in `docs/traceability-deploy.md`,
section 7: a VM smaller than OE-4's 4 vCPU / 8 GB is a deviation to record;
SE-1 "at rest" relies on Azure's disk encryption; the SE-9 re-check is
throttled with the SE-8 numbers (5 wrong passwords, 15 minutes, 429); CORS stays
closed (one origin behind Caddy, D1); the PWA caches nothing personal and shows
an offline page; the offline page's new copy; nightly backups of the database
and the media on the VM itself; the Content Security Policy covers only the
React app; OE-3 and WCAG were reviewed statically; the public demo accounts.

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
| @fontsource-variable/schibsted-grotesk | 5.3.0 | OFL-1.1 | OK under D22 (hero and heading font, self-hosted) |
| @fontsource-variable/ibm-plex-sans | 5.3.0 | OFL-1.1 | OK under D22 (body and UI font, self-hosted) |
| @fontsource/ibm-plex-mono | 5.3.0 | OFL-1.1 | OK under D22 (numbers, prices, dates and IDs, self-hosted) |

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
| sharp | 0.35.5 | Apache-2.0 | OK (build-time image optimisation only, `scripts/optimise-images.mjs`; never shipped, D10, D23) |
| @types/react, @types/react-dom, @types/node | 18.3.31, 18.3.7, 22.20.5 | MIT | OK |

Removed: `@fontsource-variable/geist` (added by `shadcn init`). Geist stays
removed. SIL OFL 1.1 fonts are now permitted under D22, and the UI uses
Schibsted Grotesk, IBM Plex Sans and IBM Plex Mono (see "Frontend runtime"
above). Fraunces, Archivo and the type-comparison candidates (Barlow,
Barlow Semi Condensed, JetBrains Mono, Red Hat Display, Red Hat Text, Red
Hat Mono) were installed during the redesign and removed again.

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
