# VRMS UI redesign: audit and design brief

Stage 1 of the frontend redesign (11 Oct 2026). This brief is the reference
for Stages 2 to 6. It changes how the app looks, never what it does.

## Binding design decisions (11 Oct 2026)

These are final. They apply to every page restyled in Stages 2 to 4, to the
pages of Stages 5 and 6, and to any page built later. Where an older section
of this brief differs, these win.

- **B1. Copy is frozen, presentation is free.** Never change a string; size,
  weight, family, width, tracking, line height, colour, alignment, grouping
  and placement may change freely.
- **B2. Fonts: type system C, "Grotesk and Plex"** (chosen 12 Oct 2026 from
  the three systems in `docs/design/type-options.md`; it replaces the
  earlier Fraunces and wide-Archivo pairing). Hero and every heading:
  Schibsted Grotesk (variable, `@fontsource-variable/schibsted-grotesk`
  5.3.0, SIL OFL 1.1); the hero at weight 800 with −0.03 em tracking, page
  and section titles at 700 with −0.02 em, subsections at 650 with
  −0.01 em. Body and UI: IBM Plex Sans. Numbers, prices, dates, IDs and
  plates: IBM Plex Mono with tabular figures. Never a cursive, script or
  handwritten face, and none of the avoided template faces listed in
  `type-options.md`.
- **B3. Bigger type everywhere, as one token change in `index.css`** (no
  per-page overrides): body 16/26, small 14/22, label 13/18; lead 19/30 on
  public pages; page title 36/42 (32 at 390), section 24/30 (22 at 390),
  subsection 19/26; home display 76 px at 1440, fluid with `clamp()` down
  to 40 px at 390; num 15, num-strong 16, num-lg ("Total payable") 28. Inputs, selects
  and buttons use 16 px text; controls are 44 px high for page actions and
  36 px in rows. After the change every table, description list, row grid
  and the sidebar is re-checked at 1440, 1024, 768 and 390: no wrapping of
  nav labels, no truncated values that were fully visible before, no
  overflow.
- **B4. No dead space.** At 1440 every page uses the full main area (no
  content cap; the page gutter stays). List and table pages fill the width
  with aligned columns. Detail and form pages use main column + right rail,
  or the settings layout. Reading pages (help, 403, 404, placeholders) use
  two columns. No page may leave a large empty right half or an empty lower
  half at 1440 or 1024; it is filled with existing content arranged better
  (rails, columns, the "Where to go" list, summaries), never with filler
  text or new claims.
- **B5. Rich, intentional motion in the default case** (no reduced-motion
  preference), with CSS, `@keyframes` and tw-animate-css only. Orchestrated
  page entry on every page: header, then first section, then the rest, in at
  most 4 steps, 40 to 60 ms apart, 250 to 400 ms each, ease-out, a 6 to
  12 px rise plus fade, once per navigation and never on refetch. Home and
  auth pages: a richer one-time hero sequence (display headline, lead,
  actions, then the status list or panel facts), up to about 700 ms in
  total. Scroll-triggered reveals (fade and rise once as a section enters
  the viewport) on public pages and on long signed-in pages: help, profile,
  licence, vehicle detail sections, booking detail, job detail sections,
  with CSS scroll-driven animations and an IntersectionObserver fallback,
  and content visible if neither runs; not on tables or on form fields while
  the user is typing. Lists and tables: staggered first-load entry, 30 to
  50 ms per row, first 10 rows only. The sticky price rail docks with its
  hairline; the top bar shows its edge once content scrolls under it;
  anchor scrolling is smooth. Overlays: dialogs and popovers scale from 0.97
  with a fade, the drawer slides, menus fade with a 4 to 6 px offset, exits
  faster than entrances. Feedback: hover and press colour transitions, a
  focus-ring transition, field errors fading and rising in, status pills
  transitioning colour, a new or changed row or value getting a primary-tint
  highlight that fades within about 1.2 s, and the confirmation check icon
  drawing once. Only transform and opacity (plus colour); no bounce, no
  loops on static elements, no parallax, no gradients, no blur.
- **B6. Never animate the value of money, totals, timers or IDs:** no
  count-up, no rolling digits. "Total payable" may get a brief highlight
  when it changes, but the exact formatted value is always shown.
- **B7. Reduced motion is kept.** Under `prefers-reduced-motion: reduce`
  movement is replaced by short opacity fades (about 150 ms) so pages still
  look finished; no rises, slides, scale or scroll reveals. Vitest runs in
  jsdom, which runs no CSS animations, so tests never wait on one.
- **B8.** Installed frontend, UI/UX, motion or accessibility skills may be
  used, but these rules win; any skill advice that would change copy,
  behaviour or tests is ignored.
- **B9. One system for every page:** colours only from the tokens in
  `index.css`; fonts only from type system C through the type tokens;
  spacing only from the 4 px scale; one radius scale; one shadow (overlays
  only, plus the vehicle-tile hover); one photo treatment
  (`imagery-brief.md`, section 4); one icon set (lucide) and stroke width;
  one button, input, table, pill, alert, tile and page-header style. No raw
  hex or rgb colours, no Tailwind palette colour classes (emerald-, sky-,
  slate-, gray- and so on) and no arbitrary font sizes outside `index.css`
  and the shared components.
- **B10. Checked by a script:** `frontend/scripts/check-design.mjs`
  (`npm run check:design`) fails if a file under `src/` outside `index.css`
  and `components/ui` contains a raw hex, rgb, hsl or oklch colour, a
  Tailwind palette colour class or an arbitrary text size such as
  `text-[13px]`. It runs in every stage alongside vitest, lint and build.
- **B11. Every page matches the others:** the same page header (with or
  without a photo band), gutters, content-width rules, type scale, image
  treatment and motion language, for existing and future pages.
- **B12. Vehicle imagery:** a vehicle's own photos come first, then the
  exact-model representative photo, then the category photo, always with
  honest "Representative image of a ..." alt text. Image-led tiles are used
  only for vehicles (`imagery-brief.md`, section 3).
- **B13. Photos and text, measured (12 Oct 2026):** photo covers use only the
  shared tokens (`--photo-overlay-strong` 30 % and `--photo-overlay-soft`
  20 % petrol; text sits on `--photo-scrim`, the same petrol at 84 %, as a
  local panel or a fade from the text side) and meet WCAG AA measured on the
  real photo pixels. No subject is ever cropped: every photo carries a
  subject box and optional focal point in its registry entry, and
  `fitPhoto` crops only background, keeping the whole subject plus 4 %
  (or the photo's own margin), or shows the photo whole. No major page
  region is text-only where a suitable photo fits. Nothing renders below the
  type minimums (16 px body and inputs, 14 px secondary, 13 px labels and
  table headers, 12 px only in dense pills); mono numbers take the size of
  their context. Images and text share container edges and centre lines
  within 1 px. Measurements: `docs/design/alignment-qa.md`.
- **B14. Image-led headers and a larger type scale (12 Oct 2026):** page
  headers with a photo use the shared `PageHeader` frame, whose photo fills
  the heading section (no side thumbnails): from 1024 px the title,
  subtitle and action sit in the left half, vertically centred, and the
  photo fills the right half to the frame's top, right and bottom edges, at
  least 280 px and about 300 to 360 px tall at 1440 to 1536; below 1024 px
  the photo runs full width above the text. List, queue, form, landing and
  home pages use it; record-detail pages (booking, job, vehicle) keep the
  plain header because their titles are references. Type floors: nothing
  visible under 15 px at any width; body, inputs, buttons, sidebar and top
  bar 18 px at 1440 (16 px floor); secondary text, captions and pills 15 px
  floor, 16 px from about 1024; field labels and table headers 16 px;
  subheadings 22 px or more at 1440; page titles 3rem or more at 1440 and
  1536, sized from their header frame so the longest two-word title stays
  on one line. Mono figures are sized from the measured figure height of
  IBM Plex Mono against IBM Plex Sans (1.02 em). References, dates and
  amounts never break inside a token. No blank area of about 200 px or more
  without content or imagery, except where the amount of data decides it
  (short queues) and on tall screens below short pages
  (`alignment-qa.md`, Stage 4.9).

Implementation notes for B1 to B8 are in sections 4 (type), 5 (space and
motion) and 6.0 (shell and content width) below, which were updated to
match. B13's are in `imagery-brief.md` (sections 2 and 4) and
`alignment-qa.md`. B14's tokens are in `frontend/src/index.css` (type
scale, `--header-gap`), its layouts in `components/page.tsx`
(`PageHeader`), `lib/layout.ts` (`RAIL_LAYOUT`, `SETTINGS_ROW`) and
`pages/DashboardPage.tsx` (destination tiles); measurements in
`alignment-qa.md`, Stage 4.9.

## 0. Ground rules

- **Behaviour is frozen.** Every route, guard, form field, validation, API
  call, query key, state and permission stays as it is.
- **Copy is frozen.** Every visible string, label, button name, heading,
  `aria-*` attribute and role stays exactly as it is. New text is limited to
  the auth-page product panel (section 6.1), and it must not repeat any
  string a test looks up.
- **Test hooks to preserve.** These are structural, not class names:
  - `[data-slot="card"]` must still wrap the "Work recorded" section of the
    job detail page (`maintenance/flows.test.tsx:147`). Card stays as a
    component; only its look changes (no box).
  - Field errors stay in a `<p>` (`RegisterPage.test.tsx:69`); "Estimated
    price" stays inside a `<p>` with the amount (`search.test.tsx:147`).
  - Lists stay lists: `list "Available vehicles"` with `listitem`s,
    `list "Photographs"`, the bookings `listitem`s, and job links whose name
    contains `Job 7 · MH01AB1234`.
  - Tables stay tables: `table "Price summary"`, `table "Price"`, and the
    `row` "Total payable ₹…".
  - Two `navigation` landmarks named "Main" (sidebar and drawer).
- **No test assertion is edited.** If a test fails, the UI change is wrong.
- **One deliberate behaviour change, requested in the brief:** the theme no
  longer follows the operating system. `lib/theme.ts` currently adds `.dark`
  when the OS is dark, which is why the app looks all black on this laptop.
  There is no theme toggle, so per the instructions none is added and the
  app is light everywhere. The `.dark` token block and the `dark:` utility
  classes are removed with it.

## 1. Audit

Method: Chrome, each demo account, every route rendered in a same-origin
iframe at exactly 1440, 1024 and 390 CSS px (the laptop viewport is 1150 px
at 125 % scaling, so the window alone cannot reach 1440). Horizontal
overflow was measured by script on every route; screenshots were reviewed
for the rest. The console had no errors.

### 1.1 Problems on every page

| # | Problem | Seen at |
|---|---|---|
| G1 | Dark theme forced by the OS setting: near-black canvas, light-blue primary with dark text. Reads as a default template. | all |
| G2 | System font stack (Segoe UI on Windows). Headings, body and numbers share one face, so there is no hierarchy and no tabular figures. | all |
| G3 | Card boxes everywhere: home status card, dashboard tile grid, search form, result cards, vehicle detail, licence status, three profile cards, job detail cards, licence review cards, auth forms. | all |
| G4 | Content is capped at `max-w-4xl` (896 px) inside the shell, and some pages at `max-w-xl`/`max-w-3xl`. At 1440 that leaves 300 to 500 px of dead canvas on the right of most pages. | 1440 |
| G5 | Sidebar is not a fixed rail: its border stops where the content ends, there is no brand at its top, and the agency name sits in the top bar instead. | 1440, 1024 |
| G6 | Top bar uses `backdrop-blur` (an AI tell per the brief) and repeats name, role, help and sign-out with mixed button styles. | all |
| G7 | Hard-coded Tailwind palette colours (`emerald-*`, `sky-*`, `amber-*`, `red-*`) in six files instead of tokens: `HomePage`, `VehicleStatusBadge`, `BookingStatusBadge`, `maintenance/badges`, `LicenceStatusCard`, `form.tsx` (`StatusMessage`). | all |
| G8 | Inconsistent control heights: buttons are 32, 36 or 40 px depending on the page (`h-8`, `h-9`, plus `className="h-10"` overrides); inputs are 40. Radius is 10 px. | all |
| G9 | Badge spam: job rows carry job status, vehicle status and severity pills; dashboard "Not available yet" items carry bright pills. | job lists, dashboard |
| G10 | "Soon" navigation items look the same as live ones, and long labels ("Handover and return") wrap to two lines next to "Soon". | staff, admin, manager |
| G11 | Money is set in the body face, in-line or left-aligned (vehicle cards, booking rows); IDs, plates and dates are not distinguished. | search, bookings, jobs |
| G12 | Two focus styles (`ring-3 ring/50` on controls, `ring-2` on nav links). | all |
| G13 | Chrome autofill paints fields light blue on the dark login form. | /login |

No route had horizontal overflow at 1440, 1024 or 390.

### 1.2 Routes and their current problems, by role

`(Soon)` marks a planned feature that renders the honest `NotAvailablePage`.

**Public (signed out)**

| Route | Page | Problems |
|---|---|---|
| `/` | Home | Two-column layout with the system-status card floating top right; everything sits in the top 300 px, the rest of the screen is empty at 1440 and 1024. Status pills use hard-coded colours. |
| `/login` | Sign in | 360 px card centred near the top; 80 % of the screen empty. No product context. |
| `/register` | Create your account | One long single-column card (1,214 px tall at 1440); emergency contact is a box inside the box. |
| `/verify` | Verify your mobile number | Same floating card; "Send a new code" looks like a second primary action. |
| `/help` | Help | Three paragraphs in `max-w-2xl`; most of the screen empty. |
| `*` | 404 | Left-aligned stub, no structure. |

**Every signed-in role**

| Route | Page | Problems |
|---|---|---|
| `/app` | Welcome (dashboard) | Two-column grid of boxed tiles with chevrons; unavailable items carry bright pills; capped at 896 px. At 390 the tiles become a long stack. |
| `/app/profile` | My profile | Three stacked cards; full-width "Send code" button; 1,178 px tall at 1440 with an empty right half. |
| any guarded route | 403 | Stub like the 404. |
| `/app/*` unknown | 404 | As above. |

**Customer**

| Route | Page | Problems |
|---|---|---|
| `/app/search` | Find a vehicle | Search form in a card; results are a three-column grid of tall cards that repeat the same labels and a boxed price note; price is in-line text, not aligned. |
| `/app/vehicles/:id` | Vehicle detail and booking | `max-w-3xl` column with 40 % of the screen empty at 1440. Price summary and the "Hold this vehicle and pay" action are at the very bottom, below policies, add-ons, discount and terms, so they are off-screen at every width. |
| `/app/bookings` | My bookings | Rows are boxed cards; status filter floats; the amount sits next to the badge with no column. Empty state is a dashed box. |
| `/app/bookings/:id` | Booking detail, invoice | Not viewed live: the demo customer has no bookings (see 1.3). Code review: one card with description list, price table and invoice link. |
| `/app/bookings/:id/pay` | Payment and confirmation | Not viewed live (see 1.3). Code review: two cards, method choice then summary, stacked. |
| `/app/licence` | Driving licence | Status in a card with a pill; "Update licence details" floats below. |

**Branch Staff**

| Route | Page | Problems |
|---|---|---|
| `/app/licences` | Licence checks | Queue rows are boxed; "Refresh" is a secondary button in the header; lots of empty space. |
| `/app/licences/:id` | Review licence | Two cards (details, photos); empty photo slots are grey boxes; Approve and Reject float under the cards. |
| `/app/maintenance` | Maintenance (branch jobs) | Boxed rows with three pills each (G9); problem text truncated at 390. |
| `/app/maintenance/report` | Report a fault | Form in a card at `max-w-2xl`; the Unsafe checkbox is a box inside the box. |
| `/app/maintenance/:id` | Job detail | Pills under the title, then a card; actions ("Cancel job") float below. Schedule form and conflicting-bookings warning only render for a Reported job (see 1.3). |
| `/app/handover` | Handover and return (Soon) | Placeholder box plus "Back to home". |
| `/app/branch-bookings` | Branch bookings (Soon) | As above. |

**Maintenance Technician**

| Route | Page | Problems |
|---|---|---|
| `/app/jobs` | Maintenance jobs | Same boxed rows and pill spam as the branch list. |
| `/app/jobs/:id` | Job detail (start, record work, complete) | "Start job" floats alone in a gap above the card; record-work form only renders on an In Progress job (see 1.3). At 390 the description list stacks label over value with uneven gaps. |

**Administrator**

| Route | Page | Problems |
|---|---|---|
| `/app/licences`, `/app/licences/:id` | Licence checks | As Branch Staff. |
| `/app/maintenance`, `/report`, `/:id` | Maintenance | As Branch Staff. |
| `/app/clearances` | Unsafe clearances | Boxed rows; one waiting job. |
| `/app/maintenance/:id` (awaiting clearance) | Clearance review | Long single column: alert, job card, "Work recorded" card with parts table, then the action. The parts table is the only right-aligned money on the site. |
| `/app/fleet`, `/app/tariffs`, `/app/users`, `/app/reports`, `/app/audit` | (Soon) | Placeholder box. |

**Branch Manager**

| Route | Page | Problems |
|---|---|---|
| `/app/maintenance`, `/report`, `/:id` | Maintenance | As Branch Staff. |
| `/app/branch-bookings`, `/app/reports` | (Soon) | Placeholder box. |

Note: the brief's Stage 5 mentions "fleet" and "branch bookings". Both are
`(Soon)` placeholders today, so Stage 5 restyles the placeholder only and
builds nothing new.

### 1.3 Not seen live in Stage 1

These screens need demo data the accounts don't have, or a state change, so
they were only reviewed in code: booking detail, payment and confirmation
(the demo customer has no bookings); the record-work and complete forms (no
job is In Progress); the schedule form and conflicting-bookings warning (no
job is Reported); the reject dialog; the booking refusal messages. Creating
a booking or starting a job would change the demo database, so Stages 4 to 6
check these with the test suite and the MSW fixtures unless you allow test
data to be created.

### 1.4 Not design, noticed in passing (not to be fixed here)

- `/app/licence` reads "Your licence was verified on —." for the demo
  customer: the verification date is missing in the seed data or the API
  response.
- The "Completed" booking status uses the `PartyPopper` icon. Swap to
  `CircleCheckBig` approved 11 Oct 2026 (icon only, the text stays); done in Stage 2.

## 2. References (patterns only)

Looked at Dribbble searches "car rental dashboard", "fleet management" and
"fleet management dashboard". Linear, Stripe docs and Sixt were attempted;
Stripe and Sixt were blocked by site permissions and Linear's page would not
render screenshots, so their patterns below are from general knowledge of
those products, not from copying.

Taken:

- Dense list rows with a fixed set of aligned columns, one status per row,
  and a quiet chevron; the row, not a box, is the unit (fleet shots, Linear).
- A filter bar across the top of a results list, with results as rows and the
  price as the right-most, right-aligned column (rental listing shots).
- Detail pages as a main column of labelled sections plus a narrow right rail
  for the summary and the primary action (Stripe payment detail).
- Hairline-separated sections with small uppercase-free section titles, and
  page headers with actions on the right (Stripe, Linear).
- A muted sidebar on a slightly darker canvas, active item marked by tint and
  a thin bar (Linear).

Rejected: car-render hero images, glass panels, gradient charts, map
backgrounds, tile dashboards.

## 3. Colour

All colours are CSS variables on `:root`, exposed to Tailwind through
`@theme inline`. The shadcn token names (`background`, `foreground`,
`primary`, `muted`, `border`, ...) stay, and point at the tokens below so the
existing primitives keep working. No hex or Tailwind palette colour appears in
a component.

### 3.1 Neutrals

| Token | Hex | Use |
|---|---|---|
| `--canvas` | `#F7F5F0` | Page background (warm off-white). Maps to `--background`. |
| `--canvas-sunken` | `#F0EDE6` | Sidebar, table header, read-only fields, skeletons. |
| `--surface` | `#FFFFFF` | Inputs, dialogs, sheets, menus, popovers. |
| `--ink` | `#1B1C1D` | Body text, headings, numbers. Maps to `--foreground`. |
| `--ink-muted` | `#55534E` | Secondary text, `dt` labels, descriptions. Maps to `--muted-foreground`. |
| `--ink-subtle` | `#6B6862` | Placeholders, captions, disabled text, "Soon". |
| `--hairline` | `#E3DFD6` | Dividers, table rules, section rules. Maps to `--border`. |
| `--line-strong` | `#8D887E` | Input, select, checkbox and outline-button borders. Maps to `--input`. |

### 3.2 Primary and accent

| Token | Hex | Use |
|---|---|---|
| `--primary` | `#0F5866` | Deep petrol. Primary buttons, links, active nav, focus ring, selected states. |
| `--primary-hover` | `#0B4753` | Hover and pressed state of primary. |
| `--primary-tint` | `#E2ECED` | Active nav background, selected row, info alert background. |
| `--on-primary` | `#FFFFFF` | Text on primary. |
| `--signal` | `#E5A21A` | Signal amber. **Markers only, never text on the canvas:** the active-nav bar, the queue-count marker ("1 licence is waiting"), the payment hold timer marker, the rule under "Total payable". At most one use per screen. |
| `--signal-ink` | `#8A5800` | Amber when it has to be text. |
| `--signal-tint` | `#F7ECD4` | Background behind amber text. |
| `--on-signal` | `#1B1C1D` | Text on a solid amber marker. |

The amber tokens are named `signal`, not `accent`: shadcn/ui already uses
`--accent` for neutral hover fills, and it maps to `canvas-sunken`.

### 3.3 Status colours

Each status keeps its icon and its name (colour is never the only cue,
WCAG 1.4.1). Pills are tint background plus ink text, no border.

| Token pair | Ink | Tint | Meaning |
|---|---|---|---|
| `--status-available` | `#2E6A3E` | `#E3EEE4` | Available, Confirmed, Completed job, Verified, success messages |
| `--status-booked` | `#2B5A8A` | `#E3EBF4` | On Rent, Active booking, Scheduled job |
| `--status-maintenance` | `#8A5800` | `#F7ECD4` | Under Maintenance, In Progress, Pending Payment, Pending licence, High severity |
| `--status-unsafe` | `#A3322A` | `#F6E2DF` | Unsafe, Awaiting clearance, Cancelled and No-show bookings, Rejected, Critical severity, errors. Maps to `--destructive`. |
| `--status-inactive` | `#55534E` | `#EAE7E1` | Retired, Draft, Reported, Cancelled job, Completed booking, Low/Medium severity |

Severity becomes plain text with a small coloured dot instead of a third
outlined pill (fixes G9); the text is unchanged ("Critical severity").

### 3.4 Charts

`--chart-1` primary, `--chart-2` status-booked, `--chart-3`
status-available, `--chart-4` signal-ink, `--chart-5` ink-subtle. Recharts
is installed but no screen draws a chart yet; the tokens exist so a future
report uses the same palette.

### 3.5 Contrast (WCAG 2.1, measured)

| Foreground | Background | Ratio | Needs |
|---|---|---|---|
| ink | canvas / sunken / surface | 15.66 / 14.60 / 17.07 | 4.5 |
| ink-muted | canvas / sunken / surface | 7.05 / 6.57 / 7.68 | 4.5 |
| ink-subtle | canvas / surface / sunken | 5.10 / 5.55 / 4.58 | 4.5 |
| line-strong (control border) | surface / canvas | 3.53 / 3.24 | 3.0 (1.4.11) |
| on-primary | primary / primary-hover | 8.05 / 10.29 | 4.5 |
| primary (link, focus ring) | canvas | 7.39 | 4.5 / 3.0 |
| primary | primary-tint | 6.69 | 4.5 |
| on-signal | signal | 7.73 | 4.5 |
| signal-ink | canvas / signal-tint | 5.54 / 5.15 | 4.5 |
| signal (marker) | canvas | 2.03 | decorative only, never text, never the only cue |
| status-available ink | tint / canvas | 5.42 / 5.94 | 4.5 |
| status-booked ink | tint / canvas | 5.95 / 6.57 | 4.5 |
| status-maintenance ink | tint | 5.15 | 4.5 |
| status-unsafe ink | tint / canvas / surface | 5.53 / 6.33 / 6.89 | 4.5 |
| status-inactive ink | tint | 6.22 | 4.5 |

## 4. Typography

Three roles, three families, all SIL OFL 1.1, self-hosted with Fontsource
(D22). No CDN and no Google Fonts link: the lab may be offline. This is
type system C from `docs/design/type-options.md`, chosen 12 Oct 2026; the
research behind it is recorded there.

| Role | Family | Package | Why |
|---|---|---|---|
| Hero and all headings: home hero, auth-panel heading, page, section and subsection titles, brand | Schibsted Grotesk (variable, weight 650 to 800) with tracking −0.01 to −0.03 em | `@fontsource-variable/schibsted-grotesk` | A grotesk drawn for a news publisher: plain and confident like the custom grotesks rental and fintech brands use (Turo Sans, Lausanne at Ramp, GT Eesti at BlaBlaCar), large and tightly tracked in the hero, compact in app titles (B2). |
| Body and UI | IBM Plex Sans (variable) | `@fontsource-variable/ibm-plex-sans` | Very legible at 13 to 15 px, open apertures, distinct `Il1`, good for forms and dense tables. Pairs with Plex Mono by design. |
| Numbers, prices, dates, IDs, plates | IBM Plex Mono 400 and 500 | `@fontsource/ibm-plex-mono` | Every figure is the same width, so columns of money and dates line up; plates like `MH02DM1006` and IDs read unambiguously. `font-variant-numeric: tabular-nums` is set as well. |

Each package's full axis or weight file is imported: the rupee sign
(U+20B9) is in the Latin Extended subset, and every subset is declared with
a `unicode-range`, so the browser downloads only Latin and Latin Extended in
practice. Formatting logic (`formatCurrency`,
`formatDateTime`, ...) is untouched; only the face changes. A `.num` utility
(Tailwind `font-mono tabular-nums`) is applied where those values render.

### 4.1 Type scale

Base size 16 px everywhere (B3). Line heights on a 2 px grid. Every size is
a token in `index.css`; pages use the token classes and never set a size of
their own.

| Token (class) | Size / line | Family, weight | Use |
|---|---|---|---|
| `display` (`.display`) | clamp(40 at 390, fluid, 76 at 1440) / 1.0 | Schibsted Grotesk 800, −0.03 em | Home hero (the agency name) |
| `title` (`text-title`) | clamp(32, fluid, 36) / 1.17 | Schibsted Grotesk 700, −0.02 em | Page title (`h1`) |
| `section` (`text-section`) | clamp(22, fluid, 24) / 1.27 | Schibsted Grotesk 700, −0.02 em | Section title (`h2`), dialog title, table caption (`.heading`) |
| `subsection` (`text-subsection`) | 19 / 26 | Schibsted Grotesk 650, −0.01 em | `h3`, form group legends (`.heading`) |
| `lead` (`text-lead`) | 19 / 30 | Plex Sans 400 | Public intro, auth-panel facts |
| `body` (`text-sm`, `text-base`) | 16 / 26 | Plex Sans 400 | Default text, inputs, buttons |
| `body-strong` | 16 / 26 | Plex Sans 500 | `dd` values, row titles |
| `small` (`text-small`) | 14 / 22 | Plex Sans 400 | Descriptions, hints, meta; form labels at 500 |
| `label` (`text-xs`) | 13 / 18 | Plex Sans 500 | Table headers, pill text, "Soon", error codes |
| `num` (`.num`) | 15 / 22 | Plex Mono 400, tabular | IDs, dates, plates, amounts in rows |
| `num-strong` (`.num-strong`) | 16 / 26 | Plex Mono 500, tabular | Totals in rows |
| `num-lg` (`.num-lg`) | 28 / 36 | Plex Mono 500, tabular | "Total payable", pickup code |

`text-sm` is the body token (16 px) because the codebase uses it as the
default text class; `text-small` is the 14 px step below it. Weights are
limited to 400 and 500 for Plex, 650, 700 and 800 for Schibsted Grotesk.
Elements that are not `h1` to `h4` but need the heading style (legends,
captions, refusal titles, the brand) use the `.heading` utility. No italics, no all-caps. Controls: 44 px
page actions and inputs, 36 px in-row buttons, 16 px text.

## 5. Space, shape, elevation, motion

- **Spacing:** 4 px base. Steps used: 4, 8, 12, 16, 24, 32, 48. Inside a
  section 16; between sections 32 with a hairline; page header to content 24.
- **Page gutter:** 32 px at ≥1024, 24 at 768, 16 at 390.
- **Content width (B4):** no cap. List and table pages fill the whole main
  area with aligned columns. Detail and form pages use a main column plus a
  320 to 352 px right rail, or the settings layout. Reading pages (help,
  403, 404, placeholders) are two columns: content up to 42 rem on the left,
  "Where to go" on the right.
- **Radius:** 4 px on controls, pills and alerts; 6 px on dialogs, sheets,
  menus and popovers. Nothing larger; avatars stay round.
- **Elevation:** no shadows on page content. Overlays only:
  `0 8px 24px rgba(27,28,29,.12), 0 1px 2px rgba(27,28,29,.08)`. The dialog
  and sheet overlay is `ink` at 40 % opacity, no blur.
- **Motion (B5 to B7):** tokens `--ease-out`, `--ease-in` and the keyframes
  `rise`, `fade`, `flash-out`, `draw` in `index.css`. Utilities: `stage`
  (orchestrated page entry: each direct child rises 350 ms, 50 ms apart, up
  to four steps), `enter` (one element rises on mount, `--enter-delay` for
  stagger from `lib/motion.ts`, first 10 rows only), `reveal` (scroll-driven
  `animation-timeline: view()` where supported, IntersectionObserver
  fallback in `components/reveal.tsx`), `flash` (primary-tint highlight
  fading within 1.2 s), `draw` (the confirmation check draws once).
  Dialogs scale from 0.97 and fade (300 ms in, 150 ms out); the drawer
  slides (300 in, 200 out); the sticky rail docks with its hairline; the top
  bar shows its edge once content scrolls under it; anchor scrolling is
  smooth. Colour transitions 150 ms; pills 300 ms. Only transform, opacity
  and colour: no bounce, loops, parallax, gradients or blur. Under
  `prefers-reduced-motion: reduce` every rise, slide, scale and scroll
  reveal becomes a 150 ms opacity fade, so pages still look finished.
  Money, totals, timers and IDs are never animated (B6).

## 6. Layout patterns

### 6.0 App shell (signed in)

- **Sidebar, ≥768 px:** fixed, full height, 272 px, `canvas-sunken`, hairline
  right edge. Top: agency name (Schibsted Grotesk 700, from `useAgency`, never
  hard-coded, D7). Then the role's navigation from `navItemsFor` (unchanged).
  Active item: `primary-tint` background, `primary` text, a 2 px `signal` bar
  on the left edge. Available items in `ink`. Planned items in `ink-subtle`
  with "Soon" right-aligned in `label` size, no pill, no hover tint, so they
  read as quiet and intentional. Labels never wrap: 272 px is what
  "Handover and return" plus "Soon" needs at 16 px. No name block at the
  bottom: the top bar already shows it, and a second copy would duplicate
  visible text.
- **Top bar:** 64 px, `canvas`, no blur; its hairline edge appears once
  content scrolls under it (B5). Left: the
  phone menu button (below 768 px) and the agency name (phones only, since
  the sidebar is hidden). Right: avatar initials, name and role (≥640 px),
  Help (ghost) and Sign out (outline). Same labels and `aria-label`s as now.
- **Phone drawer:** the existing Sheet, restyled to match the sidebar.
- **Main:** `canvas`, gutter per section 5, no inner box, no width cap
  (B4).
- **Footer:** none exists and none is added (it would be new copy).

### 6.1 Auth: sign in, register, verify OTP

Split layout from 1024 px: form on the left (form column max 26 rem for
sign-in and verify, 36 rem with two-column field pairs for register),
product panel on the right (about half the width). The panel is
`canvas-sunken` with a hairline, ink text, the agency name in the display style and
the facts in `lead`; it is the same material as the sidebar, not a second
colour block (decided 11 Oct 2026 after the solid petrol panel read as two
unrelated halves). No image, no gradient. Below 1024 the panel is hidden and
the form takes the page. The public top bar stays.

Product panel content (approved 11 Oct 2026). Short facts taken only from
copy the app already shows, reworded so no test finds a duplicate. No
prices, ratings, hours, guarantees or "24/7".

| Fact | Reworded from |
|---|---|
| Cars and two-wheelers, free for the dates you choose. | "Search cars and two-wheelers that are free for your dates." (the "Find a vehicle" menu description, `app/navigation.ts`, shown on `/app`) |
| Collect at a branch or have it delivered. | "collect it from a branch or have it delivered" (home page intro, `/`) |
| Pay by card, online, or in cash at the branch. | "pay by card, online or in cash at the branch." (home page intro, `/`) |
| Your driving licence is verified by our staff before you book. | "Our staff verify it before you can book." (Help, "Driving licence", `/help`) |

Also approved (11 Oct 2026) as a proposed addition: the heading "Where to go"
on the help, 403 and 404 pages (section 6.9). It is the only new visible
string outside the panel facts; the links under it reuse the menu labels
and descriptions, or "Sign in" and "Create an account" from the home page.

The agency name heads the panel (from `AGENCY_NAME`).

### 6.2 Public home

Two-column band at the top: agency name (`display`), the existing intro
paragraph and actions on the left; "System status" as a description list on
the right with hairline rows and status pills, "Check again" as a text
button. Below, a hairline and a three-column row of the help topics already
on `/help` ("Signing in", "Verification codes", "Driving licence") as
links-with-summary, so 1440 has no empty lower half. (Approved 11 Oct 2026:
re-uses existing help headings and links; no new claims.)

### 6.2.1 Landing page (Stage 4.6, 12 Oct 2026)

The public home page is a landing page: a centred hero that fills the first
viewport under the top bar (the agency name as the headline, the existing
intro paragraph at about 60 characters, the existing actions, a scroll cue),
then bands revealed on scroll: what the system does, how it works, the
staff side, system status with the help topics, a final call to action and
a slim footer. No numbers, prices, ratings, testimonials, images or claims.
Icons are lucide. Motion: hero entry sequence, section reveals, staggered
lists, smooth anchor scrolling, the top bar's edge on scroll (B5, B7).

Every sentence on it is either an existing string or one of the approved
additions below, each true of the current app or SRS behaviour.

| New text | Source |
|---|---|
| Book online, collect at the branch | Band title; from the home intro ("Book a car ... online ... collect it from a branch"). |
| Search, book and pay online. Our staff verify your driving licence before you can book. | Home intro; Help "Driving licence" ("Our staff verify it before you can book."). |
| Find a vehicle | Existing menu label. Body is the search page description, unchanged. |
| Licence checked by staff | Help "Driving licence"; body reuses its two sentences. |
| Card, online or cash | Home intro ("pay by card, online or in cash at the branch"); second sentence from the price summary ("Refundable security deposit ..., held separately and not part of the total."). |
| Invoices to download / Once you have paid, your booking shows its invoice, ready to download. | History.Download; the booking detail's "Download invoice ..." button. |
| Unsafe vehicles are never offered / Vehicles under maintenance or flagged Unsafe leave search and booking until they are cleared. | Search.Available (only Available vehicles are offered); BR-16; the report-fault hint "It leaves search, booking and handover at once. Only an Administrator can clear the flag". |
| Your booking history | Menu description "Your bookings, invoices and rental history."; body is the bookings page description, unchanged. |
| How it works / Four steps from your account to the keys. | The four customer steps that follow (SE-7, Book.Eligible, Book.Hold, Pay.Authorize). |
| Create your account | Existing page title; body is the register page description, unchanged. |
| Submit your licence | Existing heading on the licence page; body reuses its description and the help sentence. |
| Search and hold | Search page description plus the booking form note "We hold the vehicle for you for 15 minutes while you pay." |
| Pay and collect | Home intro plus the confirmation note "Show this code at the branch to collect the vehicle." and "have it delivered" from the intro. |
| For branch teams / Branch staff, technicians and administrators sign in to the same system. | The roles in `ROLE_LABELS`; UI-1 (one application, menus by role). Items reuse the menu labels and descriptions. |
| Help (section heading) | Existing page title. Topics are the help page's, unchanged. |

**Photography (Stage 4.7B, revised in Stage 4.8, 12 Oct 2026).** Every
landing photo is decorative (`alt=""`) except the category row. From
1024 px the hero photo fills a band at its own shape (no taller than the
first viewport) under `--photo-overlay-strong`, and the agency name, intro
and actions sit on a local `--photo-scrim` panel above the vehicle; the
final call to action is a 3:1 band whose text sits on its left, on the
gutter, over a scrim that fades to transparent before the car. Both use a
white primary and a white outline button there. Below 1024 px both stack:
text on the canvas, then the whole photo. "Book online, collect at the
branch" and "For branch teams" are split rows (a whole photo beside the
list, sides flipped); "System status" has a framed photo above it. No new
text was added in Stage 4.8. The slim
footer moved into the public layout (6.2.2). New text, approved as a
proposed addition with the photo choices:

| New text | Source |
|---|---|
| Cars and two-wheelers (band title) | The auth panel fact "Cars and two-wheelers, free for the dates you choose."; the licence categories Car and Two-Wheeler (D18). |
| Hatchback, Sedan, SUV, Scooter, Motorcycle (category row, display only, no links) | The tariff categories of the demo fleet (`seed_demo` CATEGORIES). If the agency's categories change, change this row. |
| Representative image of a Hatchback (and of a Sedan, of an SUV, of a Scooter, of a Motorcycle) | Alt text of the category photos (imagery-brief.md, 3). |

### 6.2.2 Public footer and photo credits (Stage 4.7B, 12 Oct 2026)

Every public page (home, sign in, register, verify, help, 404, photo
credits) ends with one slim footer: the agency name, then a "Footer" nav
with "Help" and "Photo credits". `/credits` uses the help page's two-column
layout: a list of every photo (thumbnail, title, author, source link,
licence link, changes made), from `src/assets/images/manifest.json`, the
same data as `docs/design/image-credits.md`, with "Where to go" on the
right. New text (D23 requires the credits):

| New text | Source |
|---|---|
| Photo credits (footer link, page title) | D23; the licences' attribution terms (CC BY, CC BY-SA). |
| The photographs in this app, who took them, where they come from and their licences. Vehicle photos are representative images of each model or category, not the vehicles in our fleet. | D23; B12 (representative photos never claim to be the vehicle). |
| By <author>, <source>, <licence> / Changes made: <changes>. | The manifest; CC BY and CC BY-SA require indicating changes. |
| Footer (nav label) | Names the footer's link group for assistive technology. |
| Representative image of a <Make> <Model> | Alt text on search tiles and the vehicle page when the vehicle has no photographs (B12). |

### 6.3 Page header (every signed-in page)

Optional back link above; `title`; one-line description in `ink-muted`;
status pills inline after the title on detail pages; actions right-aligned
on the same baseline (stack under the title below 640 px). A hairline under
the header, 24 px before content.

Stage 4.9 (B14): a page with a header photo uses the image-led frame
instead: from 1024 px the title, the description (lead size) and the
action sit in the left half, vertically centred, and the photo fills the
right half; below 1024 px the photo runs full width above them. The plain
header above stays for record-detail pages (booking, job, vehicle), the
search page, payment, profile and the sign-in screens.

### 6.4 List and queue pages

`/app/bookings`, `/app/maintenance`, `/app/jobs`, `/app/licences`,
`/app/clearances`, and search results.

- A filter row (status select, Refresh) under the header, left-aligned,
  with the count ("4 jobs.") in `ink-muted` on the right.
- Rows, not boxes: the existing `ul`/`li` stays, each `li` is a full-width
  row with a hairline under it and a CSS grid of aligned columns at ≥1024,
  collapsing to two lines below. Row hover tints `canvas-sunken`; the whole
  row is the link where it is today.
- Columns (desktop):
  - Jobs: ID and plate (mono) · type and problem (truncated) · vehicle ·
    technician · from (mono date) · one status pill (job status, or
    "Awaiting clearance"); vehicle status and severity as quiet text with a
    dot.
  - Bookings: vehicle and reference (mono) · period (mono dates) · branch ·
    amount (mono, right-aligned) · status pill.
  - Licence queue: customer · licence number (mono) · categories · submitted
    (mono date).
  - Search results: vehicle (name, year, spec line, category tags as plain
    text) · rating and last serviced · estimated price (mono, right-aligned,
    with the existing note and deposit lines beneath) · "View and book".
- Pagination: "Previous page" / "Next page" outline buttons, right-aligned
  under the list.

### 6.5 Search

The search form becomes one horizontal filter bar at ≥1024 (branch,
category, pickup, return, Search), on `canvas-sunken` with hairlines above
and below, not a card. Two columns at 768, one at 390. Results follow with
the existing heading and summary sentence, as image-led tiles (Stage 4.7B,
B12, imagery-brief.md 3) in the same "Available vehicles" list: one column
at 390, two from 640, three from 1280, four from 1536.

### 6.6 Detail with a side rail

Vehicle detail and booking, booking detail, payment, job detail, licence
review.

- Main column (flexible): sections separated by 32 px and a hairline, each
  with a `section` title and a two-column description list (`dt` 160 px in
  `ink-muted`, `dd` in `ink`, mono for numbers).
- Right rail (320 px, sticky at `top: 64px` from 1024 px): the summary and
  the primary actions.
  - Vehicle detail: the booking period, the price summary table, the deposit
    line, the terms checkbox and "Hold this vehicle and pay". Add-ons and
    discount code stay in the main column. All of it stays inside the same
    `<form>`; only placement changes.
  - Payment: price summary and the hold timer (amber marker); the payment
    method choice is the main column.
  - Booking detail: status, total, invoice download.
  - Job detail: job and vehicle status, primary actions (Start job, Cancel
    job, Clear Unsafe flag and complete); the description list, schedule,
    record-work form and "Work recorded" are the main column.
  - Licence review: Approve and Reject; details and photos in the main
    column (photos as two equal frames with a hairline, empty state text
    centred).
- Below 1024 the rail moves under the main column, not sticky.

### 6.7 Form pages

Report a fault, profile, licence submission, register.

- Settings pattern at ≥1024: each group is a row with the group title and
  its one-line description in a 280 px left column and the fields on the
  right in up to two columns (paired fields such as Job type/Severity,
  Name/Mobile). Groups separated by hairlines. No boxes.
- Checkboxes with explanations (Flag as Unsafe, terms) are a row with the
  checkbox and two lines of text, no inner box. The Unsafe one gets a left
  rule in `status-unsafe` to mark the consequence.
- Submit buttons sit at the end of the group, left-aligned with the fields,
  natural width (not full-width) above 640 px.

### 6.8 Dashboard (`/app`)

Page header, then the role's destinations as a two-column ruled list at
≥1024 (icon, label, description, chevron), one column below. Planned items
sit in a separate group after a hairline, titled with the existing "Not
available yet" text as quiet `ink-subtle` copy, without pills.

Stage 4.9 (B14): the image-led page header, then each available
destination as an image-led tile (a 3:2 photo, then icon, label,
description; the vehicle tiles' family), 2 x 2 from 1024 px and one column
below. Planned destinations follow as compact rows after a hairline, each
with the existing "Not available yet" badge. Labels and descriptions are
unchanged.

### 6.9 Help, 403, 404, placeholders

Two-column at ≥1024: content on the left (error code as `label` in
`ink-muted`, `title`, description, action); on the right a short "Where to
go" list of the role's available nav items (help/404/403) or the item's
description (placeholders). Single column below 1024. The placeholder's
"Not available yet" message becomes a hairline-bounded note with the clock
icon, not a box.

## 7. Component rules (Stage 2)

| Component | Rules |
|---|---|
| Button | Heights: 44 px (`default` and `lg`, all page actions), 36 px (`sm`, in-row actions), 28 px (`xs`). Text 16 px. Radius 4. Variants: primary (petrol), outline (`surface`, `line-strong` border), ghost, destructive (solid `status-unsafe` ink, white text, for irreversible actions only), link. Hover darkens or tints; pressed is `primary-hover`; disabled is 50 % opacity and `not-allowed`. No press translate. Icons 16 px. The per-page `className="h-10"` overrides become no-ops. |
| Focus | One style everywhere: 2 px `primary` outline, 2 px offset (`outline-offset`), on every focusable element including links, rows and nav. |
| Input, textarea, native select, date/time | 44 px, `surface`, 1 px `line-strong`, radius 4, 16 px Plex Sans; numbers and dates typed in mono where the field is numeric (mobile, odometer, date). `color-scheme: light` so native pickers match. Invalid: `status-unsafe` border plus the existing error text. Autofill background forced to `surface`. |
| Label | `label` size, `ink`; hints `small` `ink-muted`; errors `small` `status-unsafe` with the existing icon. |
| Checkbox | 16 px, radius 3, `line-strong` border, checked fill `primary`. |
| Table | Full width, no outer border. Header row `label` size `ink-muted` on `canvas-sunken`, hairline below. Rows 44 px, hairline between. Money and quantity columns right-aligned, mono. Total row: `num-strong`, rule above. Caption as `subsection`. |
| Description list | Two columns (160 px `dt`), 8 px row gap, `dt` `ink-muted`, `dd` `ink` 500; stacks below 640 px with 2 px between `dt` and `dd` and 12 px between pairs. |
| Status pill | 20 px high, radius 4, 12 px Plex Sans 500, 12 px icon, tint background and status ink from 3.3, no border. One status pill per row in lists. |
| Alert (form-level, refusal, info, success) | Radius 4, tint background of its status, 2 px left rule in the status ink, 16 px icon, text in `ink` with the title in 500. No full border. |
| Toast | No toast system exists; `StatusMessage` is the in-page equivalent and uses the alert style. None is added. |
| Dialog, sheet | `surface`, radius 6, overlay shadow from section 5, `ink`/40 overlay, no blur. Title `section`, description `small` `ink-muted`, actions right-aligned. Focus trap and Escape stay as Radix provides. |
| Tabs | None exist today. If one is needed: underline style, 2 px `primary` under the active tab. |
| Pagination | Outline buttons as above, right-aligned. |
| Skeleton | `canvas-sunken` blocks, radius 4, pulse removed under reduced motion. |
| Loading state | Spinner 16 px with the existing label, in the space the content will occupy (no jump). |
| Empty state | Left-aligned in the list area, hairline above and below: 20 px icon in `ink-subtle`, title `body-strong`, description `small`, the existing action. No dashed box. |
| Error state | Alert style with the existing title, message and "Try again". |
| Icons | lucide only, stroke width 1.75 everywhere, 16 px in controls and rows, 20 px in empty states, `aria-hidden` as today. |
| Card | Kept as a component for structure and its `data-slot` (test hook), restyled to no ring, no background, no radius, no padding; card sections become hairline-separated sections. |

## 8. Implementation notes

- Tokens live in `src/index.css`; shadcn aliases map onto them. A small set of
  utilities (`.num`, `.rule`, `.dl`) is defined there.
- `lib/theme.ts` stops following the OS: the app is always light. The `.dark`
  block and every `dark:` class are removed.
- Fonts are imported once in `main.tsx` (full files, `unicode-range` subsets), with
  `font-display: swap`; fallbacks are the current system stack so text
  renders before the fonts load.
- No new runtime dependency other than the three Fontsource packages (D22).

## 9. Stage plan

| Stage | Scope |
|---|---|
| 2 | Tokens, fonts, global styles, shared components (section 7), app shell and page header, `lib/theme.ts` removed (light only). |
| 3 | Home, register, verify, sign in, profile, licence submission and status, help, 403, 404, placeholders. |
| 4 | Search and results, vehicle detail and quote, booking form and summary, payment, confirmation, invoice, booking history and detail, every refusal message. |
| 5 | Maintenance (report, list, conflicts warning, my jobs, record work, complete, awaiting clearance, clearance queue), licence queue and review, Soon placeholders. |
| 6 | Visual QA at 1440, 1280, 1024, 768, 390 for every role and route; `docs/design/ui-qa.md`. |
