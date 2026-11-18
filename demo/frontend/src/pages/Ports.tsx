import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import 'maplibre-gl/dist/maplibre-gl.css'
import Chart, { axisStyle, tooltipStyle } from '../components/Chart'
import { Answer, Card, Kpi, Loading, PageIntro, Select } from '../components/ui'
import { load } from '../lib/data'
import { num, pct } from '../lib/format'
import { INK, SEGMENT_COLOR } from '../lib/theme'
import { useDetailed } from '../lib/view'

type Call = { port: string; lat: number; lon: number; county: string; segment: string; wait: number; berth: number; total: number; edge: boolean; confirmed: boolean }
type Band = { band: string; positions: number; legs: number; speed_change: number; low: number; high: number }
type PortsData = { calls: Call[]; legs: { speed: number; wind: number; wave: number; nm: number; segment: string }[]; speed_by_wind: Band[]; speed_by_waves: Band[]; summary: any }

maplibregl.setWorkerUrl(workerUrl)

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b)
  return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : NaN
}

export default function Ports() {
  const [d, setD] = useState<PortsData | null>(null)
  const [port, setPort] = useState<string | null>(null)
  const [weather, setWeather] = useState<'wind' | 'waves'>('wind')
  const detailed = useDetailed()
  const mapEl = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)

  useEffect(() => {
    load<PortsData>('ports').then(setD)
  }, [])

  const ports = useMemo(() => {
    if (!d) return []
    const by = new Map<string, Call[]>()
    d.calls.forEach((c) => by.set(c.port, [...(by.get(c.port) ?? []), c]))
    return [...by.entries()]
      .map(([name, cs]) => ({
        name, lat: cs[0].lat, lon: cs[0].lon, county: cs[0].county, calls: cs.length,
        wait: median(cs.map((c) => c.wait)), berth: median(cs.map((c) => c.berth)), waitShare: cs.filter((c) => c.wait > 0).length / cs.length,
        totals: cs.map((c) => c.total),
      }))
      .sort((a, b) => b.calls - a.calls)
  }, [d])

  useEffect(() => {
    if (!d || !mapEl.current || mapRef.current) return
    let cancelled = false
    load<any>('coast').then((coast) => {
      if (cancelled || !mapEl.current) return
      const map = new maplibregl.Map({
        container: mapEl.current,
        style: {
          version: 8,
          sources: { land: { type: 'geojson', data: coast } },
          layers: [
            { id: 'sea', type: 'background', paint: { 'background-color': '#dfeaf4' } },
            { id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': '#f4f2ec', 'fill-outline-color': '#c9c8c3' } },
          ],
        },
        center: [9.5, 63.5],
        zoom: 3.6,
        attributionControl: { customAttribution: 'Land: Natural Earth. Ports and calls: Kystverket (NLOD).' },
      })
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
      mapRef.current = map
      map.on('load', () => {
        const maxCalls = Math.max(...ports.map((p) => p.calls))
        map.addSource('ports', {
          type: 'geojson',
          data: {
            type: 'FeatureCollection',
            features: ports.map((p) => ({
              type: 'Feature', geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
              properties: { name: p.name, calls: p.calls, berth: p.berth, waitShare: p.waitShare, r: 5 + 18 * Math.sqrt(p.calls / maxCalls) },
            })),
          },
        })
        map.addLayer({
          id: 'ports', type: 'circle', source: 'ports',
          paint: {
            'circle-radius': ['get', 'r'],
            'circle-color': ['interpolate', ['linear'], ['get', 'berth'], 2, '#b7d3f6', 6, '#5598e7', 12, '#1c5cab', 24, '#0d366b'],
            'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5, 'circle-opacity': 0.9,
          },
        })
        const lons = ports.map((p) => p.lon)
        const lats = ports.map((p) => p.lat)
        map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 30, duration: 0 })
        const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false })
        map.on('mousemove', 'ports', (e: any) => {
          const f = e.features?.[0]
          if (!f) return
          map.getCanvas().style.cursor = 'pointer'
          const p = f.properties as any
          popup.setLngLat(e.lngLat).setHTML(`<b>${p.name}</b><br/>${p.calls} calls<br/>median ${num(p.berth, 1)} h at berth<br/>${pct(p.waitShare)} waited at anchor`).addTo(map)
        })
        map.on('mouseleave', 'ports', () => {
          map.getCanvas().style.cursor = ''
          popup.remove()
        })
        map.on('click', 'ports', (e: any) => {
          const name = (e.features?.[0]?.properties as any)?.name
          if (name) setPort(name)
        })
      })
    })
    return () => {
      cancelled = true
    }
  }, [d, ports])

  useEffect(() => () => mapRef.current?.remove(), [])

  const selected = ports.find((p) => p.name === port) ?? ports[0]
  const dist = useMemo(() => {
    if (!selected) return {}
    const bins = [0, 2, 4, 6, 8, 12, 16, 24, 36, 48, 1e9]
    const labels = ['0-2', '2-4', '4-6', '6-8', '8-12', '12-16', '16-24', '24-36', '36-48', '48+']
    const counts = labels.map((_, i) => selected.totals.filter((t) => t >= bins[i] && t < bins[i + 1]).length)
    return {
      grid: { left: 40, right: 12, top: 12, bottom: 40 },
      tooltip: { ...tooltipStyle, trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => `${v} calls` },
      xAxis: { ...axisStyle, type: 'category', data: labels, name: 'Hours in port (arrival to departure)', nameLocation: 'middle', nameGap: 26 },
      yAxis: { ...axisStyle, type: 'value', minInterval: 1 },
      series: [{ type: 'bar', data: counts, itemStyle: { color: '#2a78d6', borderRadius: [4, 4, 0, 0] }, barWidth: '60%' }],
    }
  }, [selected])

  const weatherChart = useMemo(() => {
    if (!d) return {}
    const bands = weather === 'wind' ? d.speed_by_wind : d.speed_by_waves
    return {
      grid: { left: 56, right: 16, top: 16, bottom: 44 },
      tooltip: {
        ...tooltipStyle, trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: (ps: any[]) => {
          const b = bands[ps[0].dataIndex]
          return `<b>${b.band}</b><br/>Speed vs calm: ${pct(b.speed_change, 1, true)}<br/>95% interval ${pct(b.low, 1, true)} to ${pct(b.high, 1, true)}<br/>${num(b.legs)} legs, ${num(b.positions)} positions`
        },
      },
      xAxis: { ...axisStyle, type: 'category', data: bands.map((b) => b.band), name: weather === 'wind' ? 'Wind speed' : 'Significant wave height', nameLocation: 'middle', nameGap: 28 },
      yAxis: { ...axisStyle, type: 'value', name: 'Speed vs calm conditions', nameLocation: 'middle', nameGap: 42, axisLabel: { ...axisStyle.axisLabel, formatter: (v: number) => `${num(v * 100, 0)}%` } },
      series: [
        { type: 'bar', data: bands.map((b) => b.speed_change), barWidth: '45%', itemStyle: { color: (p: any) => (p.value < 0 ? '#eb6834' : '#2a78d6'), borderRadius: 4 } },
        { type: 'custom', renderItem: (_p: any, api: any) => {
            const x = api.coord([api.value(0), api.value(1)])[0]
            const lo = api.coord([api.value(0), api.value(1)])[1]
            const hi = api.coord([api.value(0), api.value(2)])[1]
            return { type: 'group', children: [
              { type: 'line', shape: { x1: x, y1: lo, x2: x, y2: hi }, style: { stroke: INK.primary, lineWidth: 1.5 } },
              { type: 'line', shape: { x1: x - 5, y1: lo, x2: x + 5, y2: lo }, style: { stroke: INK.primary, lineWidth: 1.5 } },
              { type: 'line', shape: { x1: x - 5, y1: hi, x2: x + 5, y2: hi }, style: { stroke: INK.primary, lineWidth: 1.5 } },
            ] }
          }, data: bands.map((b, i) => [i, b.low, b.high]), z: 10, silent: true },
      ],
    }
  }, [d, weather])

  if (!d) return <Loading />
  const s = d.summary
  const legsWithWind = d.legs.filter((l) => l.wind !== null)
  const bands = [...d.speed_by_wind, ...d.speed_by_waves].map((b) => b.speed_change)
  const spread = Math.max(...bands) - Math.min(...bands)
  return (
    <>
      <PageIntro
        compact={!detailed}
        lede="Port calls by fleet ships on the Norwegian coast in August and September 2026, found from ship positions, with wind and waves along each voyage leg."
        title="Ports and weather"
        what="Port calls by fleet ships on the Norwegian coast in August and September 2026, found from AIS ship positions, with wind and waves along each voyage leg."
        how="Circles are ports: size shows the number of calls, darker blue means longer time at the quay. Click a port to see how long its calls lasted. Switch between wind and waves below."
        notice="Waiting at anchor is rare in this liner-style trade; time is spent alongside instead. Weather changes speed by only a few percent here, and the intervals overlap, so it does not explain slow legs on its own."
      />
      <Answer question="Where does the time in Norwegian ports go?"
        sub={<>
          Of {num(s.calls)} calls by {num(s.ships)} ships, only <b>{pct(s.share_with_waiting)}</b> waited at anchor first. The median call spent{' '}
          <b>{num(s.median_berth_h, 1)} hours</b> at the quay. Wind and waves changed speed by at most {pct(spread, 0)}, within the margin of error.
        </>}>
        {s.share_with_waiting < 0.1 ? <>Alongside the <em>quay</em>, not waiting at anchor.</> : <>A good part goes to <em>waiting at anchor</em>.</>}
      </Answer>
      {detailed && <div className="grid kpis">
        <Kpi label="Port calls" value={num(s.calls)} sub={`${num(s.ships)} ships, ${num(s.ports_with_calls)} ports`}
          info="Calls found from AIS: the ship stopped within 1 km of a quay or terminal for at least 30 minutes. Calls cut by the start or end of the period are left out." />
        <Kpi label="Calls with waiting" value={pct(s.share_with_waiting)} sub={`95% interval ${pct(s.share_with_waiting_interval[0])} to ${pct(s.share_with_waiting_interval[1])}`}
          info="Share of calls where the ship anchored near the same port within 24 hours before berthing." />
        <Kpi label="Median time at berth" value={`${num(s.median_berth_h, 1)} h`} sub="per call"
          info="Median hours alongside the quay, from the first berth stop to departure." />
        <Kpi label="Confirmed by Kystverket" value={pct(s.kystverket_confirmed_share)} sub="cross-check of AIS-derived calls"
          info="Share of AIS-derived calls that Kystverket's own port call records also show, at the same port within 12 hours." />
      </div>}
      <div className="grid wide-left">
        <Card title="Ports by number of calls" info="Circle size: number of calls. Color: median hours at berth (light = short, dark = long).">
          <div ref={mapEl} className="map" role="img" aria-label="Map of Norwegian ports sized by number of calls" />
        </Card>
        <Card title={`Time in port: ${selected?.name ?? ''}`} info="Distribution of hours from arrival in the port area to departure, for the selected port.">
          <Select label="Port" value={selected?.name ?? ''} onChange={(v) => setPort(v)}
            options={ports.map((p) => ({ value: p.name, label: `${p.name} (${p.calls} calls)` }))}
            info="Pick a port here or click one on the map." />
          <Chart option={dist} height={250} ariaLabel={`Distribution of hours in port at ${selected?.name}`} />
          <p className="note">
            {selected && `${num(selected.calls)} calls, median ${num(selected.berth, 1)} hours at berth, ${pct(selected.waitShare)} waited at anchor.`}
          </p>
        </Card>
      </div>
      {detailed && <Card title="Speed lost in wind and waves" info="Under-way positions at 8 knots or more, compared with the same ship's median speed in calm conditions (wind under 5 m/s, waves under 1 m). Bars show the mean change, whiskers the 95% interval from resampling voyage legs.">
        <div className="seg" role="group" aria-label="Weather measure">
          <button type="button" aria-pressed={weather === 'wind'} onClick={() => setWeather('wind')}>Wind</button>
          <button type="button" aria-pressed={weather === 'waves'} onClick={() => setWeather('waves')}>Waves</button>
        </div>
        <Chart option={weatherChart} height={300} ariaLabel={`Speed change by ${weather} band`} />
        <p className="note">
          Based on {num(s.transit_positions)} positions of {num(s.ships_with_calm_reference)} ships on {num(legsWithWind.length)} voyage legs.
          Weather: hourly ERA5 wind and marine wave data from <a href="https://open-meteo.com" target="_blank" rel="noreferrer">Open-Meteo.com</a>.
        </p>
      </Card>}
      {detailed && <p className="note">Segment colors elsewhere: <span style={{ color: SEGMENT_COLOR['Vehicle carrier'] }}>vehicle carriers</span>, <span style={{ color: SEGMENT_COLOR['Ro-ro ship'] }}>ro-ro ships</span>.</p>}
    </>
  )
}
