// Money display (CO-6, D7). The API sends amounts as decimal strings; they are
// formatted for display only and never used for arithmetic in the browser.
// Every amount shown must be itemised (UI-4).

const formatters = new Map<string, Intl.NumberFormat>()

export function formatCurrency(amount: string | number, currency = 'INR'): string {
  let formatter = formatters.get(currency)
  if (!formatter) {
    formatter = new Intl.NumberFormat('en-IN', { style: 'currency', currency })
    formatters.set(currency, formatter)
  }
  return formatter.format(typeof amount === 'string' ? Number(amount) : amount)
}

export const formatINR = (amount: string | number): string => formatCurrency(amount, 'INR')
