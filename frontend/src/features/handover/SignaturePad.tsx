import { Eraser } from 'lucide-react'
import { forwardRef, type PointerEvent, useEffect, useImperativeHandle, useRef } from 'react'

import { Button } from '@/components/ui/button'

export interface SignaturePadHandle {
  /** The drawn signature as a PNG, or null when nothing is drawn. */
  toBlob: () => Promise<Blob | null>
}

/**
 * Handover.Sign: the customer signs on the branch device's touch screen
 * (Exp 2 UC 7 special requirement). Pointer events cover finger, stylus and
 * mouse. The ink takes the page's foreground colour, so no colour is
 * hard-coded here (B9).
 */
export const SignaturePad = forwardRef<
  SignaturePadHandle,
  { id: string; label: string; signed: boolean; onSignedChange: (signed: boolean) => void; error?: string }
>(function SignaturePad({ id, label, signed, onSignedChange, error }, ref) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)

  useEffect(() => {
    const element = canvas.current
    const context = element?.getContext('2d')
    if (!element || !context) return
    const ratio = window.devicePixelRatio || 1
    element.width = element.clientWidth * ratio
    element.height = element.clientHeight * ratio
    context.scale(ratio, ratio)
    context.lineWidth = 2.5
    context.lineCap = 'round'
    context.lineJoin = 'round'
    context.strokeStyle = getComputedStyle(element).color
  }, [])

  useImperativeHandle(ref, () => ({
    toBlob: () =>
      new Promise((resolve) => {
        if (!signed || !canvas.current) return resolve(null)
        canvas.current.toBlob((blob) => resolve(blob), 'image/png')
      }),
  }))

  const point = (event: PointerEvent<HTMLCanvasElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    return [event.clientX - box.left, event.clientY - box.top] as const
  }

  const start = (event: PointerEvent<HTMLCanvasElement>) => {
    event.currentTarget.setPointerCapture?.(event.pointerId)
    drawing.current = true
    const context = event.currentTarget.getContext('2d')
    const [x, y] = point(event)
    context?.beginPath()
    context?.moveTo(x, y)
  }

  const move = (event: PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return
    const context = event.currentTarget.getContext('2d')
    const [x, y] = point(event)
    context?.lineTo(x, y)
    context?.stroke()
    if (!signed) onSignedChange(true)
  }

  const clear = () => {
    const element = canvas.current
    element?.getContext('2d')?.clearRect(0, 0, element.width, element.height)
    onSignedChange(false)
  }

  return (
    <div className="grid gap-2">
      <span id={`${id}-label`} className="text-label font-medium text-foreground">
        {label}
      </span>
      <canvas
        ref={canvas}
        id={id}
        role="img"
        aria-labelledby={`${id}-label`}
        aria-describedby={error ? `${id}-error` : `${id}-hint`}
        aria-invalid={error ? true : undefined}
        className="h-48 w-full touch-none rounded-md border border-input bg-surface text-foreground aria-invalid:border-destructive"
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={() => (drawing.current = false)}
        onPointerLeave={() => (drawing.current = false)}
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p id={`${id}-hint`} className="text-small text-muted-foreground">
          {signed ? 'Signed.' : 'The customer signs here with a finger or stylus.'}
        </p>
        <Button type="button" variant="outline" size="sm" onClick={clear} disabled={!signed}>
          <Eraser aria-hidden="true" />
          Clear signature
        </Button>
      </div>
      {error ? (
        <p id={`${id}-error`} className="enter text-small font-medium text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
})
