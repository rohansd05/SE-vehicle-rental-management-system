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

| Role | Where | What it shows | Ratio | Treatment |
|---|---|---|---|---|
| Hero | Landing page, first viewport | An Indian road or street with a car or two-wheeler, natural light | Full bleed, cover, about 16:9 crop at 1440 | Deep-petrol overlay (`--primary-hover` at 75 %) under the centred agency name, so text contrast stays AA |
| Auth panel | Sign in, register, verify (right column) | A calm road or a key-in-hand detail | Fills the panel, cover | Same petrol overlay; agency name and four facts in white |
| Section photo | Landing "How it works" steps | One per step: phone in hand, hands on the wheel, a parked car, keys changing hands | 4:3 | Radius `--radius-xl`, no overlay |
| Category row | Landing, the five categories in the demo fleet | A real model photo per category | 3:2 | Radius `--radius-xl` |
| CTA band | Landing, before the final call to action | A car on an open road | Full bleed, 3:1 to 4:1 | Petrol overlay as the hero |
| Feature-page band | Bookings, booking detail, licence, maintenance list, report a fault, job detail, technician jobs, licence checks, clearances, dashboard (`PageHeader`'s `photo`) | The page's subject (road, driver, workshop, tools, a desk) | 160 px tall, 192 px from 1024 px (stored 6:1), hidden below 640 px | Radius `--radius-xl`, no overlay; decorative (`alt=""`, `aria-hidden`) |
| Small side image | Payment rail, above the summary, from 1024 px | A card terminal | 4:3, rail width | Radius `--radius-xl`; decorative |
| Quiet image | Help, 403, 404 and photo credits ("Where to go" column, 5:2, from 1024 px); "Not available yet" pages (3:1, from 640 px); empty states (3:2, 144 px wide, from 640 px, in place of the inbox icon) | An empty road | As listed | Radius `--radius-xl` (`--radius-lg` in empty states); decorative |
| Vehicle tile | Search results | The exact model (representative) or its category | 3:2 | See section 3 |
| Vehicle detail | Top of the vehicle page's main column | The vehicle's own photos (the first large at 3:2, the rest 4:3 thumbnails), otherwise the representative photo at 3:2 above the existing "No photographs have been added yet." | 3:2 | Radius `--radius-xl` |

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
- **Crop:** 3:2, the vehicle centred slightly below the middle (focus
  0.5, 0.55), with about 8 % margin around the body.
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
- **Overlay:** text over photos uses one overlay only: the deep petrol
  `--primary-hover` (`#0B4753`) at 75 % (`bg-primary-hover/75`). In the
  worst case, a pure-white pixel under the overlay, white text measures
  5.1:1, so it passes AA for body text at every width. (The lighter
  `--primary` at 72 % was rejected: 4.0:1 in that case.)
- **Radius:** `--radius-xl` (6 px) on every photo that is not full bleed.
- **Crops:** each photo is cropped once, in the script, to the shape it is
  shown at (hero kept whole; panel 4:5; CTA band 3:1; feature band 6:1;
  section and small 4:3; quiet and vehicle 3:2), around a per-photo `focus`
  point in `scripts/image-sources.json`.
- **Formats:** AVIF at every width of the role (hero and CTA 960, 1600,
  2400; panel 480, 800, 1200; band 960, 1600, 2200; section 400, 800;
  small and quiet 320, 640; vehicle 320, 640, 960), WebP at all but the
  largest (it is only the fallback for browsers without AVIF), and one JPEG
  (hero, CTA and band 1600; panel and section 800; the rest 640). Served
  through `<picture>` with `srcset` and `sizes` and explicit width and
  height, lazy below the fold, the hero eager with `fetchpriority="high"`.
- **Location:** the outputs are static files in `frontend/public/images/<id>/`
  and the manifest in `frontend/src/assets/images/manifest.json`; the
  originals stay in the git-ignored `frontend/.image-src/`.
- **Budget:** under about 8 MB of committed images in total; each hero under
  about 400 KB at its largest AVIF. Measured 12 Oct 2026: 43 photos, 7.61 MB
  in all; the hero's 2400 px AVIF is 304 KB.
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
