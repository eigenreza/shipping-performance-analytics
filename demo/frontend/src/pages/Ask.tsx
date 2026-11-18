import { Fragment, useEffect, useMemo, useState } from 'react'
import { Card, Info, Loading, PageIntro, Select } from '../components/ui'
import { load } from '../lib/data'
import { num, pct } from '../lib/format'

type Item = { id: string; split: string; question: string; type: string; gold: any; answer: string | null; correct: boolean; text: string; sql: string[]; steps: number; latency_s: number; error: string | null }
type Run = { model: string; label: string; items: Item[] }
type Split = { answered: number; correct: number; accuracy: number | null; low: number | null; high: number | null }
type Summ = { model: string; label: string; coverage: string; stopped: string | null; dev: Split; test: Split; median_latency_s?: number; mean_input_tokens?: number; mean_output_tokens?: number; mean_steps?: number; errors?: number; tool_error_share?: number }
type Finding = { text: string; status: string; numbers: { text: string; supported: boolean }[] }
type Insight = { model: string; label: string; findings: number; supported: number; unsupported: number; no_numbers: number; share_supported: number | null; share_unsupported: number | null; pages: { page: string; findings: Finding[] }[] }
type AI = { summary: { questions: number; dev: number; test: number; analyst: Summ[]; insights: any[] } | null; runs: Run[]; insights: Insight[] }

function Highlight({ f }: { f: Finding }) {
  // Mark each checked number in the finding: green when the data supports it, red when not.
  let rest = f.text
  const parts: React.ReactNode[] = []
  f.numbers.forEach((n, i) => {
    const at = rest.indexOf(n.text)
    if (at < 0) return
    parts.push(<Fragment key={`t${i}`}>{rest.slice(0, at)}</Fragment>)
    parts.push(<span key={`n${i}`} className={n.supported ? 'mark-ok' : 'mark-bad'} title={n.supported ? 'Found in the page data' : 'Not found in the page data'}>{n.text}</span>)
    rest = rest.slice(at + n.text.length)
  })
  parts.push(<Fragment key="end">{rest}</Fragment>)
  return <>{parts}</>
}

export default function Ask() {
  const [d, setD] = useState<AI | null>(null)
  const [model, setModel] = useState('')
  const [filter, setFilter] = useState<'all' | 'correct' | 'wrong'>('all')
  useEffect(() => {
    load<AI>('ai').then((x) => {
      setD(x)
      const best = [...(x.summary?.analyst ?? [])].sort((a, b) => (b.test.accuracy ?? 0) - (a.test.accuracy ?? 0))[0]
      setModel(best?.model ?? x.runs[0]?.model ?? '')
    })
  }, [])
  const run = useMemo(() => d?.runs.find((r) => r.model === model), [d, model])
  const ins = useMemo(() => d?.insights.find((r) => r.model === model), [d, model])
  if (!d) return <Loading />
  if (!d.summary) return <p>The AI evaluation has not been run yet.</p>
  const S = d.summary
  const items = (run?.items ?? []).filter((i) => (filter === 'all' ? true : filter === 'correct' ? i.correct : !i.correct))
  const ranked = [...S.analyst].sort((a, b) => (b.test.accuracy ?? 0) - (a.test.accuracy ?? 0))
  const best = ranked[0]
  const worst = ranked[ranked.length - 1]
  const insRanked = [...d.insights].sort((a, b) => (b.share_supported ?? 0) - (a.share_supported ?? 0))

  return (
    <>
      <PageIntro
        title="Ask the data"
        what={`An AI analyst answers ${S.questions} business questions by calling tools on the warehouse: a metric catalog with the same definitions as the Power BI measures, and read-only SQL. Every answer is scored against the true value computed by SQL.`}
        how="Pick a model to see its recorded answers, the SQL it ran and whether it was right. Below, an AI insight writer drafts findings and a checker marks every number it could or could not find in the data."
        notice={`The best model answered ${pct(best.test.accuracy, 0)} of the ${S.test} test questions correctly and the weakest ${pct(worst.test.accuracy, 0)}. The same tools and data, very different reliability: answers need checking.`}
      />
      <Card title="Accuracy scorecard" info="Test split only (the development questions were set aside for prompt work). Interval: Wilson 95%. Latency and tokens per question, including tool calls.">
        <table className="data">
          <thead>
            <tr><th>Model</th><th className="n">Test accuracy</th><th className="n">95% interval</th><th className="n">Dev accuracy</th><th className="n">Median seconds</th><th className="n">Tokens in / out</th><th className="n">Tool rounds per question</th><th>Coverage</th></tr>
          </thead>
          <tbody>
            {ranked.map((s) => (
              <tr key={s.model}>
                <td>{s.label}</td>
                <td className="n"><b>{pct(s.test.accuracy, 0)}</b> ({s.test.correct}/{s.test.answered})</td>
                <td className="n">{pct(s.test.low, 0)} to {pct(s.test.high, 0)}</td>
                <td className="n">{pct(s.dev.accuracy, 0)}</td>
                <td className="n">{num(s.median_latency_s, 1)}</td>
                <td className="n">{num(s.mean_input_tokens)} / {num(s.mean_output_tokens)}</td>
                <td className="n">{num((s.mean_steps ?? 1) - 1, 1)}</td>
                <td>{s.coverage}{s.stopped ? ' (stopped: free quota)' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <div className="controls">
        <Select label="Model" value={model} onChange={setModel} options={d.runs.map((r) => ({ value: r.model, label: r.label }))}
          info="Recorded answers of the chosen model. Nothing is called live; these are the evaluation runs." />
        <Select label="Show" value={filter} onChange={setFilter}
          options={[{ value: 'all', label: 'All answers' }, { value: 'correct', label: 'Correct only' }, { value: 'wrong', label: 'Wrong only' }]}
          info="Filter the recorded answers by their score." />
      </div>
      <Card title={`Recorded answers: ${run?.label ?? ''}`} info="Each answer shows the model's text, the SQL it ran (the metric tool's SQL is shown too) and the correct value computed directly by SQL.">
        {items.map((i) => (
          <details key={i.id}>
            <summary>
              <span className={`pill ${i.correct ? 'ok' : 'bad'}`}>{i.correct ? 'correct' : 'wrong'}</span> {i.question}
            </summary>
            <p><b>Answer:</b> {i.answer ?? 'none'} &nbsp; <b>Correct value:</b> {typeof i.gold === 'number' ? num(i.gold, Math.abs(i.gold) < 10 ? 4 : 1) : String(i.gold)} &nbsp; <span className="note">{i.split === 'dev' ? 'development question' : 'test question'}, {num(i.latency_s, 1)} s</span></p>
            {i.text && <p className="note">{i.text.replace(/ANSWER:.*$/s, '').trim()}</p>}
            {i.error && <p className="note">Run error: {i.error}</p>}
            {i.sql.length > 0 ? i.sql.map((s, k) => <pre key={k}>{s}</pre>) : <p className="note">No SQL ran: the model answered without using a tool.</p>}
          </details>
        ))}
      </Card>
      <div className="grid two">
        <Card title="Insight writer and number checker" info="The writer gets the data behind a page and writes three findings. The checker extracts every number and looks for it in the data, allowing differences, ratios and rounding. Green: found. Red: not found.">
          <table className="data">
            <thead><tr><th>Model</th><th className="n">Findings</th><th className="n">All numbers supported</th><th className="n">At least one unsupported</th></tr></thead>
            <tbody>
              {insRanked.map((s) => (
                <tr key={s.model}><td>{s.label}</td><td className="n">{s.findings}</td><td className="n">{pct(s.share_supported, 0)}</td><td className="n">{pct(s.share_unsupported, 0)}</td></tr>
              ))}
            </tbody>
          </table>
          {ins?.pages.map((p) => (
            <div key={p.page}>
              <p className="note" style={{ marginTop: 10 }}>Page: {p.page}</p>
              <ul>
                {p.findings.map((f, k) => (
                  <li key={k} style={{ fontSize: 13.5, marginBottom: 4 }}>
                    <Highlight f={f} />{' '}
                    <span className={`pill ${f.status === 'supported' ? 'ok' : f.status === 'unsupported' ? 'bad' : 'warn'}`}>{f.status}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </Card>
        <Card title="What the AI is good and bad at here">
          <p>
            <b>Good:</b> turning a plain question into the right metric and filters when a catalog metric fits; writing correct SQL joins on a documented star
            schema; quoting numbers it has just read. {best.label} reached {pct(best.test.accuracy, 0)} on the test questions.
          </p>
          <p>
            <b>Bad:</b> {worst.label} often skipped a filter (for example the segment), confused a share with a percentage, answered without calling a tool, or kept calling tools without reaching an answer,
            and reached {pct(worst.test.accuracy, 0)}. Insight writers sometimes state a number that is close to, but not, the data value.
          </p>
          <p>
            <b>How this project uses it:</b> every answer shows its SQL, every number in a written finding is checked automatically, and the evaluation questions
            and scoring rules were frozen before any model was scored. Model calls are cached, so the evaluation reruns offline. <Info text="Questions, gold SQL and scoring rules are in src/spa/ai/questions.py; results in results/ai/." />
          </p>
        </Card>
      </div>
    </>
  )
}
