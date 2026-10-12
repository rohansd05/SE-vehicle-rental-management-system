import { describe, expect, it } from 'vitest'

import { fitPhoto } from './images'

// A 3:2 photo whose subject is a small car low in the middle.
const smallSubject = { width: 1500, height: 1000, subject: [0.4, 0.6, 0.6, 0.8] as [number, number, number, number] }
// A 3:2 photo whose subject fills almost the whole width.
const wideSubject = { width: 1500, height: 1000, subject: [0.02, 0.2, 0.98, 0.8] as [number, number, number, number] }

describe('fitPhoto (B13)', () => {
  it('shows a photo whole when the frame has its own aspect', () => {
    expect(fitPhoto(wideSubject, 300, 200)).toEqual({ fit: 'cover', position: '50% 50%' })
  })

  it('crops only background, centring the subject', () => {
    // A 3:1 band keeps half the height; the subject (0.6 to 0.8) is centred on 0.7.
    expect(fitPhoto(smallSubject, 300, 100)).toEqual({ fit: 'cover', position: '50% 90%' })
  })

  it('follows the focal point but never pushes the subject out', () => {
    const fit = fitPhoto({ ...smallSubject, focus: [0.5, 0] }, 300, 100)
    // Top-aligned would hide the subject; it is clamped so the box plus 4% stays in view.
    expect(fit.fit).toBe('cover')
    expect(fit.position).toBe('50% 64%')
  })

  it('falls back to contain when no crop keeps the whole subject', () => {
    // A square frame would cut a subject that spans 96% of the width.
    expect(fitPhoto(wideSubject, 200, 200)).toEqual({ fit: 'contain', position: '50% 50%' })
  })
})
