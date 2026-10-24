# Exp 10 demo scenarios: Maintenance module

Website steps for the Maintenance test cases of Exp 10 (TC-M1 to TC-M5, BR-15
and SA-2), plus the Exp 8 R7 booking-privacy check. All data is fictitious
demo data.

- Frontend http://localhost:5173, backend http://localhost:8000.
- Password for every demo account: `Demo@1234`.
- Labels in quotes are exact text from the frontend. Text from the backend
  is shown as the page shows it, including the "(BR-n)" tags.
- Dates show as the browser formats them for en-IN, for example "28 Feb 2027".

## Setup

In `backend/`, in this order:

```
python manage.py seed_demo
python manage.py seed_maintenance_scenarios
```

The command prints what it created and the four demo vehicles. Running it
again prints "Created: nothing." It needs no other scenario command, and the
booking scenarios (`seed_booking_scenarios`) can be loaded too.

| Registration | Vehicle (as search shows it) | Last service | Odometer | BR-15 due point | Test case |
|---|---|---|---|---|---|
| MH03DX9001 | Skoda Slavia, Sedan, Grey | 20,000 km, seed day − 30 days | 25,000 km | 25,000 km: **due** | TC-M4 |
| MH03DX9002 | Volkswagen Virtus, Sedan, White | 20,000 km, seed day − 30 days | 24,999 km | 25,000 km: not due | TC-M5 |
| MH03DX9003 | Yamaha Fascino 125, Scooter, Blue | 3,000 km, seed day − 30 days | 6,000 km | 6,000 km (two-wheeler interval 3,000 km): **due** | TC-M1 |
| MH03DX9004 | Hyundai Aura, Sedan, Silver | 30,000 km, 31 Aug 2026 | 31,000 km | 35,000 km or 28 Feb 2027: not due | TC-M2, TC-M3 |

All four are at Powai, with valid documents and four catalogue photos.
MH03DX9004 also has one Reported Corrective job, severity Low, "[Demo] Exp 10
scenario: check the next service due." No Preventive job is seeded: the daily
Celery Beat task raises them (section 3).

seed_demo has no sedans at Powai, so a Powai Sedan search lists only these
demo cars. `python manage.py seed_demo --reset` refuses (and deletes nothing)
while these vehicles exist, as it does for the booking scenarios.

## 1. Search leaves out the overdue sedan (TC-M4, TC-M5)

Account: `customer@vrms.test` (a guest can search too, at `/search`).

| Step | Route | Click or type | Expected on screen |
|---|---|---|---|
| 1 | `/login` | "E-mail" `customer@vrms.test`, "Password" `Demo@1234`, "Sign in" | `/app` |
| 2 | `/app/search` (menu "Find a vehicle") | "Pickup branch" Powai; "Vehicle category" Sedan (Car); "Pickup" tomorrow, 10:00; "Return" the day after, 10:00; "Search" | "Available vehicles" and "2 vehicles are free at Powai from … to …." |
| 3 | same | read the tiles | Hyundai Aura and Volkswagen Virtus (MH03DX9002, 24,999 km: TC-M5, offered). No Skoda Slavia (MH03DX9001, exactly 25,000 km: TC-M4, not offered) |

## 2. The overdue sedan's own page (TC-M4, SA-2)

The Skoda Slavia never appears in search, so open its page by its id.

| Step | Route | Click or type | Expected on screen |
|---|---|---|---|
| 1 | `/login` | Sign in as `admin@vrms.test` | `/app` |
| 2 | `/app/fleet` (menu "Fleet") | "Find" `MH03DX9001` | "1 vehicle." and the Skoda Slavia row |
| 3 | same | open the row | The address bar shows `/app/fleet/<id>`; note the number |
| 4 | `/vehicles/<id>` (type it in the address bar, signed in or not) | | "Skoda Slavia (2024)", and in the right-hand panel "Not bookable: service overdue" with "This vehicle is due for its safety service. Please choose another vehicle." |

Signed in as `customer@vrms.test`, `/app/vehicles/<id>` shows the same panel,
also with dates in the address, for example
`/app/vehicles/<id>?pickup_datetime=…&return_datetime=…`: no booking form is
offered.

## 3. The Preventive job raised for the overdue vehicles (Maint.Auto.Time, TC-M1, TC-M4)

Celery Beat runs `raise_preventive_jobs` daily (and once when Beat starts). To
raise the jobs at once, with Valkey running (`docker compose up -d`), in
`backend/`:

```
python manage.py shell -c "from apps.maintenance.services import raise_due_preventive_jobs; print(raise_due_preventive_jobs())"
```

It prints how many jobs it raised (the demo's MH02DN7001 may be among them).
It raises one for MH03DX9001 and one for MH03DX9003, none for MH03DX9002 or
MH03DX9004, and never a second one while a Preventive job is open. The
service-due e-mails go out when the Celery worker runs
(`celery -A config worker -l info --pool=solo`).

| Step | Route | Click or type | Expected on screen |
|---|---|---|---|
| 1 | `/login` | Sign in as `admin@vrms.test` | `/app` |
| 2 | `/app/maintenance` (menu "Maintenance") | "Status" Reported | rows "Job N · MH03DX9001" and "Job N · MH03DX9003"; no Preventive job for MH03DX9002 |
| 3 | open "Job N · MH03DX9001" | | "Preventive service overdue" and "MH03DX9001 has reached its service interval (BR-15). It cannot be handed over until the service is recorded (SA-2)." |
| 4 | same, card "Job and vehicle" | | "Job type" Preventive; "Severity" Medium; "Problem" "Preventive service due (BR-15) at 25,000 km or <date>, whichever comes first. The odometer reads 25,000 km."; "Reported" "Raised by the system (BR-15), …"; "Service due (BR-15)" "<date> or 25,000 km, whichever comes first" |

`<date>` is the last service date plus 6 months (seed day − 30 days + 6
months). For MH03DX9003 the problem reads "at 6,000 km or <date>" (4 months
for a two-wheeler).

## 4. Next service due on the job page (TC-M2, TC-M3)

| Step | Route | Click or type | Expected on screen |
|---|---|---|---|
| 1 | `/login` | Sign in as `admin@vrms.test` | `/app` |
| 2 | `/app/maintenance` (menu "Maintenance") | "Status" Reported | row "Job N · MH03DX9004" |
| 3 | open it | card "Job and vehicle" | "Job type" Corrective; "Severity" Low; "Problem" "[Demo] Exp 10 scenario: check the next service due."; "Odometer" 31,000 km; "Last service" "31 Aug 2026 at 30,000 km"; "Next service due (BR-15)" "28 Feb 2027 or 35,000 km, whichever comes first" |

No "Preventive service overdue" note appears: 31,000 km is short of 35,000 km
(TC-M2) and 28 Feb 2027 has not come (TC-M3; 31 Aug + 6 months, the last
day of February).

## 5. LAPTOP ONLY: a failing test on the website (TC-M4 bug)

Do this only on a laptop running `python manage.py runserver`, never on the
deployed server, and undo it straight after.

| Step | Where | Do | Expected |
|---|---|---|---|
| 1 | browser | section 1 search (Powai, Sedan (Car), tomorrow 10:00 to the day after) | "2 vehicles are free at Powai …"; no Skoda Slavia |
| 2 | `backend/apps/maintenance/services.py`, line 140 | change `vehicle.odometer >= due.odometer` to `vehicle.odometer > due.odometer` and save | runserver reloads by itself (its window prints "…services.py changed, reloading.") |
| 3 | browser | "Search" again with the same values | "3 vehicles are free at Powai …": the Skoda Slavia (MH03DX9001, exactly at 25,000 km) is now offered. This is the TC-M4 bug: a vehicle at the due point must not be bookable |
| 4 | browser | its page, `/vehicles/<id>` from section 2 | "Not bookable: service overdue" is gone |
| 5 | terminal, repository root | `git restore backend/apps/maintenance/services.py` | runserver reloads; "Search" again shows "2 vehicles are free at Powai …" |

With the change in place, `pytest apps/maintenance/tests/test_seed_scenarios.py`
in `backend/` fails too (the overdue sedan is no longer due and is found by
search).

## 6. R7 another customer's booking is not found (Exp 8, History.Privacy)

Two browsers: a normal window as `customer@vrms.test`, an incognito window as
`changes@vrms.test`.

| Step | Window | Route | Click or type | Expected on screen |
|---|---|---|---|---|
| 1 | normal | `/login` | Sign in as `customer@vrms.test` | `/app` |
| 2 | normal | `/app/bookings` (menu "My bookings") | open any booking | `/app/bookings/<id>`, "Booking VRMS-…" |
| 3 | normal | same | copy the URL from the address bar | |
| 4 | incognito | `/login` | Sign in as `changes@vrms.test` | `/app` |
| 5 | incognito | paste the URL from step 3 | | "We couldn’t load this booking" and "No Booking matches the given query." No detail of the other customer's booking is shown |

`customer@vrms.test` has no seeded booking. If "My bookings" is empty, make
one first: section 3 steps 1 and 2 of `exp-scenarios-booking.md` (search,
"View and book", "Hold this vehicle and pay", then leave the pay page). The
held booking keeps its page after the 15-minute hold runs out.
