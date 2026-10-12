# Demo route map (Veyora)

The script for the lab demo and the video. Every heading, label and record
below was read from the running app on 13 Oct 2026, signed in as each demo
account, at 1920 x 960. Only what exists is listed.

- Frontend: http://localhost:5173 (backend http://localhost:8000).
- Password for every demo account: `Demo@1234`.
- Recording viewport: 1920 x 960, Windows display scaling 100 %.
- Labels in quotes are exact. Dates and times show in Indian English
  ("14 Oct 2026, 10:00 am"); amounts in rupees ("₹4,248.00").

## Before recording

These steps change data. Doing them again needs a reset
(`python manage.py seed_demo --reset` in `backend/`, run by a person; the
seed then recreates the demo records).

- **Customer booking:** creates a new booking (B4) and its payment.
- **Approve or reject licence 2:** changes the pending customer's licence.
- **Start job 1, record the work, complete it:** changes job 1 and the Dzire.
- **Clear job 3:** completes job 3 and makes the Ntorq Available.

Do not use booking 2 (Hyundai Venue, Pending Payment) on camera: its
15-minute hold ran out on 11 Oct 2026, so its payment page says "Your hold
has run out. Paying now may ask you to hold the vehicle again."

## Seeded records you can rely on

| What | Record |
|---|---|
| Branches | Andheri, Bandra, Powai, Thane, Vashi (the demo staff and manager are at Andheri) |
| Bookable at Andheri, 14 to 16 Oct 2026 | Bajaj Platina 110, Honda Dio, Hyundai Venue, Maruti Suzuki Baleno, Maruti Suzuki Swift, Toyota Innova Crysta |
| Customer's bookings | Booking VRMS-20261011-0001, Maruti Suzuki Swift (MH02DM1001), Confirmed, 20 Oct 2026, 10:00 am to 22 Oct 2026, 10:00 am, Andheri, total ₹4,248.00, pickup code 852704, invoice INV-2026-000001. Booking 2, Hyundai Venue (MH02DB2002), Pending Payment, hold expired |
| Customer's licence | MH02 20150012345, RTO Mumbai (West), Verified, valid 1 Jun 2015 to 19 May 2035, Car and Two-Wheeler |
| Licence waiting for a check | Licence 2: Demo Customer (licence pending), MH02 20180054321, Pending Verification |
| Maintenance jobs (all Andheri, technician Demo Technician) | Job 1 · MH02DM1006 Maruti Suzuki Dzire, Scheduled, Medium, "[Demo] Clutch slipping in third gear." Job 2 · MH02DM1011 Toyota Innova Crysta, Completed. Job 3 · MH02DM1016 TVS Ntorq 125, In Progress, Critical, vehicle Unsafe, awaiting clearance. Job 4 · MH02DM1001 Maruti Suzuki Swift, Completed |
| Discount codes | WELCOME10 (10 %), FLAT500 (₹500), valid to 31 Dec 2026 |
| Sandbox payment | "Test card that is approved" or "Test card that is declined"; no card number is typed |

## a. Signed out

| Step | Route | Heading on screen | Click or type | Expected result |
|---|---|---|---|---|
| 1 | `/` | Veyora (tagline "Your Ride, Your Rules") | Scroll: "Book online, collect at the branch", "How it works", "Cars and two-wheelers", "For branch teams", "System status", "Help", "Create your account" | Sections reveal once as they scroll in |
| 2 | `/help` | Help | Topics "Signing in", "Verification codes", "Driving licence", "Where to go" | Topic list with links "Sign in" and "Create an account" |
| 3 | `/credits` (footer link "Photo credits") | Photo credits | Scroll | Every photo with its author, source and licence |
| 4 | `/register` | Create your account | Show the fields "Full name", "E-mail", "Mobile number", "Date of birth", "Address", "Emergency contact" ("Name", "Mobile number"), "Password", "Confirm password"; click "Create account" with the form empty | Each field shows its message, for example "Enter your full name." Do not complete the form: it creates a real account and goes on to "Verify your mobile number" |
| 5 | `/login` | Sign in | "E-mail" `customer@vrms.test`, "Password" `Demo@1234`, "Sign in" | Lands on `/app`, "Welcome, Demo Customer" |

`/verify` ("Verify your mobile number") is reached only after registering.
Opening `/app/bookings` while signed out goes to "Sign in".

## b. Customer (customer@vrms.test)

| Step | Route | Heading | Click or type | Expected result |
|---|---|---|---|---|
| 1 | `/app` | Welcome, Demo Customer | Tiles "Find a vehicle", "My bookings", "Driving licence", "My profile" | Signed in as Customer |
| 2 | `/app/search` (menu "Find a vehicle") | Find a vehicle | "Pickup branch" Andheri; "Vehicle category" Any category; "Pickup" 14-10-2026 10:00; "Return" 16-10-2026 10:00; "Search" | "Available vehicles": "6 vehicles are free at Andheri from 14 Oct 2026, 10:00 am to 16 Oct 2026, 10:00 am." Each tile shows its "Estimated price" |
| 3 | same | Find a vehicle | Filter: "Vehicle category" SUV (Car), "Search" | Hyundai Venue and Toyota Innova Crysta only |
| 4 | `/app/vehicles/21?…` (tile "Maruti Suzuki Baleno") | Maruti Suzuki Baleno (2025) | Read "Policies" and "Add-ons, charged per day"; tick "I accept the rental terms above." | Rail "Book this vehicle": 14 Oct 2026, 10:00 am to 16 Oct 2026, 10:00 am, collected at Andheri. "Price summary": Rental, 2 days at ₹1,800.00, ₹3,600.00; Tax at 18%, ₹648.00; "Total payable" ₹4,248.00; refundable deposit ₹5,000.00 |
| 5 | same | same | Optional: "Discount code" `WELCOME10`, "Apply" | Not tried live (it would only change the quote); skip it on camera unless rehearsed |
| 6 | same | same | "Hold this vehicle and pay" | Goes to `/app/bookings/<new id>/pay` (this creates the booking) |
| 7 | `/app/bookings/<id>/pay` | Pay for your booking | "Payment method (sandbox)": "Test card that is approved"; "Your password" `Demo@1234`; "Pay ₹4,248.00 and hold ₹5,000.00 deposit" (the amount is the step 4 total) | The hold timer counts down in the rail while you pay. After paying: the booking page with "Your booking is confirmed. Keep the pickup code safe; you will need it at the branch.", a booking reference VRMS-…, a pickup code and an invoice number |
| 8 | `/app/bookings` (menu "My bookings") | My bookings | "Status" filter: "All statuses", then "Confirmed" | Rows for each booking; "Cancelled" shows "No Cancelled bookings" |
| 9 | `/app/bookings/1` (row "Maruti Suzuki Swift · VRMS-20261011-0001") | Booking VRMS-20261011-0001 | "Download invoice INV-2026-000001" | Booking reference, pickup code 852704, transaction, invoice; price ₹4,248.00. The invoice PDF downloads |
| 10 | `/app/licence` (menu "Driving licence") | Driving licence | Read "Licence status" | Verified, MH02 20150012345, RTO Mumbai (West), 1 Jun 2015 to 19 May 2035, Car, Two-Wheeler. Note: "Your licence was verified on —" until the backend seed sets the date (see the findings) |
| 11 | `/app/profile` (menu "My profile") | My profile | Sections "Your details" ("Edit details"), "Mobile number" ("Send code"), "Password" ("Change password") | Read only unless you save |
| 12 | top bar "Sign out" | Sign in | | Back on `/login` |

## c. Branch staff (staff@vrms.test)

| Step | Route | Heading | Click or type | Expected result |
|---|---|---|---|---|
| 1 | `/app` | Welcome, Demo Branch Staff | Tiles "Licence checks", "Maintenance", "My profile", plus "Handover and return" and "Branch bookings" marked "Not available yet" | |
| 2 | `/app/licences` (menu "Licence checks") | Licence checks | Row "Demo Customer (licence pending) MH02 20180054321 · Car, Two-Wheeler" | "Refresh" re-reads the queue |
| 3 | `/app/licences/2` | Review licence: Demo Customer (licence pending) | "Details", "Photos"; rail "Approve" or "Reject" ("Reject" opens "Reject this licence?" with "Reason", "Keep it pending", "Reject licence") | Approve: the licence leaves the queue. Escape or "Keep it pending" closes the dialog with nothing changed |
| 4 | `/app/maintenance` (menu "Maintenance") | Maintenance | "Status" filter; rows Job 4, 3, 2, 1; "Report a fault" | |
| 5 | `/app/maintenance/report` | Report a fault | "Vehicle" (for example MH02DB2001 · Maruti Suzuki Baleno (Available)), "Job type" (Preventive, Corrective, Inspection, Cleaning, Documentation), "Severity" (Low to Critical), "Problem", "Flag the vehicle as Unsafe"; "Report fault" | Creates a Reported job (only if you submit). Empty submit shows "Choose the vehicle.", "Choose the job type.", "Choose the severity.", "Describe the problem." |
| 6 | `/app/maintenance/1` | Job 1 · MH02DM1006 | "Job and vehicle"; rail "Cancel job" | Do not cancel on camera if the technician will start job 1 |
| 7 | `/app/handover`, `/app/branch-bookings` | Handover and return / Branch bookings | | "Not available yet" pages with "Back to home" |

Unsafe clearances (`/app/clearances`) belong to the Administrator, not staff.

## d. Technician (tech@vrms.test)

| Step | Route | Heading | Click or type | Expected result |
|---|---|---|---|---|
| 1 | `/app/jobs` (menu "Maintenance jobs") | Maintenance jobs | Rows Job 4, 3, 2, 1 | |
| 2 | `/app/jobs/1` | Job 1 · MH02DM1006 | Rail "Start job" | Job goes In Progress; the "Record the work" form appears |
| 3 | same | "Record the work" | "Service date", "Odometer at service (km)", "Work performed", "Labour cost (₹)", "Downtime (hours)", "Parts used" ("Add a part": "Part 1", "Quantity", "Unit cost (₹)", "Remove"); "Save work record" | The "Work recorded" section shows the record and the "Total cost" |
| 4 | same | rail "Complete the job" | "Complete job" | Job Completed; the Dzire becomes Available |
| 5 | `/app/jobs/2` | Job 2 · MH02DM1011 | | "Work recorded" for a completed job, no form (use this if you skip steps 2 to 4) |
| 6 | `/app/jobs/3` | Job 3 · MH02DM1016 | | "Work recorded" and the notice "Awaiting administrator clearance" |

## e. Branch manager (manager@vrms.test)

| Step | Route | Heading | Click or type | Expected result |
|---|---|---|---|---|
| 1 | `/app` | Welcome, Demo Branch Manager | Tiles "Maintenance", "My profile"; "Branch bookings" and "Reports" marked "Not available yet" | |
| 2 | `/app/reports` | Reports | | "Not available yet" page. There are no report screens, KPIs or charts in this release |
| 3 | `/app/maintenance` | Maintenance | As for staff | |
| 4 | `/app/maintenance/1` | Job 1 · MH02DM1006 | rail "Cancel job" | Manager can cancel a Reported or Scheduled job |

## f. Administrator (admin@vrms.test)

| Step | Route | Heading | Click or type | Expected result |
|---|---|---|---|---|
| 1 | `/app` | Welcome, Demo Administrator | Tiles "Licence checks", "Maintenance", "Unsafe clearances", "My profile"; "Fleet", "Tariffs", "Users", "Reports", "Audit log" marked "Not available yet" | |
| 2 | `/app/clearances` (menu "Unsafe clearances") | Unsafe clearances | Row "Job 3 · MH02DM1016 Awaiting clearance Unsafe" | |
| 3 | `/app/maintenance/3` | Job 3 · MH02DM1016 | Rail "Clear Unsafe flag and complete", dialog "Clear the Unsafe flag on MH02DM1016?", "Approve clearance" ("Not yet" closes it) | Job 3 completed; the Ntorq becomes Available; the admin is recorded as approver (BR-16) |
| 4 | `/app/licences/2` | Review licence: Demo Customer (licence pending) | As for staff | |
| 5 | `/app/fleet`, `/app/tariffs`, `/app/users`, `/app/reports`, `/app/audit` | Fleet, Tariffs, Users, Reports, Audit log | | "Not available yet" pages. Admin data screens are not built in this release |

## Other screens

- **403:** a customer opening `/app/licences` sees "You don’t have access to
  this page".
- **404:** any unknown address, for example `/app/nope`, shows "Page not
  found".
