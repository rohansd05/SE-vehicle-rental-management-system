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

---

# Stage 4.9: image-led page headers and the larger type scale (12 Oct 2026)

Binding decision B14 (`ui-brief.md`). Measured in Chromium (Playwright) on
the running dev server with the demo accounts, at 1536 x 730 (the reported
real viewport: 1920 x 1080 at 125 %), 1440 x 900, 1280 x 800, 1024 x 768,
768 x 1024, 390 x 844 and 320 x 640. One probe ran on every page and width:
the computed size of every visible text node, the line boxes of every text
node (single-word lines, references and figures broken inside a token),
every photo's subject box against its frame, contrast on real pixels for
text over photos, the header frame's geometry, edges against the content
container, columns more than 200 px shorter than their neighbour, blank
space below the content, and horizontal overflow. 245 page and width
combinations, about 700 photo-slot checks.

Pages: landing, sign in, register, verify, help, photo credits, 404; as the
customer: home, search results, vehicle page, my bookings, booking detail,
payment, driving licence, my profile, 403; as branch staff: home,
maintenance, report a fault, job detail, licence checks, licence review, a
"Not available yet" page; as the technician: home, maintenance jobs, job
detail; as the branch manager: home, maintenance; as the administrator:
home, unsafe clearances, licence checks.

## 1. Page header frame (after)

Signed-in pages (content beside the 296 px sidebar). The photo sits inside
the frame's 1 px border, so 0.8 px is flush. The text is vertically centred
against the photo within 0.1 px on every page and width.

| Width | Frame | Photo (share) | Photo to frame edges (top, right, bottom) | Gap, text to photo | Text column |
|---|---|---|---|---|---|
| 1536 | 1161 x 348 | 580 x 347 (50 %) | 0.8, 0.8, 0.8 | 32 (`--header-gap`) | 516 |
| 1440 | 1065 x 319 | 532 x 318 (50 %) | 0.8, 0.8, 0.8 | 32 | 468 |
| 1280 | 905 x 280 | 452 x 278 (50 %) | 0.8, 0.8, 0.8 | 32 | 388 |
| 1024 | 649 x 280 | 324 x 278 (50 %) | 0.8, 0.8, 0.8 | 32 | 268 |
| 768 | 409 wide, photo above the text | 407 x 229 (16:9) | 0.8 top, left, right | n/a | 345 |
| 390 | 343 wide | 342 x 228 (3:2) | 0.8 | n/a | 311 |
| 320 | 273 wide | 271 x 181 (3:2) | 0.8 | n/a | 241 |

Public pages (help, credits, 404; no sidebar): 1457 x 360 at 1536, 1361 x
360 at 1440, 1201 x 360 at 1280, 945 x 283 at 1024, the photo 50 % each. A
frame grows past its minimum when its text needs it (403: 420 px at 1536).

Before: a 192 x 128 thumbnail at the right end of the title row, from
1280 px only, with an empty gap of several hundred pixels between it and a
short title.

## 2. Type (after)

Smallest visible text per width, over all pages: 16 px at 1536, 1440 and
1280; 15.6 px at 1024; 15.1 px at 768; 15.0 px at 390 and 320 (secondary
text and pills, at their floor). Body text, inputs, buttons, sidebar and
top bar: 18 px at 1440 and 1536, 17.6 at 1280, 17 at 1024, 16 on phones.
Field labels and table headers: 16 px everywhere. Inputs: 16 px or more
everywhere. Page titles: 56 px at 1440 and 60 px at 1536 in plain headers;
in image-led headers sized from the frame, 49 px at 1440 and 53 px at 1536.
Subheadings: 23 to 24 px at 1440 and 1536. Nothing below 15 px on any page
at any width. Buttons, inputs and selects: 48 px.

Before (Stage 4.8 tokens): body 16 px, secondary 14 px, labels 14 px, pills
and list meta 13 px, page titles 36 px, controls 44 px.

Mono figures: measured in Chromium, IBM Plex Mono and IBM Plex Sans share a
0.52 em x-height and 0.70 em caps; Plex Mono's figures are 0.71 em against
0.72 em, so `--text-num` is 1.02 em.

## 3. Fixes found by the probe (before, after)

| Page, width | Before | Fix (shared component or token) | After |
|---|---|---|---|
| My bookings, 1536 | Reference broke as "VRMS-" / "20261011-0001"; the date range wrapped inside a date; once kept whole, the dates ran into the branch column | Reference in a no-wrap span; pickup and return as two whole lines; content-sized columns from 1280 px, stacked rows below | Whole tokens, no overlap |
| Home and two-word titles, 1024 to 1536 | "Welcome, Demo Customer" one word per line in a 409 px column at 1440; "Maintenance jobs" and "Unsafe clearances" on two lines at 1440 and 1536 | 50/50 frame; the header title sized from the frame (`--text-header-title`, `--text-header-title-split`; measured: the longest two-word title is 8.73 em) | One line, or two lines of two or more words |
| Booking detail, 1024 | VRMS, TXN and INV references broken across lines in a 137 px value column | Facts stack label above value until their column is 28 rem (container query); values never wrap | Whole tokens |
| Search results, 768 | Two tiles in 409 px; "No ratings yet" one word per line | Tile columns follow the content width (container queries: two from 576 px, three from 896, four from 1280) | One column at 768 |
| Header frame, 1024 | A fixed height clipped the 404 and credits text (photo 319 px in a 283 px frame) | A minimum height instead | The frame grows with its text |
| Header frame, public pages at 1440 and 1536 | 384 px tall | Cap at 22.5 rem | 360 px |
| My profile, 1280 | Form column 177 px; "Change password" wrapped | Photo rail from 1536 px; settings label column 14 rem (16 rem from 1536) | No single-word lines or overflow at 1280 (probe) |
| Report a fault, 1536 | Header frame 672 px (the page was capped at the form's width) | The cap moved to the form | Frame 1161 px |
| Top bar, 320 (public) | Register button 1 px past the edge | Top-bar clusters never shrink or wrap; the agency name truncates | No overflow |
| Top bar, 390 (signed in) | Sign out cut off | Decorative initials hidden below 640 px (the screen-reader text stays) | No overflow |
| Top bar, 768 (branch manager) | 5 px overflow | Name and role text from 1024 px | No overflow |
| Landing, 320 | "[Agency Name]" one word per line | Display token 30 px at 320 | One line |
| Photo credits, 320 | Title one word per line | Title floor 32 px; header padding 16 px on phones | One line |
| Home tiles, 320 | "Maintenance jobs" one word per line | Tile padding 16 px and no chevron on phones | One line |
| Sign in, register, verify, below 1024 | Up to 380 px blank below a short form | The auth photo runs full width above the form | Filled |
| Sign in, 1024 and up | 353 px beside the short form | The form at the top beside the sticky photo panel (centring pushed the button to the fold at 1536 x 730) | The panel is a rail |
| 404, 403 | A short main column beside a photo and links (up to 378 px) | Quiet photo in the image-led header; "Where to go" a full-width band | Filled |
| Help | The rail 273 to 315 px shorter than the topics | "Where to go" a sticky rail beside the topics | Rail |
| Photo credits | 9,962 px blank beside the rail; 96 x 72 thumbnails | A full-width grid of photo-led tiles (3:2), "Where to go" below | Filled |
| "Not available yet" | Up to 332 px blank below | Image-led header and the "Where to go" band | Filled |
| Driving licence, my profile | Up to 360 px beside the settings label column | The label column sticks while its content scrolls (`SETTINGS_ROW`, `SETTINGS_LABEL`) | Rail |
| Home (customer) | Four link rows, the lower half empty | 2 x 2 image-led destination tiles from 1024 px | Filled |

## 4. Subject, contrast and edges (after)

- Subject visibility: every photo slot passes at all seven widths (header
  photos, destination tiles, vehicle tiles, the vehicle page, landing,
  auth, empty states, credits). The licence header now uses
  `step-licence-1` (hands on the wheel), because `band-licence-1`'s driver
  fills the photo's height and could not fill a header frame whole;
  `band-licence-1` leads the home tile instead, at 3:2. The workshop
  photo's subject box was narrowed to the car on its lift so it fits the
  header frame at every width. Clearances uses the car back on the road
  (`cta-band-1`); the bonnet-up photo (`band-clearances-2`) leads its home
  tile.
- Contrast: text over a photo only on the landing hero and call to action;
  lowest 8.0:1 at 1536 and 8.3:1 at 1440, 1280 and 1024.
- Edges: no header frame, photo, table, list, form, rail or heading outside
  the content container on any page at any width; no horizontal overflow.

## 5. Not fixed, and not checked

- "Booking VRMS-20261011-0001" (the booking detail title) is two lines below
  1024 px, each token whole: one line would need about 13.5 em, a 20 px
  title at 320.
- Short queues on tall screens: licence checks with one pending licence
  leaves 206 to 279 px below the list at 1440 x 900, 1280 x 800 and
  768 x 1024 (none at 1536 x 730). The space depends on how many licences
  are waiting; nothing was added to fill it.
- Not checked: 1920 px with the full probe; the booking form's add-on and
  discount states, dialogs, the licence form in edit mode and the job
  record-work form while editing; Safari and Firefox; reduced motion beyond
  the CSS rule.
