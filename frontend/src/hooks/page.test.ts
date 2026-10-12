import { describe, expect, it } from 'vitest'

import { brandName, PRODUCT_NAME } from './page'

describe('brandName (D7, D24)', () => {
  it('uses the configured AGENCY_NAME from the health endpoint', () => {
    expect(brandName('Test Rentals')).toBe('Test Rentals')
  })

  it('falls back to Veyora while the name is unset or still the bracketed placeholder', () => {
    expect(PRODUCT_NAME).toBe('Veyora')
    expect(brandName(undefined)).toBe('Veyora')
    expect(brandName('')).toBe('Veyora')
    expect(brandName('[Placeholder]')).toBe('Veyora')
  })
})
