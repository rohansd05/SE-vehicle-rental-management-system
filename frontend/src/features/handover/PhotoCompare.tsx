// Return.Checklist: "display the handover and return photographs together so
// that new damage can be identified". Photos come through signed links (SI-3).

import type { ConditionReport } from './api'

const FRAME = 'aspect-[4/3] w-full rounded-md border object-cover'
const EMPTY = 'grid aspect-[4/3] w-full place-items-center rounded-md border bg-muted px-4 text-center text-sm text-muted-foreground'

function photoOf(report: ConditionReport | null, side: string) {
  return report?.photos.find((photo) => photo.caption === side && photo.url) ?? null
}

/** The handover photo of one side, or a note when none was taken. */
export function HandoverPhoto({ report, side }: { report: ConditionReport | null; side: string }) {
  const photo = photoOf(report, side)
  return (
    <figure className="grid content-start gap-2">
      <figcaption className="text-label font-medium">{side} at handover</figcaption>
      {photo?.url ? (
        <img src={photo.url} alt={`${side} of the vehicle at handover`} className={FRAME} />
      ) : (
        <p className={EMPTY}>No photo was taken at handover.</p>
      )}
    </figure>
  )
}

/** Each side at handover beside the same side at return. */
export function PhotoCompare({
  sides,
  handover,
  returned,
}: {
  sides: string[]
  handover: ConditionReport | null
  returned: ConditionReport
}) {
  return (
    <ul aria-label="Handover and return photos" className="@container grid gap-8">
      {sides.map((side) => {
        const photo = photoOf(returned, side)
        return (
          <li key={side} className="grid gap-4 @xl:grid-cols-2">
            <HandoverPhoto report={handover} side={side} />
            <figure className="grid content-start gap-2">
              <figcaption className="text-label font-medium">{side} at return</figcaption>
              {photo?.url ? (
                <img src={photo.url} alt={`${side} of the vehicle at return`} className={FRAME} />
              ) : (
                <p className={EMPTY}>No photo was taken at return.</p>
              )}
            </figure>
          </li>
        )
      })}
    </ul>
  )
}
