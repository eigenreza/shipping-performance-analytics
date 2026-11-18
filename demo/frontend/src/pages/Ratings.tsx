import { useEffect, useMemo, useState } from 'react'
import Chart, { axisStyle, tooltipStyle } from '../components/Chart'
import { Answer, Card, Kpi, Legend, Loading, PageIntro, Segmented, nav } from '../components/ui'
import { load, loadFleet, SEGMENTS, shareDE, type ShipYear } from '../lib/data'
import { num, pct } from '../lib/format'
import { RATING_COLOR } from '../lib/theme'
import { useDetailed } from '../lib/view'

const LETTERS = ['A', 'B', 'C', 'D', 'E']
const RATED_YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]

export default function Ratings() {
  const [rows, setRows] = useState<ShipYear[] | null>(null)
  const [segment, setSegment] = useState('Vehicle carrier')
  const [z, setZ] = useState<{ year: number; z: number }[]>([])
  const [firstYear, setFirstYear] = useState<number | null>(null)
  const detailed = useDetailed()
  useEffect(() => {
    loadFleet().then(setRows)
    load<any>('build').then((b) => setZ(b.rules.cii_reduction))
    load<any>('analysis').then((a) => setFirstYear(a.q3_ratings.first_official_year))
  }, [])
  const zOf = (y: number) => z.find((r) => r.year === y)?.z ?? null

  const sel = useMemo(() => (rows ?? []).filter((r) => r.cii && r.segment === segment), [rows, segment])
  const option = useMemo(() => {
    const byYear = RATED_YEARS.map((y) => sel.filter((r) => r.year === y))
    return {
      grid: { left: 48, right: 16, top: 16, bottom: 36 },
      tooltip: {
        ...tooltipStyle, trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: (ps: any[]) => `<b>${ps[0].axisValue}</b><br/>` + ps.map((p) => `${p.marker} ${p.seriesName}: ${num(p.value, 1)}%`).join('<br/>'),
      },
      xAxis: { ...axisStyle, type: 'category', data: RATED_YEARS.map(String) },
      yAxis: { ...axisStyle, type: 'value', max: 100, axisLabel: { ...axisStyle.axisLabel, formatter: '{value}%' } },
      series: LETTERS.map((l) => ({
        name: l, type: 'bar', stack: 'r', barWidth: '55%',
        itemStyle: { color: RATING_COLOR[l], borderColor: '#fff', borderWidth: 1 },
        data: byYear.map((ys) => (ys.length ? (ys.filter((r) => r.cii === l).length / ys.length) * 100 : 0)),
      })),
    }
  }, [sel])

  if (!rows) return <Loading />
  const latest = sel.filter((r) => r.year === 2025)
  const prev = sel.filter((r) => r.year === 2024)
  const worse = latest.filter((r) => r.worse).sort((a, b) => (b.cii ?? '').localeCompare(a.cii ?? ''))
  const prevRating = new Map(prev.map((r) => [r.ship, r.cii]))
  const de = shareDE(latest)
  const deP = shareDE(prev)
  const avgRatio = latest.length ? latest.reduce((s, r) => s + (r.cii_ratio ?? 0), 0) / latest.length : null

  const segWord = segment === 'Vehicle carrier' ? 'vehicle carriers' : 'ro-ro ships'
  const deFirst = firstYear !== null ? shareDE(sel.filter((r) => r.year === firstYear)) : null
  const rising = de !== null && deFirst !== null && de > deFirst
  const mix = (height: number) => (
    <Card title="Rating mix by year" info="Share of rated ship-years by rating letter. Ratings are computed from EU MRV data as an approximation of the official IMO figure.">
      <Legend items={LETTERS.map((l) => ({ label: `${l}${l === 'A' ? ' (best)' : l === 'E' ? ' (worst)' : ''}`, color: RATING_COLOR[l] }))} />
      <Chart option={option} height={height} ariaLabel={`CII rating mix by year for ${segment}`} />
    </Card>
  )

  return (
    <>
      <PageIntro
        compact={!detailed}
        title="Carbon ratings"
        lede="The IMO carbon intensity rating (CII) of each ship and year, from A (best) to E (worst). The limit behind it gets stricter every year."
        what="The IMO carbon intensity rating (CII) per ship and year: A is best, E is worst. It compares CO2 per unit of capacity and distance with a required level that tightens every year."
        how="Pick a segment. The chart shows how the mix of ratings moved; the list shows ships whose letter got worse in 2025. Click a ship to see its history."
        notice="A ship that does not improve slips toward D and E because the required level tightens every year. Under IMO rules, three years of D or one year of E needs a corrective plan."
      />
      {de !== null && (
        <Answer question="Are ships slipping toward poor carbon ratings?"
          sub={<>
            <b>{pct(de, 0)}</b> of rated {segWord} were D or E in 2025{deFirst !== null && <>, against {pct(deFirst, 0)} in {firstYear}, the first official year</>}.{' '}
            {num(worse.length)} got a worse letter in 2025 than in 2024. The limit tightens every year, so a ship that does not improve slips.
          </>}>
          {rising ? <>Yes. The share rated <em>D or E</em> is growing.</> : <>Not overall, but <em>{num(worse.length)} {segWord}</em> slipped in 2025.</>}
        </Answer>
      )}
      <div className="controls knobs-row">
        <Segmented label="Ships" value={segment} onChange={setSegment} options={SEGMENTS.map((s) => ({ value: s, label: s === 'Ro-ro ship' ? 'Ro-ro ships' : 'Vehicle carriers' }))}
          info="Each segment has its own IMO reference line and rating boundaries." />
      </div>
      {!detailed && <div className="simple-chart">{mix(380)}</div>}
      {detailed && (
        <>
          <div className="grid kpis">
            <Kpi label="Rated D or E in 2025" value={pct(de)} sub={deP !== null && de !== null ? `${pct(de - deP, 1, true).replace('%', ' points')} vs 2024` : ''}
              info="Share of rated ship-years in 2025 with a D or E rating." />
            <Kpi label="Ships with a worse rating" value={num(worse.length)} sub="in 2025 than in 2024"
              info="Ships whose rating letter in 2025 is worse than their letter in 2024." />
            <Kpi label="Attained / required" value={num(avgRatio, 3)} sub="average, 2025"
              info="Attained CII divided by required CII. Below 1 means better than required." />
            <Kpi label="Rated ship-years" value={num(sel.length)} sub="2019 to 2025"
              info="Ship-years with a gross tonnage (reported or estimated) and a reduction factor, so a rating can be computed." />
          </div>
          <div className="grid wide-left">
            {mix(360)}
            <Card title="Drifting ships: worse in 2025 than 2024" info="Ships whose letter worsened. Click a row to open the ship profile.">
              <div className="scroll">
                <table className="data">
                  <thead><tr><th>Ship</th><th>Size</th><th>2024</th><th>2025</th></tr></thead>
                  <tbody>
                    {worse.map((r) => (
                      <tr key={r.ship} className="click" onClick={() => nav(`/ship/${encodeURIComponent(r.ship)}`)}>
                        <td>{r.ship}</td>
                        <td>{r.size.split(' (')[0]}</td>
                        <td><Badge l={prevRating.get(r.ship) ?? null} /></td>
                        <td><Badge l={r.cii} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
          <Card title="What the rating means">
            <p>
              Attained CII is grams of CO2 per gross tonne of capacity per nautical mile. The required CII is the IMO reference line for the ship's type and size,
              reduced each year against 2019 ({pct(zOf(2023), 0)} in 2023, {pct(zOf(2025), 0)} in 2025, {pct(zOf(2026), 0)} in 2026, {pct(zOf(2030), 1)} by 2030). Boundaries around the required value split ships into A to E. Here the
              rating is computed from EU MRV data, which covers voyages linked to EU/EEA ports, so it approximates the official figure that uses all voyages.
              Gross tonnage comes from Kystverket records or is estimated from AIS length and beam.
            </p>
          </Card>
        </>
      )}
    </>
  )
}

export function Badge({ l }: { l: string | null }) {
  if (!l) return <span className="note">n/a</span>
  const dark = l === 'A' || l === 'E'
  return <span className="badge" style={{ background: RATING_COLOR[l], color: dark ? '#fff' : '#0b0b0b' }}>{l}</span>
}
