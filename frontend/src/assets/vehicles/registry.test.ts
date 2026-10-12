import { describe, expect, it } from 'vitest'

import { representativeImage } from './registry'

describe('representativeImage (B12)', () => {
  it('uses the exact-model photo, matching make and model loosely', () => {
    expect(representativeImage({ brand: 'Maruti  Suzuki', model: 'SWIFT', category: 'Hatchback' })).toEqual({
      id: 'model-maruti-suzuki-swift-1',
      alt: 'Representative image of a Maruti  Suzuki SWIFT',
    })
  })

  it('falls back to the category photo when the model has none', () => {
    expect(representativeImage({ brand: 'Honda', model: 'Shine', category: 'Motorcycle' })).toEqual({
      id: 'cat-motorcycle-2',
      alt: 'Representative image of a Motorcycle',
    })
  })

  it('uses "an" before a vowel sound', () => {
    expect(representativeImage({ brand: 'Acme', model: 'Rover', category: 'SUV' })?.alt).toBe(
      'Representative image of an SUV',
    )
  })

  it('returns null when neither the model nor the category is known', () => {
    expect(representativeImage({ brand: 'Acme', model: 'Rover', category: 'Tractor' })).toBeNull()
  })
})
