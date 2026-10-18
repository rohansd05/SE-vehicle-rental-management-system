# Traceability: Guest catalogue, search filters, Rate Vehicle and doorstep delivery (Module R4)

Maps SRS 3.2 (Search.Browse, Search.Available, Search.Filter, Search.Detail,
Search.Price and the 3.2.2 stimuli), Book.Addons, Book.Deliver.Location, BR-7,
SA-2 (search and booking) and BR-13's effective dates to the code and the
tests, with Exp 2 use case 2 "Search Vehicles" (extension 3a), use case 6
"Rate Vehicle" (extension 2a), the "Add Doorstep Delivery" extend of use case 3,
D13, the Exp 4 sequence 1 messages the module touches, the Exp 5 activity
nodes and the Exp 6 process 2. SRS:
`docs/experiments/AC_2024300049_ROHAN_SE_EXP1.pdf`.

Paths are relative to the repository root. `B:` = `backend/apps/`,
`F:` = `frontend/src/`. Test names are pytest functions (file in brackets) or
Vitest `it` titles (in quotes). Test files: `B:fleet/tests/test_catalogue.py`
[catalogue], `B:fleet/tests/test_search_api.py` [search],
`B:bookings/tests/test_rate_vehicle.py` [rate], `B:bookings/tests/test_ratings.py`
[ratings], `B:bookings/tests/test_delivery.py` [delivery],
`B:bookings/tests/test_seed_ratings.py` [seed], `B:accounts/tests/test_admin_api.py`
[users]; Vitest `F:features/search/catalogue.test.tsx`,
`F:features/booking/delivery.test.tsx`, `F:features/rating/rating.test.tsx`,
`F:features/handover/delivery.test.tsx`.

Where the model lives: the review is the existing `bookings.Rating` (D13,
migration `bookings/0002_rating_and_discount`), so **no new model or migration
was needed**; the 14-day window and the 24-hour edit come from
`config/settings/business_rules.py` (`RATING_WINDOW`, `RATING_EDIT_WINDOW`).
A vehicle's average rating and rating count are computed in the same query
as the vehicle every time (subqueries, `bookings.services.with_average_rating()`),
so they are always current and never stored, as D13 decides. The brief's "keep
each vehicle's average rating and rating count updated" is met this way; a
stored column would contradict D13 (flagged, not changed).

## 1. Requirements

| Requirement | Implemented in | Tests |
|---|---|---|
| Search.Browse: an unauthenticated visitor browses and searches, but cannot book | Public routes `/search` and `/vehicles/:id` in `F:app/AppRoutes.tsx` (same `SearchPage` and `VehicleDetailPage` as `/app/…`, `F:features/search/paths.ts` keeps links on their side); "Browse vehicles" in `F:components/layout/PublicLayout.tsx`; the fleet endpoints are `AllowAny` with no authentication (`B:fleet/views.py`); booking stays `IsCustomer` (`B:bookings/views.py`). The guest's "Sign in to book" / "Register to book" (`SignInToBook` in `F:features/booking/VehicleDetailPage.tsx`) pass `from` = `/app/vehicles/{id}?period`, carried through `RegisterPage` → `VerifyOtpPage` → `LoginPage` | `test_every_visitor_may_search_with_filters`, `test_every_visitor_may_view_a_vehicle` [catalogue] (anonymous and every role); Vitest "lets a signed-out visitor search and see the rating with its count", "offers sign-in or registration instead of booking, keeping the vehicle and dates", "returns to the same vehicle and dates after signing in, ready to book", "carries the vehicle through registration and the code check to sign-in", "a customer on the public page goes to the app to book" |
| Search.Available: only vehicles that can be booked; never Under Maintenance, Unsafe or Retired (N3 retires); BR-1 buffer | `B:fleet/services/availability.py` `available_vehicles()` (unchanged rules: status from the status service's table, blocking bookings + 60 min, maintenance windows, availability date) | `test_vehicles_that_cannot_be_booked_are_never_offered` (3 statuses), `test_the_br1_buffer_still_applies` [catalogue]; `test_availability.py` (existing) |
| SA-2 in search and booking: no vehicle overdue for its preventive service, by date or km | `availability.service_overdue()` calls N3's **`maintenance.services.service_due()`** (the same BR-15 check as the handover refusal `service_overdue`; not duplicated); applied in `available_vehicles()` (hidden from search and from R2's 3a alternatives), `is_available()`, and as an explicit refusal in `lifecycle.create_booking()` and `hold_again()` (409 `service_overdue`). The detail shows `service_overdue` → "Not bookable: service overdue" | `test_a_car_overdue_by_date_is_not_offered`, `test_a_car_overdue_by_distance_is_not_offered`, `test_a_car_not_yet_due_is_offered`, `test_a_vehicle_without_a_service_on_record_is_never_overdue`, `test_the_detail_marks_an_overdue_vehicle` [catalogue]; `test_a_vehicle_overdue_for_its_service_cannot_be_booked` [delivery]; Vitest "marks a vehicle overdue for its service as not bookable" |
| Search.Filter: vehicle type, category, brand and model, fuel, transmission, seats, price range, minimum rating; sort by price or rating | `B:fleet/services/catalogue.py` `search()`, `_filtered()`, `_ordered()` (`SearchFilters`); query validated by `AvailabilitySearchSerializer` (`B:fleet/serializers.py`); UI "Refine" row in `F:features/search/SearchPage.tsx`, kept in the address | `test_filter_by_vehicle_type`, `test_filter_by_category`, `test_filter_by_brand_and_model`, `test_filter_by_fuel`, `test_filter_by_transmission_keeps_only_cars`, `test_filter_by_minimum_seats`, `test_price_range_uses_the_estimate_for_the_period`, `test_a_low_highest_price_is_refused_on_its_field`, `test_filter_by_minimum_rating`, `test_a_minimum_rating_outside_1_to_5_is_refused`, `test_sort_by_price_both_ways`, `test_sort_by_rating_puts_unrated_last`, `test_an_unknown_sort_is_refused` [catalogue]; Vitest "sends every filter and the sort to the server", "shows a highest price below the lowest next to its field" |
| Search.Price and BR-13: the estimate, the price range and the price sort use the tariff in force on the searched pickup date | `catalogue.estimates_for()` → `pricing.services.tariffs_in_force(pickup)` and `estimate()`; `calculate_price()` unchanged | `test_price_uses_the_tariff_in_force_on_the_searched_dates` [catalogue]; `test_the_estimate_uses_each_categorys_tariff_in_force` [search] (updated) |
| Search.Detail: at least four photographs, specification, tariff, free km, excess-km rate, deposit, fuel and cancellation policies, average rating, date last serviced | `VehicleDetailSerializer` (`rating_count`, `service_overdue` added); `catalogue.with_catalogue_facts()`: `last_serviced` = the latest **closed (Completed) maintenance job**'s service date, else the service on record; UI `VehicleFacts` (rating with its count, "Free distance … then … per km") | `test_last_serviced_comes_from_the_latest_closed_job`, `test_last_serviced_falls_back_to_the_service_on_record`, `test_the_detail_carries_the_rating_and_its_count`, `test_results_carry_the_rating_count` [catalogue]; `test_the_detail_shows_the_seeded_photos` [seed]; Vitest "shows the free distance and the excess-km rate" |
| 3.2.2 / UC 2 extension 3a: no match → the nearest alternatives by branch or by date | `catalogue.alternatives()`; `GET /api/v1/fleet/search/alternatives/` (`SearchAlternativesView`, `AllowAny`); UI `F:features/search/Alternatives.tsx` under the empty state, each a link to that search | `test_alternatives_by_branch`, `test_alternatives_by_date_nearest_first`, `test_no_alternatives_is_an_empty_list`, `test_alternatives_validate_like_the_search` [catalogue]; Vitest "offers other branches and nearby dates when nothing matches" |
| Book.Addons, BR-7: doorstep delivery is an add-on charged at its published daily rate | The N3-managed `AddOn` named "Doorstep delivery", priced by `calculate_price()` like any add-on (unchanged); identified by `lifecycle.is_delivery()` | `test_an_address_in_the_serviceable_area_is_booked_and_charged` [delivery] |
| Book.Deliver.Location: the address lies within the branch's serviceable area | `lifecycle.check_delivery()` (pincode in the pickup branch's `BranchServiceableArea`, which N3 admins manage) in `create_booking()` and `hold_again()`; stored in `Booking.delivery_address` / `delivery_pincode`. **The old "refused at booking" (`_refuse_delivery`, BK11) is removed.** A refusal is a 400 on `delivery_address` or `delivery_pincode`, shown next to the field (`F:features/booking/VehicleDetailPage.tsx` "Delivery address") | `test_an_address_outside_the_serviceable_area_is_refused_on_its_field`, `test_delivery_needs_an_address`, `test_delivery_needs_a_six_digit_pincode` (4), `test_without_delivery_an_address_is_not_kept`, `test_the_api_puts_the_refusal_next_to_the_field`, `test_holding_again_checks_the_area_again` [delivery]; `test_doorstep_delivery_needs_an_address` [test_lifecycle] (updated); Vitest "asks for the address only once delivery is chosen", "needs an address and a six-digit pincode before holding", "sends the address and shows the serviceable-area refusal next to the pincode", "holds the vehicle with a serviceable address" |
| BR-9 with delivery: cash only for a branch collection (R1, unchanged) | `lifecycle._choose_cash()` | `test_cash_is_not_offered_with_delivery` [delivery] |
| The delivery address on the booking, the handover screen and the confirmation e-mail | `BookingSerializer.delivery_address`/`delivery_pincode` (staff read it through the scoped bookings API); `DeliveryRow` in `F:features/handover/HandoverPage.tsx` (reads `GET /bookings/{id}/`, no rentals change); booking detail says "delivered to …"; `("booking_confirmed", 2)` appended in `B:bookings/notification_templates.py` with `{collection}` (version 1 untouched), sent by `services.notify_booking_confirmed()` | `test_the_api_stores_and_shows_the_address`, `test_the_confirmation_e_mail_names_the_delivery_address`, `test_a_branch_collection_e_mail_names_the_branch` [delivery]; Vitest "shows the delivery address", "shows no delivery row for a branch collection" |

## 2. Exp 2 use cases

| Use case step | Implemented in | Tests |
|---|---|---|
| UC 2 step 1: branch, pickup and return | `SearchPage` form (unchanged) | `search.test.tsx` (existing) |
| UC 2 step 2: optional filters for type, category, price and rating | Search.Filter row above | Section 1, Search.Filter |
| UC 2 step 3: genuinely available for the whole period | `available_vehicles()` + SA-2 | Section 1 |
| UC 2 step 4: matching vehicles with an estimated price each | `AvailableVehicleSerializer.estimate` from `estimates_for()` | `test_price_range_uses_the_estimate_for_the_period` |
| UC 2 step 5: select a vehicle to view its full detail | Tiles link to `{base}/vehicles/{id}?period` | Vitest "lets a signed-out visitor search…" |
| UC 2 extension 3a | `alternatives()` | Section 1 |
| UC 3 extend "Add Doorstep Delivery" (step 4) and Exp 5 "Address serviceable? [No] Reject address, offer branch pickup" | `check_delivery()`; the message offers branch pickup | Section 1, Book.Deliver.Location |
| UC 6 precondition: Completed, within the last 14 days | `services._check_ratable()`: own booking, `Completed` (set by N2's `states.complete_booking()`), now ≤ `returned_at` + `RATING_WINDOW` | `test_a_booking_returned_more_than_14_days_ago_is_refused`, `test_a_booking_returned_just_under_14_days_ago_may_be_rated`, `test_another_customers_booking_is_not_found`, `test_the_service_refuses_someone_elses_booking` [rate] |
| UC 6 refusals, each with its message | `REFUSED_STATUS`: Cancelled, No-show, Active (and any other status); 409 `rating_refused` with the message | `test_a_booking_that_is_not_completed_is_refused` (Cancelled, No-show, Active, Confirmed) [rate]; `test_only_completed_bookings` [ratings] (updated); Vitest "shows the server's refusal in its words" |
| UC 6 step 1: the system invites the actor to rate | `BookingDetailSerializer.rating_open_until` (set only while an unrated Completed booking may be rated); `F:features/rating/RatingSection.tsx` "Rate this rental" on the booking page | `test_the_booking_invites_a_rating_while_it_can_be_given` [rate]; Vitest "says nothing about rating a %s booking" |
| UC 6 step 2: vehicle and service rated separately, 1 to 5, optional comment | `RateBookingSerializer`; `Rating` check constraints; `submit_rating()`; `POST /api/v1/bookings/{id}/rating/` (`BookingRatingView`, `IsCustomer`) | `test_scores_run_from_1_to_5` (6), `test_the_comment_is_optional` [rate]; `test_scores_must_be_one_to_five` [ratings]; Vitest "invites a rating and sends both scores and the comment", "asks for both scores before sending" |
| UC 6 step 3 and post-condition: stored, the average recalculated | `Rating` row + audit "Create"; average and count computed per query | `test_a_completed_booking_is_rated_and_the_average_is_current` [rate]; `test_average_is_computed_not_stored` [ratings] |
| UC 6 extension 2a: already reviewed → edit only within 24 hours | `edit_rating()` (now ≤ `created_at` + `RATING_EDIT_WINDOW`, audit "Update" with before and after); `PATCH /api/v1/bookings/{id}/rating/`; `RatingSerializer.editable_until`; "Edit review" while editable | `test_a_booking_is_rated_only_once`, `test_the_review_is_edited_within_24_hours_and_audited`, `test_the_review_cannot_be_edited_after_24_hours`, `test_editing_needs_a_review_first`, `test_the_detail_says_until_when_the_review_is_editable` [rate]; Vitest "edits the review within 24 hours with PATCH", "no longer offers an edit after 24 hours" |
| UC 6 permissions (SE-4): only the customer | `BookingRatingView.permission_classes = [IsCustomer]`; the booking must be the caller's (404 otherwise) | `test_staff_roles_cannot_rate` (staff, technician, manager, admin × POST, PATCH), `test_an_anonymous_visitor_cannot_rate`, `test_the_customer_role_is_allowed` [rate] |

## 3. Exp 4, Exp 3, Exp 5 and Exp 6

| Element | Where | Tests |
|---|---|---|
| Exp 4 seq. 1 message 3 `Vehicle.check_availability()` | `is_available()` now also refuses SA-2 | `test_a_car_overdue_by_date_is_not_offered` (asserts `is_available` is False) |
| Exp 4 seq. 1 message 4 `Tariff.calculate_price()` | Unchanged; the delivery add-on is one more `AddOnCharge` (BR-7) | `test_an_address_in_the_serviceable_area_is_booked_and_charged` |
| Exp 3 `Customer.search_vehicle()` | `catalogue.search()`; `GET /api/v1/fleet/search/` | Section 1 |
| Exp 3 `Branch.serviceable_areas` | `BranchServiceableArea` rows, read by `check_delivery()` | Section 1, Book.Deliver.Location |
| Exp 5 phase 1 "Browse catalogue and view tariffs", "Proceed to book? → Register or log in", "Offer alternatives by branch or date" | Guest catalogue; sign-in/register round trip; `Alternatives` | Section 1 |
| Exp 5 phase 2 "Select add-ons and doorstep delivery", "Address serviceable?" | Booking form delivery fields; `check_delivery()` | Section 1 |
| Exp 6 process 2 "Search Vehicles and Check Availability" (Guest/Customer → search criteria; D2 fleet, D3 tariff) | `catalogue.search()` reads vehicles (D2), tariffs (D3), ratings (D4 bookings) | Section 1 |

## 4. Follow-ups from Module N3

| Item | Where | Tests |
|---|---|---|
| `cancel_booking()` takes an optional `actor` (default: the customer) and `reason`; the blacklist cancellation records the Administrator | `B:bookings/services.py` `cancel_booking(…, actor=None, reason="")`; `states.mark_cancelled(…, reason=)`; `B:accounts/admin_services.py` `cancel_for_blacklist()` passes `actor` and `CANCELLED_FOR_BLACKLIST_REASON`. The extra "Booking Cancelled For Blacklist" entry is removed: R2's "Booking Status Changed" now carries the Administrator and the reason, so it was a duplicate | `test_a_cancellation_records_the_customer_by_default`, `test_a_cancellation_records_the_given_actor_and_reason` [delivery]; `test_a_confirmed_booking_is_cancelled_through_r2_with_the_admin_as_actor` [users] (updated); R2's `test_changes.py` and `test_changes_api.py` unchanged and passing |
| Optional `Customer.blacklist_reason` | **Not done** (time); N3-P2's audit-entry reason stays | – |

## 5. Demo data

- Plain `seed_demo`: every demo vehicle (chassis `DEMO…`, 34 of them) gets
  photographs up to four (`B:fleet/seed.py` `seed_demo_photos()`, 136 rows);
  the five branches' serviceable areas and the "Doorstep delivery" add-on were
  already seeded. Count test: `VehiclePhoto: 136` in
  `B:core/tests/test_seed_demo.py`. No append-only rows; `--reset` works.
  Demo accounts, jobs 1 to 3 and N3's job count are unchanged.
- `seed_demo --reports` (`B:bookings/seed_ratings.py`): reports@vrms.test rates
  five of its past Completed bookings (its booking returned four days ago stays
  unrated); rating@vrms.test (password Demo@1234) has one Completed booking
  returned three days ago (may be rated) and one returned 23 days ago (refused).
  Both go through R3's `_seed_booking()` (invoices and ledger, hence behind the
  flag). R3's seed counts updated (`REPORTS_ADD`, `INVOICES = 12`).
- Tests: `test_every_demo_vehicle_has_four_photos_and_the_delivery_data`,
  `test_the_rating_demo_rates_and_invites` [seed]; `B:reports/tests/test_seed.py`.

## 6. Proposed items (awaiting team approval)

| # | Item | Proposal |
|---|---|---|
| R4-P1 | "Nearest" alternatives (UC 2 3a) | Other branches with a match for the same period (by name), then the same branch with the period moved by 1, −1, 2, −2, 3, −3 days, at most 3 dates (`SEARCH_ALTERNATIVE_DAYS`, `SEARCH_ALTERNATIVE_DATES_SHOWN`). The same filters apply. |
| R4-P2 | Delivery on a changed booking (R2) | A change has no address, so it neither adds nor removes doorstep delivery (`delivery_unchangeable`); a delivery kept across a new pickup branch must lie in that branch's areas. |
| R4-P3 | Demo photographs | Generated "Demo photo" cards (side and registration), not photographs: one licensed photo per model exists, and B12 forbids a representative photo posing as the vehicle. An Administrator replaces them (Fleet.Add). |
| R4-P4 | Serviceable area | Matched on the six-digit pincode of the address (Appendix A "pincode/locality"). |
| R4-P5 | Rating refusal status | 409 `rating_refused` with the reason (the booking's state, not the input, is at fault). |
| R4-P6 | SA-2 "overdue" in search | Judged today (as at handover), not at the pickup date. |
| R4-P7 | Tariff in search vs. in the quote | Search prices at the tariff in force on the pickup date (as asked); the booking quote and `create_booking()` still price at the tariff in force now (`pricing.services.quote()`, unchanged). They differ only while a new tariff is scheduled between now and the pickup. |

## 7. Not built

- ~~The delivery address on the **branch bookings list**~~ and ~~the pickup
  reminder saying "collect at the branch" for a delivered booking~~: both built
  in Module N4 (`docs/traceability-deploy.md`, section 4).
- `Customer.blacklist_reason` (optional N3 follow-up).
