/**
 * The main column and right rail of a detail page (docs/design/ui-brief.md,
 * 6.6). One column below 1024 px; `minmax(0, 1fr)` lets the column shrink
 * to the page width so a summary table never pushes past the gutter (B13).
 */
export const RAIL_LAYOUT =
  'grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,1fr)_18rem] lg:gap-10 xl:grid-cols-[minmax(0,1fr)_24rem] xl:gap-20'

/**
 * A settings-style section (licence, profile; ui-brief.md 6.7): its title
 * and description in a label column, the content beside it from 1024 px.
 * The label column sticks while long content scrolls past (B14).
 */
export const SETTINGS_ROW =
  'lg:grid lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-x-10 2xl:grid-cols-[16rem_minmax(0,1fr)] 2xl:gap-x-12'
export const SETTINGS_LABEL = 'content-start lg:sticky lg:top-24 lg:self-start'

/**
 * A description list on a detail page (ui-brief.md 6.6): label column and
 * value column on shared baselines once its container is 28 rem wide,
 * label above value below that. The parent needs `@container`.
 */
export const DETAILS_LIST =
  'grid gap-x-6 gap-y-1 text-sm @md:grid-cols-[12rem_minmax(0,1fr)] @md:items-baseline @md:gap-y-3 [&>dd]:mb-3 @md:[&>dd]:mb-0'

/**
 * A form laid out in settings-style rows (ui-brief.md 6.7): put FORM on the
 * <form> and FORM_INDENT on content that belongs in the field column (a
 * fieldset, the submit row), so it lines up with the fields once the form
 * is 48 rem wide.
 */
export const FORM = '@container/form grid gap-5'
export const FORM_INDENT = '@3xl/form:ml-[13.5rem]'
