import { useState } from 'react'

import { photoSources } from '@/lib/images'
import { cn } from '@/lib/utils'

/**
 * One photo with the shared treatment (docs/design/imagery-brief.md, 4):
 * AVIF and WebP at every width with a JPEG fallback, an explicit aspect ratio
 * so nothing shifts while it loads, lazy below the fold. It fades in and
 * settles from 1.03 to 1 once loaded (B5). An empty `alt` marks the photo
 * decorative, and it is then hidden from assistive technology too.
 */
export function Photo({
  id,
  alt,
  sizes = '100vw',
  priority = false,
  className,
  imgClassName,
}: {
  id: string
  alt: string
  sizes?: string
  /** Above the fold (the landing hero): load at once, at high priority. */
  priority?: boolean
  className?: string
  imgClassName?: string
}) {
  const [loaded, setLoaded] = useState(false)
  const sources = photoSources(id)
  if (!sources) return null
  const decorative = alt === ''
  return (
    <picture
      className={cn('block overflow-hidden bg-canvas-sunken', className)}
      aria-hidden={decorative ? true : undefined}
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
        className={cn('photo-in size-full object-cover', imgClassName)}
      />
    </picture>
  )
}
