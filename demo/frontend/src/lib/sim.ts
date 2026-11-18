// The home-page simulator. Same formulas as the Python scenario module and the dbt CII model:
//   CO2 and fuel at the new speed  = base x (1 + speed change)^b    (same distance sailed)
//   EU ETS cost saved              = CO2 in ETS scope saved x surrender share of the year x carbon price
//   extra time at sea              = hours at sea x (1 / (1 + speed change) - 1)
//   cost of that time              = extra ship-days x cost of one day at sea
//   CII ratio in a later year      = ratio x (1 - Z base year) / (1 - Z year), then x (1 + speed change)^b
import { load } from './data'

// segment, CO2 t, fuel t, hours at sea, CO2 in EU ETS scope t, CII ratio in millionths, distance nm
type ShipRow = [string, number, number, number, number, number | null, number]

export type SimData = {
  base_year: number
  segments: string[]
  columns: string[]
  ships: ShipRow[]
  years: number[]
  cii_reduction_millionths: Record<string, number>
  ets_share: Record<string, number>
  cii_bounds: Record<string, number[]>
  fuel_price: number
  day_cost: number
  carbon_price: number
  carbon_price_basis: string
  carbon_price_range: [number, number]
  elasticity: { data: number; data_low: number; data_high: number; engineering: number }
}

export type Reaction = 'engineering' | 'data'

export type Inputs = {
  speed: number
  year: number
  carbon: number
  fuel: number
  dayCost: number
  fleet: string
  reaction: Reaction
}

export const LETTERS = ['A', 'B', 'C', 'D', 'E'] as const
export const SPEED_MIN = -0.2
export const SPEED_MAX = 0.1

export function loadSim() {
  return load<SimData>('simulator')
}

export function exponent(d: SimData, r: Reaction) {
  return r === 'engineering' ? d.elasticity.engineering : d.elasticity.data
}

function letter(ratio: number, bounds: number[]) {
  const i = bounds.findIndex((b) => ratio < b)
  return i === -1 ? 4 : i
}

export function select(d: SimData, fleet: string) {
  return d.ships.filter((s) => fleet === 'All' || s[0] === fleet)
}

type Totals = { ships: number; co2: number; fuel: number; hours: number; scope: number; dist: number }

function totals(rows: ShipRow[]): Totals {
  const t = { ships: rows.length, co2: 0, fuel: 0, hours: 0, scope: 0, dist: 0 }
  for (const s of rows) {
    t.co2 += s[1]
    t.fuel += s[2]
    t.hours += s[3]
    t.scope += s[4]
    t.dist += s[6]
  }
  return t
}

/** Yearly money for one speed change: fuel and carbon saved, cost of the extra days, and the net. */
function money(d: SimData, t: Totals, inp: Inputs, speed: number, b: number) {
  const cut = 1 - Math.pow(1 + speed, b)
  const share = d.ets_share[String(inp.year)] ?? 1
  const fuelEur = t.fuel * cut * inp.fuel
  const etsEur = t.scope * cut * share * inp.carbon
  const shipDays = (t.hours * (1 / (1 + speed) - 1)) / 24
  const timeEur = shipDays * inp.dayCost
  return { cut, fuelEur, etsEur, savedEur: fuelEur + etsEur, shipDays, timeEur, netEur: fuelEur + etsEur - timeEur }
}

/** The curve over all speed changes on the knob, for one fuel reaction. */
export function curve(d: SimData, inp: Inputs, b: number) {
  const t = totals(select(d, inp.fleet))
  const out: { speed: number; saved: number; time: number; net: number }[] = []
  for (let i = 0; i <= 60; i++) {
    const s = SPEED_MIN + (i * (SPEED_MAX - SPEED_MIN)) / 60
    const m = money(d, t, inp, s, b)
    out.push({ speed: s, saved: m.savedEur, time: m.timeEur, net: m.netEur })
  }
  return out
}

/** Speed change with the highest net gain, on the knob's 1 percentage point steps. */
function best(d: SimData, t: Totals, inp: Inputs, b: number) {
  let top = { speed: 0, net: 0 }
  for (let i = Math.round(SPEED_MIN * 100); i <= Math.round(SPEED_MAX * 100); i++) {
    const s = i / 100
    const net = money(d, t, inp, s, b).netEur
    if (net > top.net + 1e-6) top = { speed: s, net }
  }
  return top
}

export function compute(d: SimData, inp: Inputs) {
  const rows = select(d, inp.fleet)
  const t = totals(rows)
  const b = exponent(d, inp.reaction)
  const m = money(d, t, inp, inp.speed, b)
  const factor = 1 - m.cut
  const z = (y: number) => d.cii_reduction_millionths[String(y)] / 1e6
  const tighten = (1 - z(d.base_year)) / (1 - z(inp.year))

  const before = [0, 0, 0, 0, 0]
  const after = [0, 0, 0, 0, 0]
  for (const s of rows) {
    if (s[5] === null) continue
    const ratio = (s[5] / 1e6) * tighten
    const bounds = d.cii_bounds[s[0]]
    before[letter(ratio, bounds)] += 1
    after[letter(ratio * factor, bounds)] += 1
  }
  const rated = before.reduce((a, x) => a + x, 0)
  const other: Reaction = inp.reaction === 'engineering' ? 'data' : 'engineering'
  const mo = money(d, t, inp, inp.speed, exponent(d, other))
  const lo = 1 - Math.pow(1 + inp.speed, d.elasticity.data_low)
  const hi = 1 - Math.pow(1 + inp.speed, d.elasticity.data_high)
  const baseSpeed = t.hours ? t.dist / t.hours : null
  const fitLow = money(d, t, inp, inp.speed, d.elasticity.data_low).netEur
  const fitHigh = money(d, t, inp, inp.speed, d.elasticity.data_high).netEur

  return {
    ships: t.ships,
    rated,
    b,
    co2: t.co2,
    co2Saved: t.co2 * m.cut,
    co2Share: m.cut,
    co2Interval: inp.reaction === 'data' ? [t.co2 * Math.min(lo, hi), t.co2 * Math.max(lo, hi)] : null,
    fuelEur: m.fuelEur,
    etsEur: m.etsEur,
    savedEur: m.savedEur,
    timeEur: m.timeEur,
    netEur: m.netEur,
    netPerShip: t.ships ? m.netEur / t.ships : 0,
    other,
    otherNetEur: mo.netEur,
    otherCo2Saved: t.co2 * mo.cut,
    fitRange: [Math.min(fitLow, fitHigh), Math.max(fitLow, fitHigh)] as [number, number],
    etsShare: d.ets_share[String(inp.year)] ?? 1,
    extraDaysPerShip: t.ships ? m.shipDays / t.ships : 0,
    extraShipDays: m.shipDays,
    breakEven: Math.abs(m.shipDays) > 1e-9 ? m.savedEur / m.shipDays : null,
    best: best(d, t, inp, b),
    otherBest: best(d, t, inp, exponent(d, other)),
    baseKnots: baseSpeed,
    newKnots: baseSpeed === null ? null : baseSpeed * (1 + inp.speed),
    before,
    after,
    deBefore: rated ? (before[3] + before[4]) / rated : null,
    deAfter: rated ? (after[3] + after[4]) / rated : null,
    tighter: 1 - 1 / tighten,
  }
}

export type Result = ReturnType<typeof compute>
