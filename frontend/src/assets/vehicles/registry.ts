// Display-only vehicle imagery (binding decision B12, imagery-brief.md 3).
// Maps a normalised "make model" to its representative photo, with one photo
// per category as the fallback. No API call changes: a vehicle's own photos
// from the API always come first, and these are used only when it has none.
// Photo ids refer to src/assets/images/manifest.json.

const MODELS: Record<string, string> = {
  'maruti suzuki swift': 'model-maruti-suzuki-swift-1',
  'hyundai i20': 'model-hyundai-i20-1',
  'tata tiago ev': 'model-tata-tiago-ev-1',
  'honda city': 'model-honda-city-1',
  'hyundai verna': 'model-hyundai-verna-1',
  'maruti suzuki dzire': 'model-maruti-suzuki-dzire-1',
  'mahindra xuv700': 'model-mahindra-xuv700-1',
  'tata nexon': 'model-tata-nexon-1',
  'hyundai creta': 'model-hyundai-creta-1',
  'kia seltos': 'model-kia-seltos-1',
  'toyota innova crysta': 'model-toyota-innova-crysta-1',
  'mahindra thar': 'model-mahindra-thar-1',
  'maruti suzuki baleno': 'model-maruti-suzuki-baleno-1',
  'hyundai venue': 'model-hyundai-venue-1',
  'honda activa 6g': 'model-honda-activa-6g-1',
  'tvs jupiter': 'model-tvs-jupiter-1',
  'suzuki access 125': 'model-suzuki-access-125-1',
  'tvs ntorq 125': 'model-tvs-ntorq-125-1',
  'royal enfield classic 350': 'model-royal-enfield-classic-350-1',
  'bajaj pulsar 150': 'model-bajaj-pulsar-150-1',
  'yamaha fz-s': 'model-yamaha-fz-s-1',
  'honda dio': 'model-honda-dio-1',
  'bajaj platina 110': 'model-bajaj-platina-110-1',
  // Honda Shine: no usable licensed photo was found; the category photo is used.
}

/** One photo per category, chosen 12 Oct 2026; the scooter photo is the Jupiter's (same Commons file). */
export const CATEGORIES: Record<string, string> = {
  hatchback: 'cat-hatchback-2',
  sedan: 'cat-sedan-2',
  suv: 'cat-suv-1',
  scooter: 'model-tvs-jupiter-1',
  motorcycle: 'cat-motorcycle-2',
}

const normalise = (value: string) => value.toLowerCase().replace(/\s+/g, ' ').trim()

/** "Representative image of a Sedan", "... of an SUV": honest alt text for a representative photo. */
export function representativeAlt(name: string): string {
  const article = /^(?:[aeiou]|suv\b)/i.test(name.trim()) ? 'an' : 'a'
  return `Representative image of ${article} ${name}`
}

export interface RepresentativeImage {
  /** Photo id in the image manifest. */
  id: string
  /** Honest alt text: it never claims to be the vehicle itself. */
  alt: string
}

/** The exact-model photo, else the category photo, else null. */
export function representativeImage(vehicle: {
  brand: string
  model: string
  category: string
}): RepresentativeImage | null {
  const model = MODELS[normalise(`${vehicle.brand} ${vehicle.model}`)]
  if (model) return { id: model, alt: representativeAlt(`${vehicle.brand} ${vehicle.model}`) }
  const category = CATEGORIES[normalise(vehicle.category)]
  if (category) return { id: category, alt: representativeAlt(vehicle.category) }
  return null
}
