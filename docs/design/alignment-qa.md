# Alignment, photo and type QA (Stage 4.8, 12 Oct 2026)

Binding decision B13 (`ui-brief.md`). Every number below was measured in
Chromium (Playwright, exact viewport widths, demo data seeded through the
UI) on the running dev server, with `getBoundingClientRect` and
`getComputedStyle`. Contrast was computed from the real photo pixels: the
served image file is drawn to a canvas at its rendered size, `object-fit`
and `object-position`, the overlay tokens and scrims are composited over
each pixel under every text box, and the lightest composite pixel is taken.
Widths: 1440, 1280, 1024, 768, 390 and 320 unless a section says
otherwise.

## 1. Contrast of text on photos (WCAG AA)

Only two places put text over a photo, and only from 1024 px; below that
the text sits on the canvas. The auth panel's text sits on solid petrol
(`--primary-hover`, white 10.3:1), never on its photo.

| Page | Photo | Text | 1440 | 1280 | 1024 | 768, 390, 320 |
|---|---|---|---|---|---|---|
| Landing hero | hero-1 (tint 30 %, text on the 84 % scrim panel) | Agency name (large) | 8.69:1 | 8.54:1 | 8.72:1 | text on canvas |
| | | Intro paragraph | 8.90:1 | 8.85:1 | 8.91:1 | text on canvas |
| | | "Sign in" (white outline button) | 9.10:1 | 9.05:1 | 9.01:1 | text on canvas |
| Landing call to action | cta-band-1 (tint 30 %, scrim fade from the left) | "Create your account" (large) | 8.35:1 | 8.37:1 | 8.38:1 | text on canvas |
| | | "Sign in" (white outline button) | 8.78:1 | 8.78:1 | 8.38:1 | text on canvas |

Lowest per page: landing 8.35:1. No cover failed, so no local re-grade
was needed. The light tint (30 %) alone is not relied on for text.

## 2. Subject visibility per photo slot

Each photo's subject box and optional focal point are in
`frontend/scripts/image-sources.json` (copied into
`src/assets/images/manifest.json`). `fitPhoto` crops only background.
Check: the subject box is fully inside the frame with a margin of at least
4 % of the frame side, or the photo's own margin where the subject already
runs closer to the photo's edge (for example a car's bumper touching the
frame in the original).

| Slot | Photos | Widths checked | Result |
|---|---|---|---|
| Landing hero | hero-1 | 1440 to 320 | Pass (cover; the car is 52 % to 76 % down at 1440, under the scrim panel's bottom edge) |
| Landing split rows | band-bookings-1, band-maintenance-1 | 1440 to 320 | Pass (own shape, nothing cropped) |
| How it works | step-account, step-licence, step-search, step-collect | 1440 to 320 | Pass (3:2 frames) |
| Category row | cat-hatchback-2, cat-sedan-2, cat-suv-1, model-tvs-jupiter-1, cat-motorcycle-2 | 1440 to 320 | Pass (3:2, cover) |
| System status | band-dashboard-1 | 1440 to 320 | Pass (own shape) |
| Call to action | cta-band-1 | 1440 to 320 | Pass (3:1 cover from 1024; own shape below) |
| Auth panel | auth-2 | 1440, 1280, 1024 (hidden below) | Pass (16:9 cover) |
| Search tiles | the four vehicles in the demo search | 1440 to 320 | Pass: Bajaj Platina and Honda Dio cover; Maruti Suzuki Baleno and Toyota Innova Crysta shown whole (`contain`) because their bodies fill the photo's width |
| Vehicle page | model-maruti-suzuki-baleno-1 | 1440 to 320 | Pass (own shape) |
| Page-header photos | band-bookings-1, band-licence-1, band-maintenance-1, band-technician-1, band-licence-checks-1, band-clearances-2, band-dashboard-1 | 1440, 1280 (hidden below 1280) | Pass (own shape) |
| Payment rail | band-payment-1 | 1440, 1280, 1024 (hidden below) | Pass (4:3 cover) |
| Quiet photos | band-quiet-2 (help, 403, 404, credits, "Not available yet") | 1440 to 768 where shown | Pass |
| Credits thumbnails | all 43 photos | 1440 | Pass (4:3; 18 shown whole) |

No slot failed. The fit is recomputed whenever a frame resizes.

## 3. Font-size audit

Every visible text node's computed size, at 1440, 1280, 1024, 768, 390 and
320, on every page in section 5.

- Before: mono numbers (prices, dates, plates, IDs) rendered at 15 px next
  to 16 px body text (the fixed `--text-num` 0.9375rem).
- Fix: `--text-num` is now `1em`, so numbers take their context's size: 16 px
  in body text, 14 px in secondary text, 13 px in labels. No other token
  changed.
- After: sizes in use are 13 (labels, pills, table headers), 14
  (secondary), 16 (body, inputs, buttons), 19 (lead, subsection) and the
  heading scale (22 to 76). Nothing below 13 px on any page or width. Every
  input, select and textarea is 16 px.

## 4. Alignment measurements and fixes

Deviations over 1 px found, fixed through shared components or tokens,
then re-measured:

| Page, width | Before | Fix | After |
|---|---|---|---|
| Every page after an in-app navigation | `<main>` focus scrolled the page 65 px, hiding the title under the sticky top bar | `useRouteFocus` focuses without scrolling and returns to the top (unless the address has a `#topic`) | title fully visible; `scrollY` 0 |
| Payment, 390 | rail heading and price table 4 px past the column's right edge (363 vs 359) | `RAIL_LAYOUT` (`src/lib/layout.ts`), shared by vehicle, booking and payment pages, with `minmax(0, 1fr)` | 16 to 359, on the gutter |
| Payment, 320 | page 58 px wider than the screen (pay button label) | Button labels may wrap when longer than their container (`max-w-full`, 44 px minimum height) | no overflow; one-line buttons stay 44 px |
| Booking detail, 320 | 38 px overflow (download-invoice button) | same | no overflow |
| Licence checks, 320 | 65 px overflow (truncated line widened its grid track) | queue and job lists use `minmax(0, 1fr)` columns | no overflow |
| My bookings, 768 | title wrapped one word per line (86 px wide) beside the header photo | header photos show from 1280 px only | title 277 px, one line |
| Maintenance, 1024 | "Maintenance" broken mid-word (198 px) | same | one line (483 px) |
| Landing call to action, 1024 and up | heading centred in its block, 28 px off the gutter | left-aligned on the gutter | heading and buttons both at 32 |

Checks that passed without change:

- Landing hero centre lines (heading, intro, buttons, scroll cue): 712.4,
  632.4, 504.4, 376.4 and 187.6 px at 1440, 1280, 1024, 768 and 390; the
  viewport centre is 712.5, 632.5, 504.5, 376.5 and 187.5.
- Call to action below 1024 px: heading and buttons share one centre (376.4
  at 768, 187.6 at 390).
- Image rows: steps 310 x 207 at 1440 (270 x 180 at 1280, 206 x 137 at
  1024), gaps 40, one top line; categories 256 x 171 (224 x 149, 173 x 115),
  gaps 20, one top line; search tiles equal widths and tops at every width
  (photos 348 x 232 at 1440).
- Split rows: photo and list centres within 0.1 px at 1024 and 1440 (440.0
  vs 439.9); stacked below 1024.
- Page edges: titles, photos, rails and tables start on the page gutter
  (304 at 1024 and up with the sidebar, 296 at 768, 16 at 390 and 320);
  the hero and call-to-action photos reach both viewport edges (0 to the
  scrollbar).
- No horizontal overflow on any checked page at any width after the fixes.
- Images: explicit width and height or aspect ratio on every photo; no
  stretching (`object-fit` is always `cover` or `contain`); alt text
  unchanged.

## 5. Pages and widths checked

| Tier | Pages | Widths |
|---|---|---|
| 1 | Landing | 1440, 1280, 1024, 768, 390, 320 |
| 2 | Sign in, register, verify | all six |
| 3 | Search results, vehicle page, booking detail, payment, my bookings | all six |
| 4 | Licence, licence checks, maintenance list, report a fault, job detail (staff and technician), technician jobs, clearances, dashboard | all six |
| 5 | Help, credits, 403, 404, "Not available yet" | all six |

Also at 1920 px: landing, sign in, help, credits, search results, my
bookings and payment (no overflow, titles on one line, landing photos all
`cover`); the full subject and alignment probe did not run at 1920.

Not checked: the other pages at 1920 px; the booking form's add-on and discount states, dialogs and the
licence review page; Safari and Firefox; reduced-motion rendering beyond
the CSS rule.

## 6. Text-only regions that received photos

| Region | Photo |
|---|---|
| Landing "Book online, collect at the branch" (features grid) | band-bookings-1 beside the list |
| Landing "For branch teams" | band-maintenance-1 beside the list (sides flipped) |
| Landing "System status" | band-dashboard-1 framed above the list |
| Landing "How it works" (already had a photo per step) | unchanged, frames now 3:2 |
| Landing final call to action | cta-band-1, now with the whole car in view |

Regions still without a photo, by rule: forms, tables, queues and
record-work screens; the profile page; operational pages below 1280 px (the
header photo would squeeze the title and actions). No new photos were
downloaded: every new slot reuses one of the 43 already licensed photos.
