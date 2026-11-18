import { useEffect, useMemo, useState } from 'react'
import Chart, { tooltipStyle } from '../components/Chart'
import { Card, Kpi, Loading, PageIntro } from '../components/ui'
import { load } from '../lib/data'
import { num } from '../lib/format'

type Build = {
  sources: { name: string; publisher: string; use: string; licence: string; url: string }[]
  lineage: { nodes: { id: string; name: string; layer: string; description: string }[]; edges: [string, string][]; tests: number }
  fabric: { piece: string; fabric: string; state: string }[]
  status: { check: string; detail: string; status: string }[] | null
}

const LAYERS = ['source', 'seed', 'staging', 'intermediate', 'marts']
const LAYER_LABEL: Record<string, string> = { source: 'Raw files', seed: 'Reference seeds', staging: 'Staging', intermediate: 'Intermediate', marts: 'Marts (star schema)' }
const LAYER_COLOR: Record<string, string> = { source: '#c9c8c3', seed: '#eda100', staging: '#86b6ef', intermediate: '#3987e5', marts: '#1c5cab' }

export default function Built() {
  const [d, setD] = useState<Build | null>(null)
  useEffect(() => {
    load<Build>('build').then(setD)
  }, [])

  const option = useMemo(() => {
    if (!d) return {}
    const cols: Record<string, number> = { source: 0, seed: 0, staging: 1, intermediate: 2, marts: 3 }
    const counters = [0, 0, 0, 0]
    const nodes = [...d.lineage.nodes]
      .sort((a, b) => LAYERS.indexOf(a.layer) - LAYERS.indexOf(b.layer) || a.name.localeCompare(b.name))
      .map((n) => {
        const c = cols[n.layer] ?? 0
        const y = counters[c]++
        return {
          id: n.id, name: n.name, x: c * 300, y: y * 30,
          symbolSize: 10, itemStyle: { color: LAYER_COLOR[n.layer] ?? '#999' },
          label: { show: true, position: 'right', fontSize: 11, color: '#52514e' },
          tooltip: { formatter: `<b>${n.name}</b><br/>${LAYER_LABEL[n.layer] ?? n.layer}<br/>${n.description}` },
        }
      })
    return {
      tooltip: { ...tooltipStyle, confine: true, extraCssText: tooltipStyle.extraCssText + ' max-width: 320px; white-space: normal;' },
      series: [{
        type: 'graph', layout: 'none', roam: true, data: nodes,
        links: d.lineage.edges.map(([s, t]) => ({ source: s, target: t })),
        lineStyle: { color: '#c9c8c3', curveness: 0.15, opacity: 0.8 }, edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 5,
        emphasis: { focus: 'adjacency' },
      }],
    }
  }, [d])

  if (!d) return <Loading />
  const counts = LAYERS.map((l) => d.lineage.nodes.filter((n) => n.layer === l).length)
  return (
    <>
      <PageIntro
        title="How it is built"
        what="The data sources and their licences, the warehouse lineage, the automated checks and how the project maps to Microsoft Fabric."
        how="Hover a node in the lineage to see what the model does; drag or zoom to move around. The status table shows the latest freshness and quality checks."
        notice="One command refreshes everything, from download to this site, and every step is tested."
      />
      <div className="grid kpis">
        <Kpi label="dbt models" value={num(counts[2] + counts[3] + counts[4])} sub={`${counts[2]} staging, ${counts[3]} intermediate, ${counts[4]} marts`} info="dbt builds the warehouse in DuckDB in three layers." />
        <Kpi label="dbt tests" value={num(d.lineage.tests)} sub="unique, not null, relationships, ranges, freshness" info="Data tests run on every build; a failing test stops the refresh." />
        <Kpi label="Sources" value={num(d.sources.length)} sub="all open" info="Every source is open data with a licence recorded in DATA_NOTICE.md." />
        <Kpi label="Status checks passing" value={d.status ? `${d.status.filter((s) => s.status === 'ok').length} / ${d.status.length}` : 'n/a'} sub="freshness and quality" info="Written by `spa status` after each refresh." />
      </div>
      <Card title="Warehouse lineage" info="From raw Parquet files (left) through staging and intermediate models to the star schema marts (right).">
        <div className="legend">{LAYERS.map((l) => <span key={l}><i style={{ background: LAYER_COLOR[l] }} />{LAYER_LABEL[l]}</span>)}</div>
        <Chart option={option} height={560} ariaLabel="dbt lineage graph from raw files to marts" />
      </Card>
      <div className="grid two">
        <Card title="Data sources and licences">
          <table className="data">
            <thead><tr><th>Source</th><th>Used for</th><th>Licence</th></tr></thead>
            <tbody>
              {d.sources.map((s) => (
                <tr key={s.name}><td><a href={s.url} target="_blank" rel="noreferrer">{s.name}</a><br /><span className="note">{s.publisher}</span></td><td>{s.use}</td><td>{s.licence}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card title="Refresh and monitoring" info="`spa refresh` runs: ingest, dbt build and tests, exports, analysis, AI evaluation from cache, this site's data, and the status checks below.">
          <table className="data">
            <thead><tr><th>Check</th><th>Result</th><th>Status</th></tr></thead>
            <tbody>
              {(d.status ?? []).map((s) => (
                <tr key={s.check}><td>{s.check}</td><td>{s.detail}</td><td><span className={`pill ${s.status === 'ok' ? 'ok' : s.status === 'warn' ? 'warn' : 'bad'}`}>{s.status}</span></td></tr>
              ))}
            </tbody>
          </table>
          <p className="note">Continuous integration on GitHub Actions runs linting, the Python tests, a dbt build on small fixtures, the Best Practice Analyzer and a check that the README tables match the result files.</p>
        </Card>
      </div>
      <Card title="Microsoft Fabric: built Fabric-ready" info="The project runs on a laptop at no cost. Each piece maps to a Fabric item; the gold Delta tables could be loaded into a lakehouse unchanged.">
        <table className="data">
          <thead><tr><th>In this project</th><th>Fabric counterpart</th><th>State</th></tr></thead>
          <tbody>{d.fabric.map((f) => <tr key={f.piece}><td>{f.piece}</td><td>{f.fabric}</td><td>{f.state}</td></tr>)}</tbody>
        </table>
      </Card>
    </>
  )
}
