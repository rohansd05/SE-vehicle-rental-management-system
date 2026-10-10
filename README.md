# Vehicle Rental Management System (VRMS)

A full-stack vehicle rental platform for a single-agency car and two-wheeler
rental business. Built as the semester project for the Software Engineering
course, Department of Computer Engineering, Sardar Patel Institute of
Technology, Mumbai.

VRMS replaces a manual register-and-telephone booking process with a
responsive web application backed by a REST API, eliminating double bookings,
disputes over charges, and missed vehicle servicing.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [API Documentation](#api-documentation)
- [Project Documentation](#project-documentation)
- [Team](#team)

---

## Features

**Customer**
- Browse the vehicle catalogue and view published tariffs without an account
- Real-time availability search with filters for type, category, fuel,
  transmission, price and rating
- Book a car or two-wheeler with a 15-minute vehicle hold during checkout
- Modify, extend or cancel a booking under a published cancellation policy
- Pay by card, online (UPI, net banking or wallet), or cash on branch
  collection
- Rental history with downloadable invoices, rental agreements and condition
  reports
- Rate the vehicle and the service after a completed rental

**Branch Staff**
- Retrieve a booking by reference, pickup code or customer mobile number
- Photographic handover and return checklists with digital customer signature
- Automatic itemised settlement against the security deposit
- Flag a vehicle for maintenance during return

**Maintenance Technician**
- Receive assigned jobs, record work, parts and labour cost
- Close a job and return the vehicle to service

**Administrator**
- Fleet master data, statutory document tracking and vehicle retirement
- Tariff definition with effective dates and full historical retention
- Staff account management and customer blacklist
- Refund approval above the automatic threshold
- Utilisation, revenue and maintenance-cost reporting
- Complete, non-editable audit log

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2 LTS, Django REST Framework |
| Database | PostgreSQL 16 |
| Async tasks | Celery + Valkey (Redis-protocol broker), Celery Beat for scheduled jobs |
| Auth | JWT (SimpleJWT), bcrypt password hashing |
| API docs | drf-spectacular (OpenAPI 3.0) |
| Frontend | React 18, TypeScript, Vite |
| Styling | Tailwind CSS, shadcn/ui (Radix primitives) |
| Data fetching | TanStack Query |
| Forms | React Hook Form + Zod |
| Charts | Recharts |
| Testing | pytest, pytest-django, factory-boy, Vitest |

---

## Architecture

Clients (responsive web) communicate with a single Django REST API over
HTTPS. All business logic — availability, pricing, eligibility and
authorisation — is enforced server-side; client-side validation exists for
usability only.

Two external services are integrated behind interfaces so that each can be
replaced or mocked:

- **Payment Gateway** — authorisation, capture and refund. No card data is
  stored, logged or transmitted by VRMS.
- **Notification Service** — transactional e-mail, SMS and push, queued so
  that a provider outage cannot fail a booking transaction.

Concurrency safety for bookings is enforced at the database level using a
PostgreSQL range exclusion constraint, so no two Confirmed or Active bookings
for the same vehicle can ever overlap.

---

## Getting Started

All commands below are for **Windows PowerShell**, run from the repository
root unless a `cd` says otherwise. PostgreSQL and Valkey run in Docker;
Django runs natively in a Python virtual environment.

### Prerequisites

- Python 3.12
- Node.js 22 LTS, version 22.22 or later (Vite 8, Vitest 5 and jsdom require it)
- Docker Desktop (runs PostgreSQL 16 and Valkey 8 via `docker-compose.yml`)
- Git

### Clone

```powershell
git clone https://github.com/rohansd05/vehicle-rental-management-system.git
cd vehicle-rental-management-system
```

### Start PostgreSQL and Valkey

```powershell
docker compose up -d
docker compose ps        # both services should report "healthy"
```

### Backend setup

```powershell
cd backend
py -3.12 -m venv venv                       # skip if backend\venv already exists
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env                 # then edit .env
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py seed_demo          # demo data and demo accounts
```

`seed_demo` is idempotent. `seed_demo --reset` removes only the demo data and
loads it again; it refuses if bookings or other records already use it. To
create your own administrator instead, run `manage.py createsuperuser`.

Always call the venv's interpreter (`.\venv\Scripts\python.exe`) or activate
the venv first (`.\venv\Scripts\Activate.ps1`), so that no other Python
installation on the machine is used.

### Frontend setup

```powershell
cd frontend
npm install
```

---

## Configuration

All backend configuration is read from `backend/.env`. Copy
`backend/.env.example` to `backend/.env` and fill in your own values. Never
commit `.env`.

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` in development only |
| `ALLOWED_HOSTS` | Comma-separated host names |
| `NUM_PROXIES` | Reverse proxies in front of Django: `0` locally, `1` behind Caddy (client IP for throttling and audit) |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins, e.g. `http://localhost:5173` |
| `DATABASE_URL` | `postgres://vrms:vrms_dev_password@localhost:5432/vrms` (matches `docker-compose.yml`) |
| `REDIS_URL` | `redis://localhost:6379/0` (Valkey; Celery broker and result backend) |
| `AGENCY_NAME` | Agency name shown by the API and UI (never hardcoded) |
| `CURRENCY` | `INR` |
| `AGENCY_TAX_REGISTRATION` | Tax registration (e.g. GSTIN) printed on every invoice (Pay.Invoice) |
| `PAYMENT_GATEWAY_BACKEND` | `mock` (sandbox implementation) |
| `PAYMENT_GATEWAY_KEY_ID` / `PAYMENT_GATEWAY_KEY_SECRET` | Gateway test-mode credentials |
| `NOTIFICATION_BACKEND` | `mock` (sandbox implementation) |
| `SMS_ACCOUNT_SID` / `SMS_AUTH_TOKEN` | SMS provider credentials |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_USE_TLS` / `DEFAULT_FROM_EMAIL` | Mail service settings |
| `MEDIA_URL_EXPIRY_SECONDS` | Signed document link lifetime (default 900) |
| `SECURE_HSTS_SECONDS` | Production only: HSTS max-age |

All external integrations run in **sandbox mode**. No live financial
settlement takes place.

---

## Running the Application

Start PostgreSQL and Valkey (`docker compose up -d`), then run four
processes, each in its own PowerShell terminal:

```powershell
# 1. API server
cd backend; .\venv\Scripts\python.exe manage.py runserver

# 2. Celery worker (--pool=solo is required on Windows)
cd backend; .\venv\Scripts\celery.exe -A config worker -l info --pool=solo

# 3. Celery Beat scheduler
cd backend; .\venv\Scripts\celery.exe -A config beat -l info

# 4. Frontend dev server (proxies /api, /admin and /static to port 8000)
cd frontend; npm run dev
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000/api/v1/ |
| Health check | http://localhost:8000/api/v1/health/ |
| API docs (Swagger) | http://localhost:8000/api/docs/ |
| Django admin | http://localhost:8000/admin/ |

### Demo accounts

Created by `manage.py seed_demo`. Demo data only; never use these accounts
or this password in production.

| Role | E-mail | Password |
|---|---|---|
| Customer | customer@vrms.test | Demo@1234 |
| Branch Staff | staff@vrms.test | Demo@1234 |
| Technician | tech@vrms.test | Demo@1234 |
| Administrator | admin@vrms.test | Demo@1234 |
| Branch Manager | manager@vrms.test | Demo@1234 |

---

## Testing

PostgreSQL must be running (`docker compose up -d`); the test settings use it.

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest                                  # full suite
.\venv\Scripts\python.exe -m pytest --cov=apps --cov-report=html     # with coverage report
.\venv\Scripts\python.exe -m pytest apps/bookings/tests/ -v          # one app
.\venv\Scripts\python.exe -m pytest -m concurrency                   # concurrency suite only
.\venv\Scripts\python.exe -m ruff check .
.\venv\Scripts\python.exe -m black --check .
```

```powershell
cd frontend
npm run typecheck           # tsc
npm run lint                # oxlint
npm run test -- --run       # Vitest + Testing Library; the API is mocked with MSW
npm run build
```

### Frontend API types

The frontend's API types are generated from the backend schema. After any
API change, regenerate both files and commit them:

```powershell
cd frontend
npm run api:schema          # backend schema -> docs/api/openapi.yaml
npm run api:types           # docs/api/openapi.yaml -> src/api/schema.d.ts
```

### How the session works (D19, D21)

- Sign-in returns a short-lived access token, kept only in memory; the
  refresh token is an httpOnly cookie the page cannot read. Nothing is
  stored in localStorage or sessionStorage.
- Reloading the page restores the session from the cookie.
- While you use the app, the access token is renewed shortly before it
  expires. After 30 minutes without activity you are signed out and the
  sign-in page says why.

Coverage targets: at least 70% of business logic overall, and 100% of the
pricing, availability and settlement logic.

---

## API Documentation

Interactive documentation is generated from the code and served at
`/api/docs/` (public in development; administrators only in production,
D12). To export the schema:

```powershell
cd backend
.\venv\Scripts\python.exe manage.py spectacular --file ..\docs\api\openapi.yaml
```

### Authentication and licence endpoints (`/api/v1/`)

| Method and path | Who may call it |
|---|---|
| `POST auth/register/` | Anyone (creates a customer account; staff accounts are created in the Django admin) |
| `POST auth/verify-otp/`, `POST auth/resend-otp/` | Anyone |
| `POST auth/login/`, `POST auth/refresh/`, `POST auth/logout/` | Anyone (refresh and logout act on the refresh cookie) |
| `POST auth/password/change/` | Any signed-in user |
| `GET`/`PATCH me/`, `POST me/verify-mobile/` | Any signed-in user |
| `GET`/`POST licence/` | Customer |
| `GET licences/`, `POST licences/{id}/approve/`, `POST licences/{id}/reject/` | Branch Staff, Administrator |
| `GET files/{token}/` | Anyone holding a valid signed link (expires after 15 minutes, SI-3) |

Sign-in returns `{access, user}` and sets the refresh token in the httpOnly
`vrms_refresh` cookie (D21). Send `Authorization: Bearer <access>`; call
`auth/refresh/` with no body while the user is active (D19). In development
the OTP SMS is printed by the Celery worker
(`celery -A config worker --pool=solo -l info`); start the worker before
registering.

---

## Project Documentation

Course deliverables are in `docs/experiments/`:

| # | Deliverable |
|---|---|
| 1 | Software Requirements Specification (IEEE 830) |
| 2 | Use Case Diagram and Descriptions |
| 3 | Class Diagram |
| 4 | Interaction Diagrams (Sequence, Collaboration) |
| 5 | Activity Diagram |
| 6 | Data Flow Diagrams (Level 0 and 1) |
| 7 | Work Breakdown Structure and Schedule |
| 8 | Risk Mitigation, Monitoring and Management Plan |
| 9 | Module Implementation |
| 10 | Test Cases and Unit Testing |

The SRS is the authoritative specification. Business rules BR-1 to BR-16
in Section 5.5 are referenced throughout the codebase; any change to a rule
must be reflected in every requirement and test that references it.

---

## Team

| Name | UID | Division | Batch |
|---|---|---|---|
| Rohan Dhumal | 2024300049 | A | A3 |
| Nidhi Rajkamal Dhyani | 2024300050 | A | A3 |

Department of Computer Engineering
Sardar Patel Institute of Technology, Andheri (W), Mumbai

---

## Licence

Academic project. Not licensed for commercial use.