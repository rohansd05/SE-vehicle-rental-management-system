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
| Landing hero | hero-1 (tint 30 %, text on the 84 % scrim panel) | Brand name (large) | 8.69:1 | 8.54:1 | 8.72:1 | text on canvas |
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
| Top bar, 320 (public) | Register button 1 px past the edge | Top-bar clusters never shrink or wrap; the brand name truncates | No overflow |
| Top bar, 390 (signed in) | Sign out cut off | Decorative initials hidden below 640 px (the screen-reader text stays) | No overflow |
| Top bar, 768 (branch manager) | 5 px overflow | Name and role text from 1024 px | No overflow |
| Landing, 320 | The placeholder brand name (before Veyora, D24) one word per line | Display token 30 px at 320 | One line |
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

---

# Stage 4.10: Veyora, the tagline and the landing hero panel (12 Oct 2026)

Decision D24 (`docs/decisions.md`). Measured in Chromium (Playwright) on the
running dev server, signed out, at 1920 x 1080, 1536 x 730, 1440 x 900,
1280 x 800, 1024 x 768, 768 x 1024, 390 x 844 and 320 x 640.

## 1. Hero panel opacity

Final token: `--hero-panel-bg` = petrol (`--primary-hover`) mixed with 25 %
ink, at **57 %** opacity (was the 84 % `--photo-scrim`). Border: one
hairline in `--hero-panel-border` (20 % white); radius 6 px; no blur, no
backdrop filter. The photo, its position, focal point and the 30 %
overlay outside the panel are unchanged.

How it was found: every pixel of the real photo behind each text block was
composited with the 30 % overlay and the panel at every opacity from 30 %
to 90 %, and the lightest result taken.
- **Pure petrol:** the paragraph at 1536 (over the mist) needed 60 % to
  reach 4.8:1 (4.5 plus the 0.3 margin).
- **No text shadow:** a halo cannot be measured as a change of background
  on real pixels, so it was not used.
- **Darker tone:** petrol with 25 % ink reached the target at 55 % in the
  first layout.
- **Final opacity:** once the wordmark sat on one line, the paragraph moved
  over a lighter patch (4.76:1 at 55 %), so the opacity rose to 57 %.

The outline button's border went from 60 % to 80 % white so it keeps 3:1
against the translucent panel.

| Text block (white) | Size at 1536 | 1920 | 1536 | 1440 | 1280 | 1024 |
|---|---|---|---|---|---|---|
| Wordmark "Veyora" (large, 3:1) | 76 px / 800 | 7.40 | 7.14 | 7.66 | 7.66 | 7.07 |
| Tagline (large, 3:1) | 36 px / 500 italic | 7.60 | 7.34 | 7.39 | 7.53 | 7.48 |
| Paragraph (4.5:1) | 22.9 px / 400 | 7.09 | 4.95 | 7.50 | 7.29 | 7.72 |
| "Sign in" text (4.5:1) | 18 px / 500 | 7.87 | 5.54 | 8.16 | 7.94 | 8.07 |
| "Sign in" border (non-text, 3:1) | 80 % white | 5.64 | 4.36 | 5.90 | 5.84 | 5.75 |

The lowest is the paragraph at 1536, 4.95:1 (margin 0.45). Below 1024 px
there is no panel: the text stands on the canvas (the tagline in
`--primary`, 7.4:1). The "Create an account" button is ink on white,
independent of the photo.

## 2. Panel geometry

- **Width:** content clamped at 68 rem; panel 1088 px wide from 1280 px,
  945 at 1024.
- **Paragraph:** two balanced lines at 768 px and wider (last line 773 of
  990 px at 1536; no single word alone). Four lines at 390 and five at
  320, on the canvas.
- **Padding:** 48 px on the sides and bottom, 36 px at the top, because the
  wordmark carries 12 px of its own space above its capitals. Measured
  margins: 48 px from the panel's top to the wordmark's cap height, 49 px
  from the buttons' bottom to the panel's bottom, at 1024 to 1920.
- **Centre lines:** panel, wordmark, tagline, paragraph and buttons share
  one centre within 0.1 px of the viewport's at every width. At 1536: 760.4
  for each, against a viewport centre of 760.5.
- **The photo:** identical before and after at 1536, 1440 and 1024 (frame,
  image box, `cover`, object-position, source file, 30 % overlay). At 390
  the stacked photo keeps its size and crop (343 x 229, `cover`, 50 % 50 %)
  but sits 54 px lower, under the tagline and the larger phone wordmark.
- **The car:** at 1536 x 730 the hero is only 658 px tall, so the panel's
  lower part overlaps the car's roof. Those pixels are part of the
  measurements above.

## 3. Wordmark and tagline sizes

| Place | Wordmark | Tagline |
|---|---|---|
| Landing hero | `--text-display`: 48 px at 320 and 390, 60 at 768, 69 at 1024, 76 from about 1150 | `--text-tagline-hero` 500: 24 px at 320 and 390, 26 at 768, 30 at 1024, 33 at 1280, 35 at 1440, 36 from 1536 (about half the wordmark) |
| Final call to action | (the heading; the name when signed in) | `--text-tagline` 500: 18 px at 320 and 390, 19 at 768, 20 at 1024, 21 at 1440 and 1536, 22 at 1920 |
| Public footer | `--text-brand` 22 to 26 px | `--text-tagline` 500, as above |
| Sign-in and register panels | `--text-display-sm` | `--text-tagline` 500 |
| App sidebar | `--text-brand` | `--text-tagline-sm` 400: 15 px, one line, not clipped |
| Top bar, drawer | `--text-brand` | not shown |

Every wordmark and tagline is one line at every width from 320 to 1920 (no
clipping, no horizontal overflow). The tagline is IBM Plex Sans's own
italic (`wght-italic.css`; the loaded face reports `font-style: italic`),
`font-synthesis: none`. Contrast where it is not on a photo (calculated from the token colours): white on
solid petrol in the auth panel 10.3:1; `--ink-muted` on the canvas (footer)
7.1:1 and on the sidebar 6.6:1. On the call-to-action band over the photo:
8.7:1 at 1024 to 1536.

## 4. Name and titles

- **Page titles:** "<Page> - Veyora" (for example "Welcome, Demo Customer
  - Veyora"); the landing page "Veyora - Your Ride, Your Rules".
- **Brand links:** the brand link's accessible name is "Veyora" in the
  sidebar, the top bar and the public header.
- **No placeholder left:** the bracketed default name no longer appears in the frontend; the
  placeholder is recognised by its shape (a name in square brackets) and
  replaced by the Veyora fallback until `AGENCY_NAME` is set.

## 5. Not checked

- **The live backend name:** the running backend still returns the
  placeholder. Your `backend/.env` already reads `AGENCY_NAME=Veyora`, so
  the server needs a restart; until then the UI shows the fallback.
- **Signed-in variants:** the signed-in landing and call to action (the
  name as the heading) were not measured.
- **Browsers:** Safari and Firefox.
- **Print and PDF:** not re-checked (the tagline is not used there).

---

# Stage 5: staff, technician, manager and administrator pages (12 Oct 2026)

Measured in Chromium (Playwright) on the running dev server, signed in as
each demo account, at 1920 x 1080, 1536 x 730, 1440 x 900, 1024 x 768,
768 x 1024, 390 x 844 and 320 x 640. The probe from Stage 4.9 ran on every
route and width, extended with cumulative layout shift (CLS, while the
images load). No record was created, changed or deleted: every state shown
comes from the seeded data.

## 1. Routes checked (31 routes x 7 widths)

| Role | Routes |
|---|---|
| Branch staff | home, licence checks, licence review (licence 2), maintenance, report a fault (form only, not submitted), job 1 (Scheduled), handover and return, branch bookings, my profile |
| Technician | home, maintenance jobs, job 1 (Scheduled: Start job in the rail), job 2 (Completed: "Work recorded"), my profile |
| Branch manager | home, maintenance, job 3 (awaiting clearance), branch bookings, reports, my profile |
| Administrator | home, licence checks, maintenance, job 3 (awaiting clearance: approve in the rail), unsafe clearances, fleet, tariffs, users, reports, audit log, my profile |

The customer pages were measured again after the shared changes (Field,
label line height, loading state, dialog width): no new issues.

## 2. Results (after)

- **Type:** nothing below 15 px on any route at any width. The one 15 px
  item at every width is the sidebar tagline, at its floor by design.
  Body, buttons and inputs are 16 to 18 px; inputs are 16 px or more
  everywhere.
- **Header frames:**
  - Full variant (homes, placeholders): 1161 x 348 at 1536, 1065 x 319 at
    1440, the photo 50 %.
  - Compact variant (queues, report a fault): 200 px at 1440 (1065 x 200,
    photo 447 x 198, 42 %), 209 to 224 px at 1536, 240 px at 1920, 217 to
    249 px at 1024.
  - Both: photo flush to the frame (0.8 px inside the 1 px border), gap
    32 px, text centred against the photo within 0.1 px.
  - The one compact header over 240 px at 1440 is unsafe clearances,
    278 px: its description takes three lines.
- **Subject visibility:** every photo slot passes at every width after one
  change (see 3).
- **Contrast:** no text sits on a photo on these pages (header text sits
  on the canvas-sunken half; home tiles put their text under the photo:
  17.1:1).
- **Edges and overflow:** no frame, photo, table, list, form, rail or
  heading outside the content container; no horizontal overflow from 320
  to 1920 on any route.
- **Layout shift:** CLS 0.000 to 0.008 on every route but unsafe
  clearances at 1536 x 730 (0.055: the two skeleton rows are replaced by
  the single real row). All are under the 0.1 "good" threshold; photos
  never shift anything (explicit width and height, or a fixed frame).
- **Form labels:** baselines measured on report a fault at 1536. With the
  label line height at 1.5, each label's baseline is within 0.75 px of the
  control's text baseline (calculated from IBM Plex Sans's ascent and
  descent; text-box centres differ by 1.2 px because the face's ascent and
  descent are unequal). Labels start at x 328 and controls at x 544 on
  every row.
- **Rail tops:** at 1024 the rail's first item and the main column's first
  heading share one top line.

## 3. Fixes found by the probe (before, after)

| Route, width | Before | Fix | After |
|---|---|---|---|
| Licence checks, 768 | Customer name one word per line in a 28 px column; the date column took the width | Row columns follow the list's own width (container query, 36 rem), not the screen | Stacked at 768 (the content is 409 px beside the sidebar) |
| Maintenance, 768 | 44 px horizontal overflow (three columns in 409 px) | Same | No overflow |
| Technician home, 1440 and 1536 | Header photo (`band-clearances-2`): the raised bonnet cut at the top (0 px margin) | The workshop photo (`band-maintenance-1`); the bonnet photo stays on its 3:2 home tile | Whole subject |
| Report a fault, 1536 | Job type and Severity side by side, so their label columns collided; labels centred on the textarea's middle | Paired fields become rows once the form is 48 rem wide; `items-start` on field rows | One label column, labels on the first text line |
| Report a fault, 1536 | Label text-box centres 1.2 px off the control | Label line height 1.4 to 1.5 | Baselines within 0.75 px |

## 4. What changed on these pages

- **Queues** (maintenance for staff, manager and admin; maintenance jobs;
  licence checks; unsafe clearances):
  - The bordered card rows became shared divider rows.
  - The filter and the count share one toolbar row.
  - Loading shows skeleton rows.
  - Every page uses the compact image-led header.
- **Job detail and licence review:** a main column plus a sticky right rail
  for notices and actions; description lists on shared baselines; the
  parts table stacks by its container's width; licence images sit in a
  fixed 3:2 frame (no shift while they load).
- **Forms** (report a fault, assign and schedule, record the work):
  settings-style rows; the primary action lines up with the field column;
  the Unsafe option and the scheduling conflict notice use the status
  tints.
- **Homes and placeholders:** a header photo per role and per planned
  feature, from photos already in the set (no downloads; images still
  8.12 MB).
- **Dialogs:** 32 rem wide (was 28) for the larger type; tokens, overlay
  shadow and 6 px radius as before.

## 5. Not checked

- **States that need a data change:** a Reported job (the "Assign and
  schedule" form live), an In Progress job (the "Record the work" form
  and "Complete the job" live), the reject dialog with its reason, and the
  scheduling conflict notice. Seeing them would mean reporting a fault or
  starting job 1; they are covered by the component tests. Ask, and I will
  click through them and list the records touched.
- **Admin data screens:** fleet, tariffs, users, reports and audit log
  are "Not available yet" placeholders; there are no data tables,
  manager KPIs or charts to measure yet.
- **Browsers:** Safari and Firefox.
- **Reduced motion:** checked beyond the CSS rule only for the skeletons
  (`motion-reduce:animate-none`).

---

# Stage 6 QA: demo readiness (13 Oct 2026)

Measured in Chromium (Playwright) on the running dev servers, signed in as
each demo account. Recording viewport 1920 x 960; also 1536 x 730,
1440 x 900, 1024 x 768, 768 x 1024, 390 x 844 and 320 x 640.

The Stage 4.9 probe ran on every route and width. It was extended with:

- **Content:** "undefined", "null", "NaN", "Invalid Date", "[object
  Object]", "[Agency Name]", lorem ipsum, raw enum values, bare "—"
  values, rupee format and alignment, tabular figures, the date formats
  found.
- **Accessibility:** h1 count, heading order, unlabelled fields, alt text,
  broken images.
- **Visual rules:** radius over 6 px, shadows outside overlays,
  pointer-only elements.
- **Network and console:** every failing request and every console error
  or warning.

No record was created, changed or deleted. Validation was tried only
client side (never a wrong password). Error and loading states were made
by intercepting one API call in the test browser.

Check groups: 1 visual system, 2 typography, 3 layout, 4 images,
5 content, 6 interaction, 7 motion, 8 console and network,
9 accessibility. P = pass, F = fail before the fix, then fixed.

## Tier 1: the demo story (all seven viewports)

| Route | Role | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | Fixes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `/` landing | signed out | P | P | P | P | P | P | P | P (a) | P | |
| `/help`, `/credits` | signed out | P | P | P | P | P | P | P | P (a) | P | |
| `/register`, `/login`, `/verify` | signed out | P | P | P | P | P | P | P | P (a) | P | |
| `/app` home | customer | P | P | F | P | P | P | P | P | P | scrollbar gutter (F2) |
| `/app/search` empty and with results, category filter | customer | P | F | F | P | P | P | P | P | P | tabular figures (F3), gutter (F2) |
| `/app/vehicles/21` (Baleno), price summary | customer | P | F | P | P | P | P | P | P | P | tabular figures (F3) |
| `/app/bookings/2/pay` | customer | P | F | F | P | P | P | P | P | P | payment column (F1), F3 |
| `/app/bookings`, `/app/bookings/1`, `/app/bookings/2` | customer | P | P | F | P | P | P | P | P | P | F2 |
| `/app/licence` | customer | P | P | P | P | F (b) | P | P | P | P | backend data, reported |
| `/app/profile`, sign out | customer | P | P | P | P | P | P | P | P | P | |
| `/app/licences`, `/app/licences/2` | staff, admin | P | P | F | P | P | F (c) | P | P | P | F2, dialog scroll lock (F4) |
| `/app/maintenance`, `/report`, `/1`, `/3` | staff | P | F | P | P | P | P | P | P | P | F3 |
| `/app/handover`, `/app/branch-bookings` | staff | P | P | P | P | P | P | P | P | P | |
| `/app/jobs`, `/app/jobs/1` to `/4` ("Work recorded") | technician | P | P | P | P | P | P | P | P | P | |
| `/app`, `/app/reports`, `/app/maintenance`, jobs 2 and 3 | manager | P | P | P | P | P | P | P | P | P | |
| `/app`, fleet, tariffs, users, reports, audit, licence checks, maintenance, job 3, clearances, profile | admin | P | P | F | P | P | P | P | P | P | F2 |

- **(a)** One expected 401 from `POST /api/v1/auth/refresh/` on every
  signed-out load (no session cookie). Chrome logs it as a console error.
  It is not from our code; see the backend findings.
- **(b)** "Your licence was verified on —". The frontend reads
  `verified_at`; the API returns `null` for the seeded licence. Missing
  backend data.
- **(c)** Opening a dialog shifted the shell 15 px left once F2 was in
  place; F4 fixes it.

## Tier 2: every other route (all seven viewports)

The Tier 1 batches already covered every route in the Stage 5 inventory.
The extra Tier 2 routes:

| Route | Role | Result |
|---|---|---|
| 403 (`/app/licences` as a customer) | customer | P on all groups |
| 404 (`/no-such-page`, `/app/nope`) | signed out, customer | P |
| `/app/bookings` signed out | signed out | Redirects to "Sign in"; P |

## Tier 3: states (1920, 390)

| State | How | Result |
|---|---|---|
| Validation: sign in, register, search, report a fault, pay | Empty submit; bad e-mail and mobile | P: every invalid field has `aria-invalid` and its message in `aria-describedby`; focus goes to the first invalid field; no overflow; nothing under 15 px |
| Empty lists | My bookings "Status" Cancelled; maintenance "Status" Cancelled | P: "No Cancelled bookings" with its photo; no overflow |
| Server error | `GET /api/v1/bookings/` answered 500 | P: "We couldn’t load your bookings", "Try again" |
| Network failure | search request aborted | P: "We couldn’t search right now" with the connection message |
| Loading | bookings and jobs delayed 3 s | P: announced label plus skeleton rows; no shift when data lands (CLS at most 0.006 everywhere) |
| Sign out | top bar "Sign out" | P: back on `/login` |
| Keyboard | Tab through licence review, maintenance, report a fault, search, vehicle, pay, bookings | P: every stop shows the focus outline (the date-time inputs too, 1.6 px). The order follows the page |
| Dialogs and menu | Reject dialog; mobile menu at 390 | P: Escape closes and focus returns to the trigger ("Reject", "Open menu"); both "Main" navigation landmarks are present when the menu is open |
| Reduced motion | emulated `prefers-reduced-motion: reduce` | P: no running animations on home, bookings or search. Without it only the B5 reveal transform runs, once |
| Long text | Toyota Innova Crysta, "Demo Customer (licence pending)", the Andheri address, VRMS-20261011-0001, INV-2026-000001, TXN-… | P: no mid-token breaks, no clipping |

## Fixes (before, after)

| # | Problem | Fix | After |
|---|---|---|---|
| F1 | Pay page at 1920: the form column stopped at 672 px, leaving a 410 px empty band before the rail | The column fills the main grid column (`min-w-0` instead of `max-w-2xl`), like the vehicle and booking pages; the password field keeps its own width | No band; probe clean at all seven widths |
| F2 | Content edges moved 15 px between pages: short pages (licence checks, clearances, booking detail) have no scrollbar. Sign out sat at x 1888 there and x 1873 elsewhere | `scrollbar-gutter: stable` on `html` | Sign out at x 1873 and the header frame 1545 px wide on every route at 1920 |
| F3 | Amounts inside sentences ("₹150.00 per hour", "Rental, 2 days at ₹1,800.00", the Pay button, labour cost) used proportional figures | `font-variant-numeric: tabular-nums` on `body`; the mono `num` utilities unchanged | Every amount on every route has tabular figures |
| F4 | With F2, a dialog's scroll lock added a 15 px margin, so the shell jumped when Reject opened | `html body[data-scroll-locked] { margin-right: 0 !important }` | Sign out stays at x 1873 with a dialog open |

## Remaining P2 (not fixed)

- **Data-dependent blank space:** 224 to 473 px below the content of the
  one-item queues (licence checks, unsafe clearances), the unsubmitted
  search form, and booking detail at 1920 x 960.
- **Booking title:** "Booking VRMS-20261011-0001" takes two lines below
  1024 px. The reference itself never breaks (known since Stage 4.9).
- **Skip link:** every page load moves focus to the page content, so
  "Skip to main content" is reached with Shift+Tab, not the first Tab.
  Behaviour, left as is.
- **Native date-time inputs:** they show the operating system's format
  (14-10-2026 10:00) while every other date reads "14 Oct 2026, 10:00
  am". Browser control, not styled.
- **Month name:** Indian English writes September as "Sept"
  (28 Sept 2026). Consistent everywhere, from `Intl`.
- **Licence page dividers:** the divider above the licence details spans
  the content column (42 rem) and the one above "Update licence details"
  spans the row. This follows the settings-row pattern.

## Not checked

- **States that change data:** the live "Record the work" form, "Complete
  the job", "Assign and schedule", the payment result and the booking
  confirmation banner. Each needs a data change and is covered by the
  component tests. The booking flow up to "Hold this vehicle and pay" was
  checked.
- **Discount codes:** applying one was not tried.
- **Downloads:** the invoice PDF was not opened.
- **Browsers:** Safari, Firefox and real phones.
- **Network throttling:** Slow 4G was approximated with 3 s API delays, not
  DevTools throttling of all assets.
- **Contrast:** text on a photo exists only on the landing hero, measured
  in Stage 4.10; Stage 6 found no other text on a photo.
