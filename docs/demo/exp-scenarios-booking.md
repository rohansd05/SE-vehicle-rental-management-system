# Exp 8 / Exp 10 demo scenarios: Booking module

Website steps for the Booking scenarios of Exp 8 (risks R6, R7, R10) and
Exp 10 (TC-B1 to TC-B3, TC-B5). All data is fictitious demo data.

- Frontend http://localhost:5173, backend http://localhost:8000.
- Password for every demo account: `Demo@1234`.
- Labels in quotes are exact text from the frontend. Text from the backend
  is shown as the page shows it, including the "(BR-n)" tags.

## Setup

In `backend/`, in this order:

```
python manage.py seed_demo
python manage.py seed_demo --reports
python manage.py seed_booking_scenarios
```

The last command prints what it created and the three accounts
`refunds@vrms.test`, `young@vrms.test` and `lockout@vrms.test`. Running it
again prints "Created: nothing."

**Timing.** The refund bookings are collected 72, 30 and 6 hours after the
command ran, so their slabs hold only for a while: show the 75% booking
within 18 hours and the 100% booking within 24 hours of seeding. The 6-hour
booking becomes a No-show once its pickup time has passed. young@vrms.test
turns 21 seven days after the first run (the date of birth is set once and
not moved by later runs). Run the command on the demo day.

## 1. BR-8 refund slabs (Exp 10 TC-B1 to TC-B3)

Account: `refunds@vrms.test`. Three Confirmed one-day bookings, all paid by
the sandbox card, on demo hatchbacks Maruti Suzuki Wagon R MH02DX8001,
MH02DX8002 and MH02DX8003 at Andheri. At the demo tariff each rental is
₹2,124.00 (₹1,800.00 plus tax at 18%) with a ₹5,000.00 deposit.

| Step | Route | Click or type | Expected on screen |
|---|---|---|---|
| 1 | `/login` | "E-mail" `refunds@vrms.test`, "Password" `Demo@1234`, "Sign in" | `/app` |
| 2 | `/app/bookings` (menu "My bookings") | | "My bookings": three rows "Maruti Suzuki Wagon R · VRMS-…", each "Confirmed", at Andheri |
| 3 | `/app/bookings/<id>` (the row collected about 3 days ahead, MH02DX8001) | "Cancel booking" | Dialog "Cancel this booking?" with "Rental refund, 100% of the rental" ₹2,124.00, "Security deposit, refunded in full" ₹5,000.00, "Total refund" ₹7,124.00 (TC-B1) |
| 4 | same | "Keep booking" | Dialog closes, nothing changed |
| 5 | the row collected about 30 hours ahead (MH02DX8002), "Cancel booking" | | "Rental refund, 75% of the rental" ₹1,593.00, "Security deposit, refunded in full" ₹5,000.00, "Total refund" ₹6,593.00 (TC-B2) |
| 6 | the row collected about 6 hours ahead (MH02DX8003), "Cancel booking" | | "Rental refund, 50% of the rental" ₹1,062.00, "Security deposit, refunded in full" ₹5,000.00, "Total refund" ₹6,062.00 (TC-B3) |
| 7 | optional, in any of the dialogs | "Your password" `Demo@1234`, "Cancel booking" | The dialog closes (there is no success message); the badge shows "Cancelled" and a "Refunds" section lists the refunds |

Step 7 moves money (append-only refund and ledger entries). Showing the
three quotes and pressing "Keep booking" changes nothing, so it can be
repeated.

## 2. BR-2 under-21 refusal (Exp 10 TC-B5)

Account: `young@vrms.test`, verified licence for Car and Two-Wheeler, aged 20
today and 21 on the seed day + 7 days ("the birthday" below).

| Step | Route | Click or type | Expected on screen |
|---|---|---|---|
| 1 | `/login` | "E-mail" `young@vrms.test`, "Password" `Demo@1234`, "Sign in" | `/app` |
| 2 | `/app/search` (menu "Find a vehicle") | "Pickup branch" Andheri; "Vehicle category" Hatchback (Car); "Pickup" two days before the birthday, 10:00; "Return" the next day, 10:00; "Search" | "Available vehicles": "… vehicles are free at Andheri from …" |
| 3 | tile "View and book" on any car | tick "I accept the rental terms above.", "Hold this vehicle and pay" | "You can’t make this booking" and "You must be at least 21 on the pickup date to rent a car (BR-2)."; buttons "Keep browsing" and "Exit". No booking is created |
| 4 | "Keep browsing", then search again with "Vehicle category" Scooter (Two-Wheeler), same dates | "View and book" (for example Honda Dio), tick "I accept the rental terms above." and "I have read the safety notice.", "Hold this vehicle and pay" | Allowed: "Pay for your booking" (minimum age for a two-wheeler is 18) |
| 5 | search a car again with "Pickup" on the birthday, 10:00 | "View and book", tick the terms, "Hold this vehicle and pay" | Allowed: "Pay for your booking" |

Steps 4 and 5 create Pending Payment bookings; leave the pay page without
paying and the 15-minute hold runs out and releases the vehicle.

## 3. R6 double booking (Exp 8)

Two browsers: a normal window as `customer@vrms.test`, an incognito window as
`changes@vrms.test`. Use dates with no demo bookings, for example the seed day
+ 12 at 10:00 to + 14 at 10:00.

| Step | Window | Route | Click or type | Expected on screen |
|---|---|---|---|---|
| 1 | normal | `/app/search` | Sign in as `customer@vrms.test`; "Pickup branch" Andheri, "Vehicle category" Any category, the dates above, "Search" | "N vehicles are free at Andheri from … to …." Note N and pick a car, for example Maruti Suzuki Baleno |
| 2 | normal | vehicle page | "View and book", tick "I accept the rental terms above.", "Hold this vehicle and pay" | "Pay for your booking" and "The vehicle is held for you for 14:5x more." Stop here; do not pay |
| 3 | incognito | `/login`, `/app/search` | Sign in as `changes@vrms.test`; same branch, category and dates; "Search" | "N−1 vehicles are free at Andheri …"; the held car is not in the list |

The hold lasts 15 minutes; after "Your hold has run out. Paying now may ask
you to hold the vehicle again." the car is offered again. Section 4 can carry
on from this pay page.

## 4. R10 declined, then approved payment (Exp 8)

On a pay page (`/app/bookings/<id>/pay`, for example the one from section 3
step 2, within its 15-minute hold):

| Step | Click or type | Expected on screen |
|---|---|---|
| 1 | "How would you like to pay?" "Card"; "Payment method (sandbox)" "Test card that is declined"; "Your password" `Demo@1234`; "Pay ₹… and hold ₹… deposit" | "Your payment was declined" and "Your payment was declined: Declined by mock gateway. The vehicle stays held until the hold expires; you can try another card." The form stays open and the password is cleared |
| 2 | "Test card that is approved"; "Your password" `Demo@1234`; "Pay ₹… and hold ₹… deposit" | The booking page: "Your booking is confirmed. Keep the pickup code safe; you will need it at the branch." with "Booking reference", "Pickup code", "Transaction" and "Invoice" |

No card number is typed: the sandbox options stand for gateway tokens.
Step 2 issues an invoice (append-only).

## 5. R7 sign-in lockout (Exp 8, SE-8)

Account: `lockout@vrms.test`, used for nothing else, so no other demo account
is locked.

| Step | Route | Click or type | Expected on screen |
|---|---|---|---|
| 1 | `/login` | "E-mail" `lockout@vrms.test`, "Password" `wrong-password`, "Sign in", four times | Each time "Unable to sign in with the details provided." |
| 2 | same | the wrong password a fifth time, "Sign in" | "Your account is locked for 15 minutes after too many failed sign-in attempts. Check your e-mail." |
| 3 | same | the right password `Demo@1234`, "Sign in" | Still "Your account is locked for 15 minutes after too many failed sign-in attempts. Check your e-mail." |

The lock lasts 15 minutes, after which `Demo@1234` signs in. To unlock at once
before a rehearsal: `python manage.py axes_reset_username lockout@vrms.test`
in `backend/`.
