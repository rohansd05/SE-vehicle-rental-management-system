# VRMS UI redesign: audit and design brief

Stage 1 of the frontend redesign (11 Oct 2026). This brief is the reference
for Stages 2 to 6. It changes how the app looks, never what it does.

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
(D22). No CDN and no Google Fonts link: the lab may be offline.

| Role | Family | Package | Why |
|---|---|---|---|
| Headings, brand, page titles | Archivo (variable, weight 500 to 700; width axis if the package ships it) | `@fontsource-variable/archivo` | A grotesque drawn for both print and screen, with a squared, engineered feel close to automotive signage. Slightly expanded width on page titles gives the "industrial" tone without a display face. |
| Body and UI | IBM Plex Sans (variable) | `@fontsource-variable/ibm-plex-sans` | Very legible at 13 to 15 px, open apertures, distinct `Il1`, good for forms and dense tables. Pairs with Plex Mono by design. |
| Numbers, prices, dates, IDs, plates | IBM Plex Mono 400 and 500 | `@fontsource/ibm-plex-mono` | Every figure is the same width, so columns of money and dates line up; plates like `MH02DM1006` and IDs read unambiguously. `font-variant-numeric: tabular-nums` is set as well. |

Each package's full axis or weight file is imported: the rupee sign
(U+20B9) is in the Latin Extended subset, and every subset is declared with
a `unicode-range`, so the browser downloads only Latin and Latin Extended in
practice. Formatting logic (`formatCurrency`,
`formatDateTime`, ...) is untouched; only the face changes. A `.num` utility
(Tailwind `font-mono tabular-nums`) is applied where those values render.

### 4.1 Type scale

Base size 14 px in the app (dense operations UI), 16 px for lead text on
public pages. Line heights on a 4 px grid.

| Token | Size / line | Family, weight | Use |
|---|---|---|---|
| `display` | 32 / 40 | Archivo 650, width 108 % | Public home title only |
| `title` | 24 / 32 | Archivo 600, width 104 % | Page title (`h1`) |
| `section` | 17 / 24 | Archivo 600 | Section title (`h2`), dialog title |
| `subsection` | 14 / 20 | Archivo 600 | `h3`, table caption, form group |
| `lead` | 16 / 26 | Plex Sans 400 | Public intro, auth panel |
| `body` | 14 / 22 | Plex Sans 400 | Default text |
| `body-strong` | 14 / 22 | Plex Sans 500 | `dd` values, row titles |
| `small` | 13 / 20 | Plex Sans 400 | Descriptions, hints, meta |
| `small` (label) | 13 / 20 | Plex Sans 500 | Form labels |
| `label` | 12 / 16 | Plex Sans 500 | Table headers, pill text, "Soon" |
| `num` | 13 / 20 | Plex Mono 400 | IDs, dates, plates, amounts in rows |
| `num-strong` | 14 / 22 | Plex Mono 500 | Totals |
| `num-lg` | 20 / 28 | Plex Mono 500 | "Total payable" in the booking summary |

Weights are limited to 400, 500 and 600 (Archivo up to 650). No italics, no
all-caps.

## 5. Space, shape, elevation, motion

- **Spacing:** 4 px base. Steps used: 4, 8, 12, 16, 24, 32, 48. Inside a
  section 16; between sections 32 with a hairline; page header to content 24.
- **Page gutter:** 32 px at ≥1024, 24 at 768, 16 at 390.
- **Content width:** list and table pages use the full content area up to
  1280 px. Detail and form pages use a main column plus a 320 px right rail.
  Reading pages (help, 403, 404, placeholders) cap text at 680 px but sit in
  a two-column page so the right side is used (see 6).
- **Radius:** 4 px on controls, pills and alerts; 6 px on dialogs, sheets,
  menus and popovers. Nothing larger; avatars stay round.
- **Elevation:** no shadows on page content. Overlays only:
  `0 8px 24px rgba(27,28,29,.12), 0 1px 2px rgba(27,28,29,.08)`. The dialog
  and sheet overlay is `ink` at 40 % opacity, no blur.
- **Motion:** 120 ms colour and background transitions only. Dialog and
  sheet keep a short fade/slide, all of it removed under
  `prefers-reduced-motion: reduce`, as are spinners' rotation speed-ups and
  skeleton pulses. No `translate-y` press effect.

## 6. Layout patterns

### 6.0 App shell (signed in)

- **Sidebar, ≥768 px:** fixed, full height, 256 px, `canvas-sunken`, hairline
  right edge. Top: agency name (Archivo 600, from `useAgency`, never
  hard-coded, D7). Then the role's navigation from `navItemsFor` (unchanged).
  Active item: `primary-tint` background, `primary` text, a 2 px `signal` bar
  on the left edge. Available items in `ink`. Planned items in `ink-subtle`
  with "Soon" right-aligned in `label` size, no pill, no hover tint, so they
  read as quiet and intentional. Labels never wrap: 256 px (not 240) is what
  "Handover and return" plus "Soon" needs at 14 px. No name block at the
  bottom: the top bar already shows it, and a second copy would duplicate
  visible text.
- **Top bar:** 56 px, `canvas`, hairline bottom edge, no blur. Left: the
  phone menu button (below 768 px) and the agency name (phones only, since
  the sidebar is hidden). Right: avatar initials, name and role (≥640 px),
  Help (ghost) and Sign out (outline). Same labels and `aria-label`s as now.
- **Phone drawer:** the existing Sheet, restyled to match the sidebar.
- **Main:** `canvas`, gutter per section 5, no inner box, content up to
  1280 px.
- **Footer:** none exists and none is added (it would be new copy).

### 6.1 Auth: sign in, register, verify OTP

Split layout from 1024 px: form on the left (form column max 400 px for
sign-in and verify, 560 px with two-column field pairs for register),
product panel on the right (40 % width, solid `primary`, `on-primary` text,
no image, no gradient). Below 1024 the panel is hidden and the form takes the
page. The public top bar stays.

Product panel content (approved 11 Oct 2026). Short facts taken only from
copy the app already shows, reworded so no test finds a duplicate. No
prices, ratings, hours, guarantees or "24/7".

| Fact | Reworded from |
|---|---|
| Cars and two-wheelers, free for the dates you choose. | "Search cars and two-wheelers that are free for your dates." (the "Find a vehicle" menu description, `app/navigation.ts`, shown on `/app`) |
| Collect at a branch or have it delivered. | "collect it from a branch or have it delivered" (home page intro, `/`) |
| Pay by card, online, or in cash at the branch. | "pay by card, online or in cash at the branch." (home page intro, `/`) |
| Your driving licence is verified by our staff before you book. | "Our staff verify it before you can book." (Help, "Driving licence", `/help`) |

The agency name heads the panel (from `AGENCY_NAME`).

### 6.2 Public home

Two-column band at the top: agency name (`display`), the existing intro
paragraph and actions on the left; "System status" as a description list on
the right with hairline rows and status pills, "Check again" as a text
button. Below, a hairline and a three-column row of the help topics already
on `/help` ("Signing in", "Verification codes", "Driving licence") as
links-with-summary, so 1440 has no empty lower half. (Approved 11 Oct 2026:
re-uses existing help headings and links; no new claims.)

### 6.3 Page header (every signed-in page)

Optional back link above; `title`; one-line description in `ink-muted`;
status pills inline after the title on detail pages; actions right-aligned
on the same baseline (stack under the title below 640 px). A hairline under
the header, 24 px before content.

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
and below, not a card. Two columns at 768, one at 390. Results follow as in
6.4 with the existing heading and summary sentence.

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
| Button | Heights: 40 px (`default` and `lg`, all page actions), 32 px (`sm`, in-row actions), 24 px (`xs`). Radius 4. Variants: primary (petrol), outline (`surface`, `line-strong` border), ghost, destructive (solid `status-unsafe` ink, white text, for irreversible actions only), link. Hover darkens or tints; pressed is `primary-hover`; disabled is 50 % opacity and `not-allowed`. No press translate. Icons 16 px. The per-page `className="h-10"` overrides become no-ops. |
| Focus | One style everywhere: 2 px `primary` outline, 2 px offset (`outline-offset`), on every focusable element including links, rows and nav. |
| Input, textarea, native select, date/time | 40 px, `surface`, 1 px `line-strong`, radius 4, 14 px Plex Sans; numbers and dates typed in mono where the field is numeric (mobile, odometer, date). `color-scheme: light` so native pickers match. Invalid: `status-unsafe` border plus the existing error text. Autofill background forced to `surface`. |
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
