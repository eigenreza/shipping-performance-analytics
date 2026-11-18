import { useEffect, useMemo, useState } from 'react'
import Chart, { axisStyle, tooltipStyle } from '../components/Chart'
import { Answer, Card, Kpi, Legend, Loading, PageIntro, Select, nav } from '../components/ui'
import { efficiency, load, loadFleet, type ShipYear } from '../lib/data'
import { big, eur, num, pct } from '../lib/format'
import { INK, SEGMENT_COLOR } from '../lib/theme'
import { useDetailed } from '../lib/view'
import { Badge } from './Ratings'

type Deviation = { ship: string; year: number; excess_vs_expected_pct: number; z: number; direction: string; co2_kg_per_nm: number; speed_kn: number }

export default function Ship({ param }: { param?: string }) {
  const [rows, setRows] = useState<ShipYear[] | null>(null)
  const [devs, setDevs] = useState<Deviation[]>([])
  const detailed = useDetailed()
  useEffect(() => {
    loadFleet().then(setRows)
    load<any>('analysis').then((a) => setDevs(a.q5_deviations.items))
  }, [])

  const ships = useMemo(() => [...new Set((rows ?? []).map((r) => r.ship))].sort(), [rows])
  const flagged = useMemo(() => {
    const years = new Map<string, number>()
    for (const r of rows ?? []) if (r.ok) years.set(r.ship, (years.get(r.ship) ?? 0) + 1)
    const up = devs.filter((d) => d.z > 0).sort((a, b) => b.year - a.year || (years.get(b.ship) ?? 0) - (years.get(a.ship) ?? 0) || b.z - a.z)
    return [...new Set(up.map((d) => d.ship))]
  }, [devs, rows])
  const ship = param ? decodeURIComponent(param) : flagged[0] ?? ships[0]
  const mine = useMemo(() => (rows ?? []).filter((r) => r.ship === ship).sort((a, b) => a.year - b.year), [rows, ship])
  const last = mine[mine.length - 1]

  const peers = useMemo(() => {
    if (!rows || !last) return [] as { year: number; peer: number | null }[]
    return mine.map((m) => ({
      year: m.year,
      peer: efficiency(rows.filter((r) => r.year === m.year && r.segment === last.segment && r.size === last.size)).co2nm,
    }))
  }, [rows, mine, last])

  const option = useMemo(() => ({
    grid: { left: 52, right: 16, top: 16, bottom: 32 },
    tooltip: { ...tooltipStyle, trigger: 'axis', valueFormatter: (v: number) => (v === null ? 'n/a' : `${num(v, 1)} kg/nm`) },
    xAxis: { ...axisStyle, type: 'category', data: mine.map((m) => String(m.year)) },
    yAxis: { ...axisStyle, type: 'value', scale: true, name: 'CO2 per nautical mile (kg)', nameLocation: 'middle', nameGap: 40 },
    series: [
      { name: ship, type: 'line', data: mine.map((m) => (m.ok ? m.co2nm : null)), symbolSize: 8, lineStyle: { width: 2, color: SEGMENT_COLOR[last?.segment ?? 'Vehicle carrier'] }, itemStyle: { color: SEGMENT_COLOR[last?.segment ?? 'Vehicle carrier'] }, connectNulls: true },
      { name: 'Peers: same segment and size class', type: 'line', data: peers.map((p) => p.peer), symbol: 'none', lineStyle: { width: 2, type: 'dashed', color: INK.secondary } },
    ],
  }), [mine, peers, ship, last])

  if (!rows) return <Loading />
  if (!last) return <p>Ship not found. <a href="#/ship">Open the first flagged ship</a>.</p>
  const e = efficiency(mine.filter((m) => m.year === last.year))
  const peerLast = peers[peers.length - 1]?.peer ?? null
  const variance = e.co2nm !== null && peerLast ? e.co2nm / peerLast - 1 : null
  const myDevs = devs.filter((d) => d.ship === ship)

  const flaggedYears = myDevs.filter((d) => d.z > 0).map((d) => d.year)
  const picker = (
    <div className="controls">
      <Select label="Ship" value={ship} onChange={(v) => nav(`/ship/${encodeURIComponent(v)}`)}
        options={[...flagged, ...ships.filter((s) => !flagged.includes(s))].map((s) => ({ value: s, label: flagged.includes(s) ? `${s} (flagged)` : s }))}
        info="Ships are shown under stable pseudonyms. Flagged ships emit far more per mile than speed, size and age predict in at least one year." />
      <p className="note" style={{ margin: 0 }}>
        {last.segment}, {last.size}, {last.gen.toLowerCase()}, flag region {last.flag}
        {last.gt ? `, about ${num(last.gt)} gross tonnage` : ''}.
      </p>
    </div>
  )
  const trend = (height: number) => (
    <Card title="CO2 per nautical mile over time" info="Quality-checked years only. The dashed line is the average of ships in the same segment and size class.">
      <Legend items={[{ label: ship, color: SEGMENT_COLOR[last.segment] }, { label: 'Peers', color: INK.secondary, dashed: true }]} />
      <Chart option={option} height={height} ariaLabel={`CO2 per nautical mile of ${ship} by year against peers`} />
    </Card>
  )

  return (
    <>
      <PageIntro
        compact={!detailed}
        title="Ship drill-down"
        lede="One ship over the years, under its pseudonym, against ships of the same segment and size."
        what="One ship over the years, under its pseudonym: efficiency, carbon rating, EU carbon cost and how it compares with ships of the same segment and size."
        how="Pick a ship, or arrive here by clicking a ship on another page. Ships flagged as deviating are listed first."
        notice="A positive variance means the ship burns more per mile than its peers. A flag means the gap is larger than speed, size and age explain; it is a reason to look closer, not a verdict."
      />
      {picker}
      {variance !== null && (
        <Answer question={`How does ${ship} compare with similar ships?`}
          sub={<>
            In {last.year} it emitted {num(e.co2nm, 0)} kg of CO2 per mile against {num(peerLast, 0)} kg for ships of its segment and size
            {last.cii ? <>, and was rated <b>{last.cii}</b></> : null}.{' '}
            {flaggedYears.length
              ? <>In {flaggedYears.join(', ')} its CO2 per mile was far above what its speed, size and age predict: a reason to look closer, not a verdict.</>
              : 'No year is flagged as unusual.'}
          </>}>
          It burns <em>{pct(Math.abs(variance), 0)} {variance > 0 ? 'more' : 'less'}</em> CO2 per mile than its peers.
        </Answer>
      )}
      {!detailed && <div className="simple-chart">{trend(340)}</div>}
      {detailed && (
        <>
          <div className="grid kpis">
            <Kpi label={`CO2 per nautical mile, ${last.year}`} value={`${num(e.co2nm, 1)} kg`} sub={`peers ${num(peerLast, 1)} kg`}
              info="This ship's CO2 per nautical mile in its latest year, and the same figure for all ships of its segment and size class." />
            <Kpi label="Variance against peers" value={pct(variance, 1, true)} sub={variance !== null && variance > 0 ? 'more than peers' : 'less than peers'}
              info="How much more (positive) or less (negative) CO2 per mile the ship emits than its peers." />
            <Kpi label={`CII rating, ${last.year}`} value={last.cii ?? 'n/a'} sub={last.cii_ratio ? `attained / required ${num(last.cii_ratio, 2)}` : 'no gross tonnage'}
              info="IMO carbon intensity rating, A best to E worst, computed from EU MRV data." />
            <Kpi label={`EU ETS cost, ${last.year}`} value={eur(last.ets_cost)} sub={`${big(last.eua)} allowances`}
              info="Allowances due (CO2 in EU ETS scope times the phase-in share) times the year's average allowance price. Zero before 2024." />
          </div>
          <div className="grid wide-left">
            {trend(300)}
            <Card title="Flagged deviations" info="Years where the ship's CO2 per mile is far from what speed, size, age and segment predict (robust z-score beyond 2.5).">
              {myDevs.length === 0 && <p>No year of this ship is flagged.</p>}
              {myDevs.map((d) => (
                <p key={d.year}>
                  <b>{d.year}:</b> {pct(d.excess_vs_expected_pct / 100, 0, true)} CO2 per mile against the model's expectation ({d.direction}). At {num(d.speed_kn, 1)} knots the ship
                  emitted {num(d.co2_kg_per_nm, 1)} kg per mile. Possible reasons to check: long waiting with engines running, hull fouling, a different trade or cargo mix, or a
                  reporting issue.
                </p>
              ))}
            </Card>
          </div>
          <Card title="Year by year">
            <div className="scroll">
              <table className="data">
                <thead>
                  <tr><th>Year</th><th className="n">CO2 (t)</th><th className="n">Distance (nm)</th><th className="n">Speed (kn)</th><th className="n">CO2 per nm (kg)</th><th>CII</th><th className="n">EU ETS cost</th><th>Checks</th></tr>
                </thead>
                <tbody>
                  {mine.map((m) => (
                    <tr key={m.year}>
                      <td>{m.year}</td>
                      <td className="n">{num(m.co2)}</td>
                      <td className="n">{num(m.dist)}</td>
                      <td className="n">{num(m.speed, 1)}</td>
                      <td className="n">{num(m.co2nm, 1)}</td>
                      <td><Badge l={m.cii} /></td>
                      <td className="n">{eur(m.ets_cost)}</td>
                      <td>{m.ok ? <span className="pill ok">passes</span> : <span className="pill warn">excluded</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </>
  )
}
