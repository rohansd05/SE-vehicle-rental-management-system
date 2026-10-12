# VRMS type options (Stage 4.6, Part A)

**Decision (12 Oct 2026): system C, "Grotesk and Plex", was chosen.** It is
now B2 in `ui-brief.md` and D22 in `decisions.md`. The `/_type` comparison
route and the unchosen packages have been removed; this file stays as the
record of the research and the alternatives.

Three complete type systems to replace B2 (Fraunces display, wide Archivo
headings). Compare them live at **http://localhost:5173/_type** (development
builds only; the route and its fonts are not in a production build). Each
system is shown on the landing hero (brand name, intro paragraph, the two
actions, centred) and on a sample app section (page title, section title,
body paragraph, a booking row with a plate, a date, an amount and a status,
and a price summary), with real app strings and the real demo booking.

All candidate packages were checked on npm before installing; each is SIL
OFL 1.1 at version 5.3.0, so D22 covers whichever is chosen. None is on the
avoid list (Inter, Geist, Poppins, Montserrat, DM Sans, Space Grotesk,
Playfair Display, Fraunces, Instrument Serif, Outfit, Plus Jakarta Sans,
Manrope, script or handwritten faces).

## 1. Research notes

Measured in Chrome at a 1440 px window with computed styles of the visible
hero headline and body text (11 to 12 Oct 2026).

| Site | Headline face, size / line, weight, tracking, alignment | Body face | What it says about the category |
|---|---|---|---|
| sixt.com | Helvetica Now, 72 / 72, 900, +0.025 em, uppercase, centred | Helvetica Now 16 | Rental brands lead with one heavy, compact grotesk line, centred over the booking widget. |
| hertz.com | Open Sans, 50 / 37.5, 400, left | Open Sans 14 | Generic system; nothing to take. |
| avis.com | Avis Headline (custom condensed), 64 / 76.8, 400, −1 px, uppercase, left | Avis Sans 28 lead | Condensed display plus a separate text face. |
| europcar.com | System stack, 24 / 35, 700 (region gate in front of the real hero) | Arial | Partial: a country gate hid the home page. |
| revv.co.in | Poppins (avoid list), 28 / 32, 800 | Poppins | Indian rental market, template face; a counter-example. |
| turo.com | Turo Sans (custom grotesk), 38 / 44, 900, −0.9 px (−0.024 em), centred | Turo Sans 16 / 24, centred | Centred hero, heavy weight, tight tracking, one family for everything. |
| uber.com | Uber Move, 52 / 64, 700, left | Uber Move Text 12 to 16 | A display cut and a text cut of one family. |
| blablacar.in | GT Eesti (custom grotesk), 54 / 54, 800, left | GT Eesti 16 | Heavy, tight leading (1.0) on the headline. |
| polestar.com | Polestar Unica, 30 / 32, 400, −1.2 px (−0.04 em) (region gate) | Polestar Unica | Very tight tracking on a neutral grotesk. |
| porsche.com | Porsche Next (fallback Arial Narrow), sizes inside shadow DOM | Porsche Next 16 / 24 | A narrow automotive grotesk. |
| linear.app | Inter (avoid list), 64 / 64, 510, −1.4 px (−0.022 em), left | Inter 15 / 24 | Structure only: large, medium weight, tight tracking, line height 1.0. |
| ramp.com | Lausanne, 64 / 64, 400, left | Lausanne 14 / 20 | Large and plain: size, not weight, carries the headline. |
| mercury.com | Arcadia Display, 52 / 57, 480, centred | Arcadia 12 to 16 | Centred hero, display cut paired with a text cut. |
| fontsinuse.com, tag "car rental" | Check scooter rental: Action Condensed; Current (Bermuda EV rental): Object Sans; Hertz campaigns; Vanzzz | | Mobility identities lean on bold condensed or compact grotesks. |
| fontsource.org | Specimens of Barlow Semi Condensed, Schibsted Grotesk, Red Hat Display | | Confirmed weights, axes and licences. |

Not reachable from this browser (site permissions): enterprise.com,
zoomcar.com, getaround.com, bolt.eu, volvocars.com, rivian.com, stripe.com,
vercel.com, wise.com, typewolf.com. bmw.com loaded but denied script access
and its screenshot did not render. fonts.google.com was not needed:
Fontsource lists the same families with their licences.

Patterns taken: one display line set large (52 to 72 px) with line height
near 1.0; heavy weight (700 to 900) or large size, not both at once; tight
tracking (−0.02 to −0.04 em) on grotesks, but none on condensed faces;
centred heroes are common in rental (Sixt, Turo, Mercury); a display cut
paired with a text cut of the same family (Uber, Mercury, Avis); body at
16 px with line height about 1.5.

## 2. The three systems

Sizes are given at 1440 and 390. Display and title sizes are fluid
(`clamp()`), so values between are interpolated. Body sizes are fixed.

### A. Highway: Barlow Semi Condensed, Barlow, JetBrains Mono

Inspired by Sixt (compact heavy hero, centred), Check scooter rental
(Action Condensed), Porsche Next (narrow automotive grotesk) and the
highway and licence-plate lettering Barlow is drawn from. The most
distinctively "vehicle" of the three.

| Role | Face | 1440 | 390 | Weight | Tracking | Line height |
|---|---|---|---|---|---|---|
| Display (hero) | Barlow Semi Condensed | 88 | 44 | 700 | −0.005 em | 0.95 |
| Page title | Barlow Semi Condensed | 40 | 32 | 600 | 0 | 1.1 |
| Section | Barlow Semi Condensed | 26 | 24 | 600 | 0 | 1.3 |
| Subsection | Barlow Semi Condensed | 20 | 20 | 600 | 0 | 1.3 |
| Lead | Barlow | 20 | 20 | 400 | 0 | 1.55 |
| Body, inputs, buttons | Barlow | 17 | 17 | 400 / 500 | 0 | 1.6 |
| Small | Barlow | 15 | 15 | 400 | 0 | 1.5 |
| Label | Barlow | 14 | 14 | 500 | 0 | 1.3 |
| num / num-strong / num-lg | JetBrains Mono (tabular) | 15 / 16 / 28 | same | 400 / 500 / 500 | 0 | 1.45 |

Barlow is static (no variable cut), so weights 400, 500, 600 and 700 are
imported. Body is 17 px because Barlow's slightly narrow proportions read
smaller than Plex at the same size.

### B. Superfamily: Red Hat Display, Red Hat Text, Red Hat Mono

Inspired by Uber (Uber Move for display, Move Text for body), Turo (heavy,
tight, centred) and Polestar (tight tracking on a neutral grotesk). One
family designed to work together, the most "product" of the three.

| Role | Face | 1440 | 390 | Weight | Tracking | Line height |
|---|---|---|---|---|---|---|
| Display (hero) | Red Hat Display | 72 | 40 | 700 | −0.025 em | 1.0 |
| Page title | Red Hat Display | 36 | 32 | 650 | −0.015 em | 1.17 |
| Section | Red Hat Display | 24 | 22 | 650 | −0.015 em | 1.3 |
| Subsection | Red Hat Display | 19 | 19 | 600 | −0.01 em | 1.35 |
| Lead | Red Hat Text | 20 | 20 | 400 | 0 | 1.5 |
| Body, inputs, buttons | Red Hat Text | 16 | 16 | 400 / 500 | 0 | 1.625 |
| Small | Red Hat Text | 14 | 14 | 400 | 0 | 1.57 |
| Label | Red Hat Text | 13 | 13 | 500 | 0 | 1.38 |
| num / num-strong / num-lg | Red Hat Mono (tabular) | 15 / 16 / 28 | same | 400 / 500 / 500 | 0 | 1.45 |

All three are variable (weight axis), so one file each.

### C. Grotesk and Plex: Schibsted Grotesk, IBM Plex Sans, IBM Plex Mono

Inspired by Ramp (Lausanne, large and plain), Mercury (display cut,
centred), BlaBlaCar (GT Eesti 800, line height 1.0) and Linear (tight
tracking). Changes only the headline face; body and numbers stay as they
are today.

| Role | Face | 1440 | 390 | Weight | Tracking | Line height |
|---|---|---|---|---|---|---|
| Display (hero) | Schibsted Grotesk | 76 | 40 | 800 | −0.03 em | 1.0 |
| Page title | Schibsted Grotesk | 36 | 32 | 700 | −0.02 em | 1.17 |
| Section | Schibsted Grotesk | 24 | 22 | 700 | −0.02 em | 1.3 |
| Subsection | Schibsted Grotesk | 19 | 19 | 650 | −0.01 em | 1.35 |
| Lead | IBM Plex Sans | 19 | 19 | 400 | 0 | 1.58 |
| Body, inputs, buttons | IBM Plex Sans | 16 | 16 | 400 / 500 | 0 | 1.625 |
| Small | IBM Plex Sans | 14 | 14 | 400 | 0 | 1.57 |
| Label | IBM Plex Sans | 13 | 13 | 500 | 0 | 1.38 |
| num / num-strong / num-lg | IBM Plex Mono (tabular) | 15 / 16 / 28 | same | 400 / 500 / 500 | 0 | 1.45 |

## 3. Recommendation

**A (Highway)** if the brand should read as a vehicle business first: it
is the one choice no generic template would make, and its plate-and-signage
origin is the subject itself. **B (Superfamily)** if consistency across a
dense operations UI matters most. C is the smallest change.

## 4. What happens after the pick (Part B)

The chosen system goes into the `index.css` tokens for every page; the
unchosen packages, and Fraunces and Archivo if unused, are uninstalled; the
`/_type` route and `src/dev/TypeLab.tsx` are deleted; B2, the type scale,
D22, the runtime package table and CLAUDE.md are updated.
