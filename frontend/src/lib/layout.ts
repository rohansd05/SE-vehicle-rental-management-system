/**
 * The main column and right rail of a detail page (docs/design/ui-brief.md,
 * 6.6). One column below 1024 px; `minmax(0, 1fr)` lets the column shrink
 * to the page width so a summary table never pushes past the gutter (B13).
 */
export const RAIL_LAYOUT =
  'grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,1fr)_18rem] lg:gap-10 xl:grid-cols-[minmax(0,1fr)_24rem] xl:gap-20'
