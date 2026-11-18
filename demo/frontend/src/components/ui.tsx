import { useState, type ReactNode } from 'react'

/** Small "i" button that shows a definition on hover, focus or tap. */
export function Info({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="info" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="info-btn" aria-label={text} onClick={() => setOpen((o) => !o)} onBlur={() => setOpen(false)}>
        i
      </button>
      {open && <span className="info-pop" role="tooltip">{text}</span>}
    </span>
  )
}

/** The three plain lines that open every page. */
export function PageIntro({ title, what, how, notice, compact, lede }: {
  title: string; what: string; how: string; notice: ReactNode; compact?: boolean; lede?: string
}) {
  if (compact) {
    return (
      <section className="intro compact" data-tour="intro">
        <h1>{title}</h1>
        {lede && <p className="lede">{lede}</p>}
        <details className="about-page">
          <summary>About this page</summary>
          <dl>
            <div><dt>What this is</dt><dd>{what}</dd></div>
            <div><dt>How to use it</dt><dd>{how}</dd></div>
            <div><dt>What to notice</dt><dd>{notice}</dd></div>
          </dl>
        </details>
      </section>
    )
  }
  return (
    <section className="intro" data-tour="intro">
      <h1>{title}</h1>
      <dl>
        <div>
          <dt>What this is</dt>
          <dd>{what}</dd>
        </div>
        <div>
          <dt>How to use it</dt>
          <dd>{how}</dd>
        </div>
        <div>
          <dt>What to notice</dt>
          <dd>{notice}</dd>
        </div>
      </dl>
    </section>
  )
}

export function Kpi({ label, value, sub, info }: { label: string; value: string; sub?: ReactNode; info: string }) {
  return (
    <div className="kpi">
      <div className="kpi-label">
        {label} <Info text={info} />
      </div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  )
}

export function Card({ title, info, children, className = '' }: { title: string; info?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      <h2>
        {title} {info && <Info text={info} />}
      </h2>
      {children}
    </section>
  )
}

type Option<T> = { value: T; label: string }

export function Select<T extends string | number>({
  label, value, options, onChange, info,
}: { label: string; value: T; options: Option<T>[]; onChange: (v: T) => void; info: string }) {
  return (
    <label className="control" title={info}>
      <span>
        {label} <Info text={info} />
      </span>
      <select
        value={String(value)}
        onChange={(e) => {
          const o = options.find((x) => String(x.value) === e.target.value)
          if (o) onChange(o.value)
        }}
      >
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export function Slider({
  label, value, min, max, step, onChange, format, info,
}: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; format: (v: number) => string; info: string }) {
  return (
    <label className="control slider" title={info}>
      <span>
        {label} <Info text={info} /> <strong>{format(value)}</strong>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} aria-valuetext={format(value)} />
    </label>
  )
}

/** A large slider with its value, tick labels and a short hint underneath. */
export function Knob({
  label, value, min, max, step, onChange, format, info, ticks, hint,
}: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void
  format: (v: number) => string; info: string; ticks: { value: number; label: string }[]; hint?: ReactNode
}) {
  const at = (v: number) => `${((v - min) / (max - min)) * 100}%`
  return (
    <div className="knob">
      <label className="knob-head">
        <span>
          {label} <Info text={info} />
        </span>
        <output>{format(value)}</output>
        <input
          type="range" min={min} max={max} step={step} value={value} aria-valuetext={format(value)}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ ['--fill' as string]: at(value) }}
        />
      </label>
      <div className="knob-ticks" aria-hidden="true">
        {ticks.map((t) => (
          <button type="button" tabIndex={-1} key={t.value} style={{ left: at(t.value) }} onClick={() => onChange(t.value)}>
            {t.label}
          </button>
        ))}
      </div>
      {hint && <div className="knob-hint">{hint}</div>}
    </div>
  )
}

/** A row of buttons for choosing one of a few options. */
export function Segmented<T extends string | number>({
  label, value, options, onChange, info,
}: { label: string; value: T; options: Option<T>[]; onChange: (v: T) => void; info: string }) {
  return (
    <div className="knob">
      <div className="knob-head">
        <span>
          {label} <Info text={info} />
        </span>
      </div>
      <div className="seg" role="group" aria-label={label}>
        {options.map((o) => (
          <button type="button" key={String(o.value)} aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span key={i.label}>
          <i style={{ background: i.dashed ? 'none' : i.color, borderTop: i.dashed ? `2px dashed ${i.color}` : undefined }} />
          {i.label}
        </span>
      ))}
    </div>
  )
}

export function Loading() {
  return <p className="loading">Loading data...</p>
}

export function nav(path: string) {
  window.location.hash = path
}

/** The question a page answers, the answer in one line, and one supporting sentence. */
export function Answer({ question, children, sub }: { question: string; children: ReactNode; sub?: ReactNode }) {
  return (
    <section className="card answer-card" data-tour="answer">
      <p className="question">{question}</p>
      <h2 className="answer">{children}</h2>
      {sub && <p className="answer-sub">{sub}</p>}
    </section>
  )
}
