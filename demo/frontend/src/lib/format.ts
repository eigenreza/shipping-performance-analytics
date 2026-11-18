// One number format for the whole demo (American English).
const nf = (d: number) => new Intl.NumberFormat('en-US', { maximumFractionDigits: d, minimumFractionDigits: d })

export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return 'n/a'
  return nf(digits).format(v)
}

/** Large values as "4.30 million" style text. */
export function big(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return 'n/a'
  const a = Math.abs(v)
  if (a >= 1e9) return `${nf(digits).format(v / 1e9)} billion`
  if (a >= 1e6) return `${nf(digits).format(v / 1e6)} million`
  if (a >= 1e4) return `${nf(1).format(v / 1e3)} thousand`
  return nf(0).format(v)
}

export function eur(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return 'n/a'
  return `EUR ${big(v, digits)}`
}

export function pct(v: number | null | undefined, digits = 1, signed = false): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return 'n/a'
  const s = nf(digits).format(v * 100)
  return `${signed && v > 0 ? '+' : ''}${s}%`
}
