import { useCallback, useEffect, useMemo, useState } from 'react'
import Chart, { axisStyle, tooltipStyle } from '../components/Chart'
import { Answer, Card, Knob, Kpi, Legend, Loading, PageIntro, Segmented, nav } from '../components/ui'
import { efficiency, load, loadFleet, SEGMENTS, sum, type ShipYear, YEARS } from '../lib/data'
import { big, num } from '../lib/format'
import { INK, SEGMENT_COLOR } from '../lib/theme'
import { useDetailed } from '../lib/view'

export default function Fleet() {
  const [rows, setRows] = useState<ShipYear[] | null>(null)
  const [b, setB] = useState<number | null>(null)
  const [q1, setQ1] = useState<any>(null)
  const detailed = useDetailed()
  const [year, setYear] = useState(2025)
  const [segment, setSegment] = useState('All')
  useEffect(() => {
    loadFleet().then(setRows)
    load<any>('analysis').then((a) => {
      setB(a.q1_drivers.cross_sectional.log_speed.estimate)
      setQ1(a.q1_drivers)
    })
  }, [])

  const sel = useMemo(
    () => (rows ?? []).filter((r) => r.year === year && (segment === 'All' || r.segment === segment)),
    [rows, year, segment],
  )
  const prev = useMemo(
    () => (rows ?? []).filter((r) => r.year === year - 1 && (segment === 'All' || r.segment === segment)),
    [rows, year, segment],
  )
  const onClick = useCallback((p: any) => {
    if (p?.data?.ship) nav(`/ship/${encodeURIComponent(p.data.ship)}`)
  }, [])

  const option = useMemo(() => {
    const pts = sel.filter((r) => r.ok && r.speed && r.co2nm)
    const series: any[] = SEGMENTS.filter((s) => segment === 'All' || s === segment).map((s) => ({
      name: s,
      type: 'scatter',
      symbolSize: 8,
      itemStyle: { color: SEGMENT_COLOR[s], opacity: 0.75, borderColor: '#fff', borderWidth: 1 },
      emphasis: { scale: 1.6 },
      data: pts.filter((r) => r.segment === s).map((r) => ({ value: [r.speed, r.co2nm], ship: r.ship, size: r.size, co2: r.co2 })),
    }))
    if (b !== null && pts.length > 5) {
      const speeds = pts.map((r) => r.speed!).sort((x, y) => x - y)
      const co2s = pts.map((r) => r.co2nm!).sort((x, y) => x - y)
      const x0 = speeds[Math.floor(speeds.length / 2)]
      const y0 = co2s[Math.floor(co2s.length / 2)]
      const lo = speeds[Math.floor(speeds.length * 0.03)]
      const hi = speeds[Math.floor(speeds.length * 0.97)]
      const line = (exp: number) => Array.from({ length: 30 }, (_, i) => {
        const x = lo + ((hi - lo) * i) / 29
        return [x, y0 * Math.pow(x / x0, exp)]
      })
      series.push({ name: 'Fitted across ships', type: 'line', showSymbol: false, data: line(b), lineStyle: { color: INK.primary, width: 2 }, silent: true, z: 5 })
      series.push({ name: 'Engineering rule (speed squared)', type: 'line', showSymbol: false, data: line(2), lineStyle: { color: INK.secondary, width: 2, type: 'dashed' }, silent: true, z: 5 })
    }
    return {
      grid: { left: 56, right: 16, top: 16, bottom: 44 },
      tooltip: {
        ...tooltipStyle,
        trigger: 'item',
        formatter: (p: any) =>
          p.data?.ship
            ? `<b>${p.data.ship}</b><br/>${p.seriesName}, ${p.data.size}<br/>Speed ${num(p.value[0], 1)} kn<br/>CO2 per nm ${num(p.value[1], 1)} kg<br/>CO2 ${big(p.data.co2)} t<br/><i>Click to open the ship</i>`
            : '',
      },
      xAxis: { ...axisStyle, type: 'value', name: 'Average speed (knots)', nameLocation: 'middle', nameGap: 28, scale: true },
      yAxis: { ...axisStyle, type: 'value', name: 'CO2 per nautical mile (kg)', nameLocation: 'middle', nameGap: 44, scale: true },
      series,
    }
  }, [sel, segment, b])

  if (!rows) return <Loading />
  const e = efficiency(sel)
  const ep = efficiency(prev)
  const delta = (cur: number | null, p: number | null) =>
    cur !== null && p !== null && p !== 0 ? (
      <span className={cur > p ? 'up' : 'down'}>
        {cur > p ? '+' : ''}
        {num(((cur - p) / p) * 100, 1)}% vs {year - 1}
      </span>
    ) : (
      'no previous year'
    )
  const ships = new Set(sel.map((r) => r.ship)).size
  const ranked = sel.filter((r) => r.ok && r.co2nm).sort((x, y) => (y.co2nm ?? 0) - (x.co2nm ?? 0))

  const segWord = segment === 'All' ? 'ships' : segment === 'Vehicle carrier' ? 'vehicle carriers' : 'ro-ro ships'
  const legend = (
    <Legend items={[
      ...SEGMENTS.filter((s) => segment === 'All' || s === segment).map((s) => ({ label: s, color: SEGMENT_COLOR[s] })),
      { label: 'Fitted across ships', color: INK.primary },
      { label: 'Engineering rule', color: INK.secondary, dashed: true },
    ]} />
  )
  const scatter = (height: number) => (
    <Card title="Speed against CO2 per nautical mile"
      info="One dot per ship. The solid line is the relation fitted across ships; the dashed line is the engineering rule that fuel per mile rises with speed squared. Click a dot to open that ship.">
      {legend}
      <Chart option={option} height={height} onClick={onClick} ariaLabel={`Scatter of speed against CO2 per nautical mile for ${year}`} />
    </Card>
  )

  return (
    <>
      <PageIntro
        compact={!detailed}
        title="Fleet efficiency"
        lede="How much CO2 each ship emits per nautical mile, against its average speed, from the yearly EU emission reports."
        what="How much CO2 each ship emits per nautical mile against its average speed, from the EU MRV reports."
        how="Pick a year and a segment. Hover a dot for the ship's numbers; click it to open that ship's profile."
        notice="Bigger ships sit higher. Ships far above the cloud at their speed burn more than peers and are worth a closer look."
      />
      {q1 && (
        <Answer question="What makes some ships burn more per mile?"
          sub={<>
            Doubling a ship's size goes with <b>{num(q1.size_effect_doubling_gt_pct, 0)}% more CO2 per mile</b>, and ships of the newer design generation emit{' '}
            <b>{num(Math.abs(q1.eedi_generation_effect_pct), 0)}% less</b> than older ships of the same size and speed. In {year} the {num(ships)} {segWord} emitted{' '}
            {num(e.co2nm, 0)} kg of CO2 per mile on average.
          </>}>
          Mostly <em>size</em>, then <em>design age</em>.
        </Answer>
      )}
      <div className="controls knobs-row">
        <Knob label="Year" value={year} min={YEARS[0]} max={YEARS[YEARS.length - 1]} step={1} onChange={setYear} format={String}
          info="EU MRV reporting year. Each ship reports one year of voyages to, from and between EU/EEA ports."
          ticks={YEARS.map((y, i) => ({ value: y, label: i === 0 || i === YEARS.length - 1 ? String(y) : `'${String(y).slice(2)}` }))} />
        <Segmented label="Ships" value={segment} onChange={setSegment}
          options={[{ value: 'All', label: 'All' }, { value: 'Vehicle carrier', label: 'Vehicle carriers' }, { value: 'Ro-ro ship', label: 'Ro-ro' }]}
          info="Vehicle carriers move new cars and rolling cargo; ro-ro ships move trailers and rolling equipment." />
      </div>
      {!detailed && <div className="simple-chart">{scatter(440)}</div>}
      {detailed && (
        <>
          <div className="grid kpis">
            <Kpi label="CO2 emitted" value={`${big(sum(sel, 'co2'))} t`} sub={delta(sum(sel, 'co2'), sum(prev, 'co2'))}
              info="Total CO2 in the EU MRV scope, in tonnes, for the selected year and segment." />
            <Kpi label="Fuel burned" value={`${big(sum(sel, 'fuel'))} t`} sub={delta(sum(sel, 'fuel'), sum(prev, 'fuel'))}
              info="Total fuel in tonnes reported in the EU MRV scope." />
            <Kpi label="CO2 per nautical mile" value={`${num(e.co2nm, 1)} kg`} sub={delta(e.co2nm, ep.co2nm)}
              info="Total CO2 divided by total distance, over ship-years that pass the plausibility checks. Lower is better." />
            <Kpi label="Distance sailed" value={`${big(sel.reduce((a, r) => a + (r.dist ?? 0), 0))} nm`}
              sub={`${num(ships)} ships, average ${num(e.speed, 1)} knots`}
              info="Total nautical miles in the EU MRV scope for the selection, and the number of ships reporting. Speed is distance divided by time at sea." />
          </div>
          <div className="grid wide-left">
            {scatter(420)}
            <Card title="Highest CO2 per nautical mile" info="Quality-checked ship-years in the selection, highest first. Click a row to open the ship.">
              <div className="scroll">
                <table className="data">
                  <thead><tr><th>Ship</th><th>Size</th><th className="n">kg/nm</th><th className="n">kn</th></tr></thead>
                  <tbody>
                    {ranked.slice(0, 40).map((r) => (
                      <tr key={r.ship} className="click" onClick={() => nav(`/ship/${encodeURIComponent(r.ship)}`)}>
                        <td>{r.ship}</td>
                        <td>{r.size.split(' (')[0]}</td>
                        <td className="n">{num(r.co2nm, 1)}</td>
                        <td className="n">{num(r.speed, 1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </>
      )}
    </>
  )
}
