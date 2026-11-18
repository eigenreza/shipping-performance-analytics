// Loads the precomputed JSON written by `spa demo-export`, once per file.
const cache = new Map<string, Promise<unknown>>()

export function load<T>(name: string): Promise<T> {
  if (!cache.has(name)) {
    cache.set(
      name,
      fetch(`/data/${name}.json`, { cache: 'no-cache' }).then((r) => {
        if (!r.ok) throw new Error(`Could not load ${name}`)
        return r.json()
      }),
    )
  }
  return cache.get(name) as Promise<T>
}

export type ShipYear = {
  ship: string
  segment: string
  year: number
  size: string
  flag: string
  gen: string
  gt: number | null
  co2: number
  fuel: number
  dist: number | null
  hours: number | null
  speed: number | null
  co2nm: number | null
  ets_scope: number
  eua: number
  ets_cost: number
  cii: string | null
  cii_ratio: number | null
  worse: boolean
  ok: boolean
}

type Table = { columns: string[]; rows: unknown[][] }

export async function loadFleet(): Promise<ShipYear[]> {
  const t = await load<Table>('fleet')
  return t.rows.map((r) => Object.fromEntries(t.columns.map((c, i) => [c, r[i]])) as ShipYear)
}

export const SEGMENTS = ['Vehicle carrier', 'Ro-ro ship'] as const
export const YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

/** CO2 per nautical mile and speed over quality-checked ship-years, the same rule as the Power BI measures. */
export function efficiency(rows: ShipYear[]) {
  const ok = rows.filter((r) => r.ok && r.dist && r.hours)
  const co2 = ok.reduce((s, r) => s + r.co2, 0)
  const dist = ok.reduce((s, r) => s + (r.dist ?? 0), 0)
  const hours = ok.reduce((s, r) => s + (r.hours ?? 0), 0)
  return { co2nm: dist ? (co2 * 1000) / dist : null, speed: hours ? dist / hours : null }
}

export function sum(rows: ShipYear[], key: 'co2' | 'fuel' | 'ets_cost' | 'eua' | 'ets_scope') {
  return rows.reduce((s, r) => s + (r[key] ?? 0), 0)
}

export function shareDE(rows: ShipYear[]) {
  const rated = rows.filter((r) => r.cii)
  if (!rated.length) return null
  return rated.filter((r) => r.cii === 'D' || r.cii === 'E').length / rated.length
}
