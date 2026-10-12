import { type CSSProperties, useLayoutEffect, useRef, useState } from 'react'

import { fitPhoto, PHOTOS, type PhotoFit, photoSources } from '@/lib/images'
import { cn } from '@/lib/utils'

/**
 * One photo with the shared treatment (docs/design/imagery-brief.md, 4):
 * AVIF and WebP at every width with a JPEG fallback, explicit width and
 * height so nothing shifts while it loads, lazy below the fold. It fades in
 * and settles from 1.03 to 1 once loaded (B5). An empty `alt` marks the
 * photo decorative, and it is then hidden from assistive technology too.
 *
 * The frame's shape comes from `className` (an aspect ratio or a height), or
 * from the photo itself with `aspect="native"`. The photo is fitted to the
 * frame from its subject box and focal point (B13): it is cropped only where
 * the whole subject stays in view, and shown whole (`contain`) otherwise.
 */
export function Photo({
  id,
  alt,
  sizes = '100vw',
  priority = false,
  aspect,
  className,
  imgClassName,
}: {
  id: string
  alt: string
  sizes?: string
  /** Above the fold (the landing hero): load at once, at high priority. */
  priority?: boolean
  /**
   * "native": the frame takes the photo's own aspect ratio, so nothing is
   * cropped (`--photo-aspect`; a wider-screen class such as `lg:aspect-auto`
   * can still override it).
   */
  aspect?: 'native'
  className?: string
  imgClassName?: string
}) {
  const [loaded, setLoaded] = useState(false)
  const entry = PHOTOS[id]
  const frame = useRef<HTMLPictureElement>(null)
  const [fit, setFit] = useState<PhotoFit | null>(null)

  useLayoutEffect(() => {
    const element = frame.current
    if (!element || !entry) return
    const measure = () => {
      const { width, height } = element.getBoundingClientRect()
      const next = fitPhoto(entry, width, height)
      setFit((current) => (current?.fit === next.fit && current.position === next.position ? current : next))
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [entry])

  const sources = photoSources(id)
  if (!sources || !entry) return null
  const decorative = alt === ''
  return (
    <picture
      ref={frame}
      className={cn('block overflow-hidden bg-canvas-sunken', aspect === 'native' && 'aspect-(--photo-aspect)', className)}
      style={aspect === 'native' ? ({ '--photo-aspect': `${entry.width} / ${entry.height}` } as CSSProperties) : undefined}
      aria-hidden={decorative ? true : undefined}
      data-photo={id}
      data-fit={fit?.fit}
    >
      <source type="image/avif" srcSet={sources.avif} sizes={sizes} />
      <source type="image/webp" srcSet={sources.webp} sizes={sizes} />
      <img
        // An image already in the cache can finish before React sees the event.
        ref={(img) => {
          if (img?.complete && img.naturalWidth > 0 && !loaded) setLoaded(true)
        }}
        src={sources.fallback}
        srcSet={sources.jpg}
        sizes={sizes}
        alt={alt}
        width={sources.width}
        height={sources.height}
        loading={priority ? 'eager' : 'lazy'}
        decoding={priority ? 'sync' : 'async'}
        // React 18 does not know fetchPriority yet; the DOM attribute is lowercase.
        {...(priority ? { fetchpriority: 'high' } : {})}
        onLoad={() => setLoaded(true)}
        data-loaded={loaded ? '' : undefined}
        style={{ objectFit: fit?.fit ?? 'cover', objectPosition: fit?.position ?? '50% 50%' }}
        className={cn('photo-in size-full', imgClassName)}
      />
    </picture>
  )
}
