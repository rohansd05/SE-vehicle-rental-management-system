import { X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import type { DamageMark } from './api'

// Handover.Checklist: "existing damage marked on a diagram of the vehicle".
// A top view split into nine areas; each area is a real button, so a mark
// can be placed by touch, mouse or keyboard. A mark is stored at its area's
// centre, in percent of the diagram (x across, y from the front).
const AREAS = [
  ['Front left', 20, 15],
  ['Front', 50, 15],
  ['Front right', 80, 15],
  ['Left side', 20, 50],
  ['Roof and centre', 50, 50],
  ['Right side', 80, 50],
  ['Rear left', 20, 85],
  ['Rear', 50, 85],
  ['Rear right', 80, 85],
] as const

export function VehicleDiagram({
  marks,
  onChange,
}: {
  marks: DamageMark[]
  onChange: (marks: DamageMark[]) => void
}) {
  const update = (index: number, note: string) =>
    onChange(marks.map((mark, i) => (i === index ? { ...mark, note } : mark)))

  return (
    <div className="grid gap-5 @2xl:grid-cols-[16rem_minmax(0,1fr)] @2xl:items-start">
      <div className="relative mx-auto aspect-[1/2] w-full max-w-64">
        {/* The outline: body, windscreen and rear window, in the ink tokens. */}
        <svg viewBox="0 0 100 200" aria-hidden="true" className="absolute inset-0 size-full text-ink-subtle">
          <rect x="12" y="6" width="76" height="188" rx="26" fill="none" stroke="currentColor" strokeWidth="2" />
          <rect x="22" y="46" width="56" height="26" rx="6" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <rect x="22" y="138" width="56" height="20" rx="6" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <div className="absolute inset-0 grid grid-cols-3 grid-rows-3">
          {AREAS.map(([name, x, y]) => (
            <button
              key={name}
              type="button"
              className="rounded-md transition-colors hover:bg-primary-tint focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              aria-label={`Mark damage: ${name}`}
              onClick={() => onChange([...marks, { x, y, note: name }])}
            />
          ))}
        </div>
        {marks.map((mark, index) => (
          <span
            key={index}
            aria-hidden="true"
            className="pointer-events-none absolute grid size-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-status-unsafe text-small font-semibold text-primary-foreground"
            style={{ left: `${mark.x}%`, top: `${mark.y}%`, marginLeft: `${(index % 3) * 6}px` }}
          >
            {index + 1}
          </span>
        ))}
      </div>
      <div className="grid gap-3">
        {marks.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No damage marked. Tap the area of the diagram where the vehicle is already damaged.
          </p>
        ) : (
          <ol className="grid gap-3">
            {marks.map((mark, index) => (
              <li key={index} className="flex items-end gap-2">
                <div className="grid min-w-0 flex-1 gap-1.5">
                  <Label htmlFor={`damage-${index}`}>Mark {index + 1}</Label>
                  <Input
                    id={`damage-${index}`}
                    value={mark.note ?? ''}
                    maxLength={200}
                    onChange={(event) => update(index, event.target.value)}
                  />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  aria-label={`Remove mark ${index + 1}`}
                  onClick={() => onChange(marks.filter((_, i) => i !== index))}
                >
                  <X aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}
