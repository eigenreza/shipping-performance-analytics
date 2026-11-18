import { useEffect, useMemo, useState } from 'react'
import { Card, Kpi, Loading, PageIntro } from '../components/ui'
import { load } from '../lib/data'
import { num } from '../lib/format'

type PBI = {
  measures: { name: string; folder: string; dax: string; description: string; format: string }[]
  tables: { name: string; description: string; kind: string }[]
  relationships: { from: string; to: string; active: boolean }[]
  calculation_group: { item: string; dax: string }[]
  field_parameter: string[]
  what_if: { name: string; min: number; max: number; step: number; default: number; description: string }[]
  roles: { name: string; segment: string; description: string }[]
  bpa_exceptions: Record<string, string>
  bpa: { rules_checked: number; findings: number } | null
  reconciliation: { summary: Record<string, number> } | null
  screenshots: string[]
}

const FACTS = ['Ship Year Emissions', 'Port Calls', 'Voyage Legs', 'Carbon Price']

function StarSchema({ rels }: { rels: PBI['relationships'] }) {
  // Facts in the middle row, dimensions above and below, lines for each relationship.
  const W = 900
  const pos: Record<string, [number, number]> = {}
  FACTS.forEach((f, i) => (pos[f] = [110 + i * 226, 150]))
  pos['Date'] = [225, 40]
  pos['Ship'] = [675, 40]
  pos['Segment'] = [225, 262]
  pos['Port'] = [675, 262]
  const table = (t: string) => t.split('[')[0]
  return (
    <svg viewBox={`0 0 ${W} 300`} width="100%" role="img" aria-label="Star schema: four fact tables linked to four shared dimensions">
      {rels.map((r, i) => {
        const a = pos[table(r.from)]
        const b = pos[table(r.to)]
        if (!a || !b) return null
        return <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={r.active ? '#86b6ef' : '#c9c8c3'} strokeWidth={1.5} strokeDasharray={r.active ? undefined : '5 4'} />
      })}
      {Object.entries(pos).map(([name, [x, y]]) => {
        const fact = FACTS.includes(name)
        return (
          <g key={name}>
            <rect x={x - 92} y={y - 18} width={184} height={36} rx={6} fill={fact ? '#1F4E79' : '#ffffff'} stroke="#1F4E79" />
            <text x={x} y={y + 5} textAnchor="middle" fontSize="13" fill={fact ? '#ffffff' : '#1F4E79'} fontWeight={600}>{name}</text>
          </g>
        )
      })}
    </svg>
  )
}

export default function PowerBI() {
  const [d, setD] = useState<PBI | null>(null)
  const [q, setQ] = useState('')
  useEffect(() => {
    load<PBI>('powerbi').then(setD)
  }, [])
  const measures = useMemo(
    () => (d?.measures ?? []).filter((m) => (m.name + m.folder + m.description).toLowerCase().includes(q.toLowerCase())),
    [d, q],
  )
  if (!d) return <Loading />
  const rec = d.reconciliation?.summary
  const folders = [...new Set(measures.map((m) => m.folder))]

  return (
    <>
      <PageIntro
        title="Inside the Power BI solution"
        what="The Power BI project behind this site: a semantic model (the tables, relationships and measures a report is built on) written in TMDL, a report in the enhanced report format, and a printable paginated report."
        how="Search the measure catalogue to see each measure's DAX (the formula language of Power BI) and its plain meaning. Scroll down for the model's design, quality checks and the report pages."
        notice="Every key measure is checked against the same number computed in SQL, and the model passes Microsoft's Best Practice Analyzer rules."
      />
      <div className="grid kpis">
        <Kpi label="Documented measures" value={num(d.measures.length)} sub={`${folders.length || ''} display folders`} info="Every measure has a description, a format string and a display folder." />
        <Kpi label="Measures checked against SQL" value={rec ? `${rec.reconciliation_matches} / ${rec.reconciliation_checks}` : 'n/a'} sub={rec ? `all ${rec.measures_without_error} measures evaluate without error` : ''}
          info="Key measures by year and segment were evaluated in the Power BI engine and compared with the same numbers computed in SQL (relative tolerance one in a million)." />
        <Kpi label="Best Practice Analyzer" value={d.bpa ? `${d.bpa.findings} findings` : 'n/a'} sub={d.bpa ? `${d.bpa.rules_checked} rules checked` : ''}
          info="Microsoft's Best Practice Analyzer rules, run with Tabular Editor 2 from the command line. Deliberate exceptions are annotated in the model with a reason." />
        <Kpi label="Row-level security roles" value={rec ? `${rec.rls_roles_passed} / ${rec.rls_roles}` : 'n/a'} sub="tested in the engine" info="Each role was queried as a member; it sees only its segment's ships, ship-years and port calls." />
      </div>
      <div className="grid two">
        <Card title="Star schema" info="Fact tables (dark) hold events and yearly reports; shared dimensions (white) describe them. Dashed: an inactive relationship used by one measure.">
          <StarSchema rels={d.relationships} />
          <p className="note">Ship is a slowly changing dimension: a new version starts when a ship's flag, segment, ice class or efficiency index type changes, and facts point to the version valid in their year.</p>
        </Card>
        <Card title="Model features">
          <details open>
            <summary>Calculation group: Time Intelligence</summary>
            {d.calculation_group.map((c) => <p key={c.item}><b>{c.item}:</b> <code>{c.dax}</code></p>)}
          </details>
          <details>
            <summary>Field parameter: Metric Selector</summary>
            <p>Lets a reader choose the metric a visual shows: {d.field_parameter.join(', ')}.</p>
          </details>
          <details>
            <summary>What-if parameters</summary>
            {d.what_if.map((w) => <p key={w.name}><b>{w.name}</b> ({w.min} to {w.max}, default {w.default}): {w.description}</p>)}
          </details>
          <details>
            <summary>Row-level security roles</summary>
            {d.roles.map((r) => <p key={r.name}><b>{r.name}:</b> {r.description}</p>)}
          </details>
          <details>
            <summary>Best Practice Analyzer exceptions</summary>
            {Object.entries(d.bpa_exceptions).map(([k, v]) => <p key={k}><code>{k}</code>: {v}</p>)}
          </details>
        </Card>
      </div>
      <Card title="Measure catalogue" info="Generated from the semantic model definition. Search by name, folder or meaning.">
        <input className="search" placeholder="Search measures, for example 'ETS' or 'peer'" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search measures" />
        <div className="scroll" style={{ maxHeight: 520 }}>
          {folders.map((f) => (
            <div key={f}>
              <p className="note" style={{ fontWeight: 700, marginTop: 10 }}>{f}</p>
              {measures.filter((m) => m.folder === f).map((m) => (
                <details key={m.name}>
                  <summary>{m.name}</summary>
                  <p>{m.description}</p>
                  <pre>{m.dax}</pre>
                </details>
              ))}
            </div>
          ))}
        </div>
      </Card>
      <Card title="Report pages and the paginated report">
        {d.screenshots.length > 0 ? (
          <div className="img-grid">
            {d.screenshots.map((s) => (
              <figure key={s}>
                <img src={`/powerbi/${s}`} alt={`Power BI report page: ${s.replace(/^\d+-|\.png$/g, '').replace(/-/g, ' ')}`} loading="lazy" />
                <figcaption>{s.replace(/^\d+-|\.png$/g, '').replace(/-/g, ' ')}</figcaption>
              </figure>
            ))}
          </div>
        ) : (
          <p>The report has eight pages: Fleet overview, Fleet efficiency, Slow steaming and carbon cost, Carbon ratings, Ports and weather, Explore, a Ship profile drill-through page and a ship tooltip page.</p>
        )}
        <iframe className="pdf" src="/powerbi/SegmentPerformance.pdf" title="Paginated report: segment performance (PDF)" />
        <p className="note">The paginated report is built for Power BI Report Builder: parameters for segment and year, a KPI summary against the previous year, the rating mix, the fifteen least efficient ships and the monthly carbon cost.</p>
      </Card>
      <Card title="Open the files yourself">
        <ol>
          <li>Install Power BI Desktop (free) and clone the repository.</li>
          <li>
            Open <code>powerbi/ShippingPerformance.pbip</code>. By default the model reads its data straight from the repository on GitHub, so nothing needs
            setting up. To read a local copy instead, set the DataFolder parameter (Transform data, Edit parameters) to the full path of the{' '}
            <code>data\exports\gold</code> folder in your clone, for example <code>C:\Projects\shipping-performance-analytics\data\exports\gold</code>.
          </li>
          <li>Click Refresh.</li>
          <li>For the paginated report, open <code>powerbi/paginated/SegmentPerformance.rdl</code> in Power BI Report Builder (free) and click Run. Its data is built into the file.</li>
        </ol>
      </Card>
    </>
  )
}
