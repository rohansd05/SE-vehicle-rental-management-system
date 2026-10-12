# VRMS imagery brief (Stage 4.7)

How photography is used across the app: where photos go, what they show,
how they are cropped and treated, and how vehicle listings present the car.
It applies with `ui-brief.md` (binding decisions B1 to B12) and decision D23
(`docs/decisions.md`: photo sources, licences, credits).

## 1. Reference study (12 Oct 2026)

Studied in Chrome at a 1440 px window, measuring each page's images with
their computed size, aspect ratio, corner radius and fit. Layout and photo
usage only: nothing was copied, traced or downloaded from these sites.

| Site | Hero | Vehicle listing | Other photos |
|---|---|---|---|
| revv.co.in (primary) | Full-bleed illustrated road scene with a real car, 2.67:1, booking cards over it | "Top selling cars": white tiles, 15 px radius, no visible shadow; make and model label at the top left; a cut-out car at three-quarter front on white, 2:1; a spec row of three icons (fuel, transmission, seats) in small grey text; price per day in bold below | Promo banners 2.1:1, square corners; the app screenshot |
| mychoize.com | Illustration with a car, 2.16:1, booking bar on top | Fleet tiles 1.37:1, 15 px top radius only, car photo on top | One lifestyle photo (people on a car at sunset) in a 30 px rounded block beside a dark panel |
| sixt.com | A dark studio car photo (front on), full bleed, 2.78:1, under the booking widget | (behind the booking flow) | Editorial photos at 1.25:1 and portrait 0.67:1, square corners, text over them |
| turo.com | A close-up car photo inside a rounded (12 px) 3.64:1 band, darkened for white text, search on top | Real street photos of the actual cars, 3:2, 12 px radius, no card border; bold model name under the photo, a meta line, then the price per day | |
| zoomcar.com | 2.05:1 hero | A carousel of portrait (0.84:1) car "showcase" photos | |
| europcar.com | A lifestyle photo (driver in a car) behind the booking box | Vehicle-type tiles at 3:2 with cut-out cars | Cookie dialog left untouched |
| hertz.com | Background-image hero | | Promo blocks 1.2:1 |
| getaround.com | CSS-background hero | | |

Not reachable this session (site permissions): avis.co.in and blablacar.in
(BlaBlaCar was reachable during the type study, Stage 4.6, but not now).
Zoomcar and Getaround were blocked during the type study but reachable now.

Patterns taken:

- **The car photo leads the listing.** Every rental site puts the vehicle
  image first in its tile, at a fixed aspect ratio (2:1 for cut-outs, 3:2
  for photos), with the model name, a short spec row and the price directly
  under it. Revv and Europcar use studio cut-outs; Turo uses real photos.
- **Three-icon spec row** (fuel, transmission, seats) is the shared
  shorthand for cars; two-wheelers show engine size instead.
- **Price in bold, unit after it** ("₹1,656 per day"), left aligned under
  the name, not in a separate column.
- **Heroes are wide and short** (2:1 to 3.6:1). Text over a photo always sits
  on a darkened or flat area.
- **Corners:** Revv and Turo round tiles and photos at 12 to 15 px; Sixt is
  square. Our radius scale stops at 6 px (`--radius-xl`), which reads as
  "lightly rounded" like Turo without the app-store softness of Revv.
- **Lifestyle photos are rare and large**: one per page section, not
  scattered thumbnails.

## 2. Photo roles in VRMS

Stage 4.8 (12 Oct 2026) replaced the fixed role crops: photos are stored
at their native aspect, each with a subject box and optional focal point
(`scripts/image-sources.json`, copied into the manifest), and every slot is
fitted at runtime by `fitPhoto` (`src/lib/images.ts`, unit-tested): `cover`
only when the whole subject plus a 4 % margin stays in the frame, else
`contain`. The table below is updated to the Stage 4.8 layouts.

| Role | Where | What it shows | Ratio | Treatment |
|---|---|---|---|---|
| Hero | Landing page, first viewport | An Indian road with a car, natural light | From 1024 px a full-bleed band at the photo's own shape, capped at the first viewport; below, the whole photo under the text | `--photo-overlay-strong`; the text on a local `--photo-scrim` panel above the car |
| Auth panel | Sign in, register, verify (right column, from 1024 px) | A key-in-hand detail | 16:9 frame at the top of the petrol panel (subject fits) | `--photo-overlay-strong`; the agency name and facts on the solid petrol below, never on the photo |
| Section photo | Landing "How it works" steps | One per step: phone in hand, hands on the wheel, a parked car, keys changing hands | 3:2 | Radius `--radius-xl`, no overlay |
| Category row | Landing, the five categories in the demo fleet | A real model photo per category | 3:2 | Radius `--radius-xl` |
| Split photo | Landing "Book online", "For branch teams" and "System status" | A car on a wet road; a workshop; dashboard gauges | The photo's own shape | Radius `--radius-xl`, no overlay; vertically centred against the text |
| CTA band | Landing, the final call to action | A car on an open road | From 1024 px a full-bleed 3:1 band (the car fits); below, the whole photo above the text | `--photo-overlay-strong`; the text on the left over a `--photo-scrim` fade |
| Page-header photo (Stage 4.9, B14) | Home (every role), my bookings, driving licence, maintenance, report a fault, technician jobs, licence checks, clearances, help, photo credits, 403, 404, "Not available yet" (`PageHeader`'s `photo`) | Home: dashboard gauges; bookings: a car on a wet road; licence: hands on the wheel; maintenance and report: the workshop car on its lift; technician: the tool wall; licence checks: the branch desk; clearances: a car back on the road; help, credits, 403, 404 and placeholders: the empty road | The right half of the header frame from 1024 px (full frame height, at least 280 px); full width above the text below 1024 px (3:2, 16:9 from 640 px) | `--photo-overlay-soft`; decorative; the first image on the page, eager with high fetch priority |
| Destination tile (Stage 4.9) | Home: one image-led tile per available destination | Search: a parked car; bookings: the wet-road car; licence: a driver; profile: phone in hand; licence checks: the desk; maintenance: the workshop; jobs: the tool wall; clearances: a car with its bonnet up | 3:2 | No overlay |
| Small side image | Payment rail, above the summary, from 1024 px | A card terminal | 4:3, rail width | Radius `--radius-xl`; decorative |
| Quiet image | Empty states (Stage 4.9: 3:2, two fifths of the block beside the message from 640 px, above it on phones); help, credits, 403, 404 and placeholders now carry it as their page-header photo | An empty road | 3:2 | Radius `--radius-xl`; decorative |
| Vehicle tile | Search results | The exact model (representative) or its category | 3:2 | See section 3 |
| Vehicle detail | Top of the vehicle page's main column | The vehicle's own photos (the first large at 3:2, the rest 4:3 thumbnails), otherwise the representative photo at its own shape above the existing "No photographs have been added yet." | Own shape | Radius `--radius-xl` |

Pages that do **not** use photos: forms while they are being filled (no
photo inside a form, table or queue), the profile page, and every table,
list row and dialog except vehicle tiles.

## 3. Vehicle presentation (Revv-style, B12)

- **Image source order:** the vehicle's own photos from the API first, then
  the exact-model representative photo (from the registry), then the
  category photo. Alt text for the last two is "Representative image of a
  <Make> <Model>" or "Representative image of a <Category>" ("an" before a
  vowel sound, so "an SUV"), never implying it is the vehicle itself.
- **Chosen set (12 Oct 2026):** one photo per model (option 1), 23 models.
  Honda Shine has no licensed photo and falls back to the Motorcycle
  category photo. The Scooter category photo is the TVS Jupiter's (the
  candidate `cat-scooter-2` was the same Commons file), so it is stored
  once. Category photos: `cat-hatchback-2`, `cat-sedan-2`, `cat-suv-1`,
  `model-tvs-jupiter-1`, `cat-motorcycle-2`
  (`src/assets/vehicles/registry.ts`).
- **Angle and background:** three-quarter front view, the whole vehicle in
  frame, on a plain or uncluttered background where one exists. Facing
  direction is kept consistent where the source photos allow; the brief
  records each model's direction in `scripts/image-sources.json` notes and
  never mirrors a photo (mirroring reverses badges and lettering).
- **Crop (Stage 4.8):** never. Tiles are 3:2 frames; a photo is cropped
  only where its subject box (the whole vehicle) plus 4 % still fits, and
  otherwise shown whole (`contain`) on the `canvas-sunken` tone. The
  vehicle page shows the representative photo at its own shape.
- **Tile:** photo on top (3:2, radius `--radius-xl` on the top corners,
  canvas-sunken behind it while it loads); model name in Schibsted Grotesk
  (subsection size) with the year in mono; category · type as small text; a
  spec row with lucide icons showing only fields the API returns (fuel,
  transmission and seats for cars; fuel and engine cc for two-wheelers);
  rating and last service; the price block with the existing "Estimated
  price" sentence in a `<p>`, the amount in IBM Plex Mono and the deposit
  line; the existing "View and book" action. Hairline border, no shadow; on
  hover the tile lifts 2 px and the border tints to `--line-strong`.
- **Plates:** any readable number plate is blurred in the optimisation
  script (padded box, pixelated and blurred), recorded per photo in
  `scripts/image-sources.json`.

## 4. One photo treatment

- **Colour grade:** every photo gets the same grade in
  `scripts/optimise-images.mjs`: saturation × 0.9 and contrast × 1.04, so
  photos from different photographers read as one set.
- **Overlay (Stage 4.8, B13):** two tint tokens only, `--photo-overlay-strong`
  (petrol `--primary-hover` at 30 %) on covers and the auth panel and
  `--photo-overlay-soft` (20 %) on feature-page photos, so photos stay vivid.
  Text never relies on the tint: it sits on `--photo-scrim` (the same petrol
  at 84 %) as a local panel (hero) or a fade from the text side (final call
  to action), or on solid petrol (auth panel). Contrast is measured on the
  real photo pixels in `alignment-qa.md`; the lowest is 8.35:1.
- **Radius:** `--radius-xl` (6 px) on every photo that is not full bleed.
- **Crops:** none in the script (Stage 4.8); see section 2.
- **Formats:** AVIF at every width of the role (hero and CTA 960, 1600,
  2400; panel 480, 800, 1200; band 480, 960, 1440; section 400, 800;
  small 320, 640; quiet and vehicle 320, 640, 960; `step-licence-1` and
  `band-quiet-2` moved to the band role in Stage 4.9 because they now fill
  page headers), WebP at all but the
  largest (it is only the fallback for browsers without AVIF), and one JPEG
  (hero and CTA 1600; band 960; panel and section 800; the rest 640). Served
  through `<picture>` with `srcset` and `sizes` and explicit width and
  height, lazy below the fold, the hero eager with `fetchpriority="high"`.
- **Location:** the outputs are static files in `frontend/public/images/<id>/`
  and the manifest in `frontend/src/assets/images/manifest.json`; the
  originals stay in the git-ignored `frontend/.image-src/`.
- **Budget:** under about 8 MB of committed images in total; each hero under
  about 400 KB at its largest AVIF. Measured after Stage 4.8 (native aspect, 12 Oct 2026): 43 photos,
  7.99 MB in all; the hero's 2400 px AVIF is 303 KB. After Stage 4.9: 43
  photos, 8.12 MB; the largest AVIF of any page-header photo is 117 KB
  (`band-technician-1`); no new photos were downloaded.
- **Motion (B5, B7):** photos fade and settle from scale 1.03 to 1 once they
  have loaded (`photo-in`); the landing hero eases from scale 1.04 on load
  (`hero-zoom`); vehicle tiles stagger on first load; landing photos reveal
  with their sections. Under reduced motion they fade only and the hero does
  not zoom.

## 5. Sources and licences

Only Unsplash (Unsplash License, never Unsplash+), Pexels (Pexels License)
and Wikimedia Commons (CC0, Public Domain, CC BY, CC BY-SA). Never a
manufacturer, dealer or rental-company image, including manufacturer
accounts on Unsplash (two such candidates, from Ather Energy and Hyundai
Motor Group, were rejected for this reason). Each photo's page, author and
licence are recorded in `scripts/image-sources.json` and, after the
choice in Stage 4.7B, in `docs/design/image-credits.md` and on the public
"Photo credits" page.
