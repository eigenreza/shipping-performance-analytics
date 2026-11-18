import { useEffect, useMemo, useState } from 'react'
import Chart, { axisStyle, tooltipStyle } from '../components/Chart'
import { Info, Knob, Legend, Loading, PageIntro, Segmented } from '../components/ui'
import { compute, curve, exponent, LETTERS, loadSim, SPEED_MAX, SPEED_MIN, type Inputs, type Reaction, type SimData } from '../lib/sim'
import { big, eur, num, pct } from '../lib/format'
import { INK, RATING_COLOR } from '../lib/theme'
import { useDetailed } from '../lib/view'

const FLEET: Record<string, { button: string; plural: string }> = {
  All: { button: 'All', plural: 'ships' },
  'Vehicle carrier': { button: 'Vehicle carriers', plural: 'vehicle carriers' },
  'Ro-ro ship': { button: 'Ro-ro', plural: 'ro-ro ships' },
}

const REACTION: Record<Reaction, { button: string; text: string }> = {
  engineering: { button: 'Engineering rule', text: 'engineering rule' },
  data: { button: 'Cautious fit', text: 'cautious fit from the yearly reports' },
}

function defaults(d: SimData): Inputs {
  return {
    speed: -0.1,
    year: d.years.includes(d.base_year + 1) ? d.base_year + 1 : d.base_year,
    carbon: Math.round(d.carbon_price),
    fuel: d.fuel_price,
    dayCost: d.day_cost,
    fleet: 'All',
    reaction: 'engineering',
  }
}

const round100 = (v: number) => `EUR ${num(Math.round(v / 100) * 100)}`
const speedText = (v: number) => (Math.abs(v) < 1e-9 ? 'no change' : pct(v, 0, true))
const speedWords = (v: number) => (Math.abs(v) < 0.0025 ? 'the 2025 speed' : `${pct(Math.abs(v), 0)} ${v < 0 ? 'slower' : 'faster'}`)
// Short form for the pinned phone bar: 29M, 1.8M, 450k.
const short = (v: number) => {
  const a = Math.abs(v)
  const s = a >= 1e9 ? `${num(a / 1e9, 1)}B` : a >= 1e6 ? `${num(a / 1e6, a >= 1e8 ? 0 : 1)}M` : a >= 1e3 ? `${num(a / 1e3, 0)}k` : num(a, 0)
  return v < 0 ? `-${s}` : s
}

export default function Simulator() {
  const [d, setD] = useState<SimData | null>(null)
  const [inp, setInp] = useState<Inputs | null>(null)
  const detailed = useDetailed()
  const [why, setWhy] = useState(false)
  const [pulse, setPulse] = useState<{ n: number; spot: string }>({ n: 0, spot: '' })
  const [tried, setTried] = useState<string | null>(null)
  useEffect(() => {
    loadSim().then((s) => {
      setD(s)
      setInp(defaults(s))
    })
  }, [])
  // A "Try" link about ratings scrolls to the ratings step once it has re-rendered.
  useEffect(() => {
    if (pulse.spot !== 'ratings') return
    const el = document.querySelector('.step2')
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    // Fall back to a jump if smooth scrolling did not get there (reduced motion, background tab).
    const id = window.setTimeout(() => {
      const box = el?.getBoundingClientRect()
      if (el && box && (box.top > window.innerHeight || box.bottom < 0)) el.scrollIntoView({ block: 'center' })
    }, 700)
    return () => window.clearTimeout(id)
  }, [pulse])
  const set = <K extends keyof Inputs>(k: K) => (v: Inputs[K]) => {
    setTried(null)
    setInp((p) => (p ? { ...p, [k]: v } : p))
  }

  const r = useMemo(() => (d && inp ? compute(d, inp) : null), [d, inp])

  const gainChart = useMemo(() => {
    if (!d || !inp || !r) return {}
    const pts = curve(d, inp, exponent(d, inp.reaction))
    const x = (s: number) => Math.round(s * 1000) / 10
    const byX = new Map(pts.map((p) => [x(p.speed), p]))
    const sign = (v: number) => (v >= 0 ? eur(v, 0) : `-${eur(-v, 0)}`)
    return {
      grid: { left: 64, right: 18, top: 24, bottom: 46 },
      tooltip: { ...tooltipStyle, trigger: 'axis', formatter: (ps: any[]) => {
        const p = byX.get(ps.find((q) => q.seriesName === 'Net gain')?.value?.[0] ?? ps[0]?.value?.[0])
        if (!p) return ''
        return [
          `<b>Speed ${p.speed > 0 ? '+' : ''}${num(p.speed * 100, 1)}%</b>`,
          `Fuel and carbon saved: ${sign(p.saved)}`,
          `Cost of the extra days: ${sign(-p.time)}`,
          `<b>Net gain: ${sign(p.net)}</b>`,
        ].join('<br/>')
      } },
      xAxis: { ...axisStyle, type: 'value', min: SPEED_MIN * 100, max: SPEED_MAX * 100, name: 'Speed change against 2025 (%)', nameLocation: 'middle', nameGap: 30,
        axisLabel: { ...axisStyle.axisLabel, formatter: (v: number) => (v > 0 ? `+${v}` : String(v)) } },
      yAxis: { ...axisStyle, type: 'value', name: 'EUR million per year', nameLocation: 'middle', nameGap: 48 },
      series: [
        {
          name: 'Net gain', type: 'line', showSymbol: false, data: pts.map((p) => [x(p.speed), p.net / 1e6]),
          lineStyle: { color: '#0b0b0b', width: 3 },
          markLine: {
            symbol: 'none', silent: true,
            data: [
              { yAxis: 0, lineStyle: { color: INK.muted, type: 'solid', width: 1 }, label: { show: false } },
              ...(r.best.net > 0 ? [{ xAxis: x(r.best.speed), lineStyle: { color: INK.secondary, type: 'dotted' as const, width: 1.5 },
                label: { formatter: 'Best', color: INK.secondary, fontSize: 12 } }] : []),
            ],
          },
        },
        ...(inp.reaction === 'data' ? (['data_low', 'data_high'] as const).map((k, i) => ({
          name: i ? '95% range, upper' : '95% range, lower', type: 'line', showSymbol: false, silent: true,
          data: curve(d, inp, d.elasticity[k]).map((p) => [x(p.speed), p.net / 1e6]),
          lineStyle: { color: INK.muted, width: 1.5, type: 'dotted' as const },
        })) : []),
        { name: 'You', type: 'scatter', symbolSize: 15, z: 5, data: [[x(inp.speed), r.netEur / 1e6]],
          itemStyle: { color: '#0b0b0b', borderColor: '#fff', borderWidth: 2.5 }, tooltip: { show: false } },
      ],
    }
  }, [d, inp, r])

  const ratingChart = useMemo(() => {
    if (!r) return {}
    const share = (arr: number[]) => arr.map((x) => (r.rated ? (x / r.rated) * 100 : 0))
    const b = share(r.before)
    const a = share(r.after)
    return {
      grid: { left: 128, right: 12, top: 4, bottom: 24 },
      tooltip: { ...tooltipStyle, trigger: 'item', formatter: (p: any) => `${p.name}<br/>Rating ${p.seriesName}: ${num(p.value, 1)}% of rated ships` },
      xAxis: { ...axisStyle, type: 'value', max: 100, axisLabel: { ...axisStyle.axisLabel, formatter: '{value}%' } },
      yAxis: { ...axisStyle, type: 'category', inverse: true, data: ['Same speed as 2025', 'Your speed'], splitLine: { show: false } },
      series: LETTERS.map((L, i) => ({
        name: L, type: 'bar', stack: 'mix', barWidth: 34,
        data: [b[i], a[i]],
        itemStyle: { color: RATING_COLOR[L], borderColor: '#fff', borderWidth: 1 },
        label: { show: true, color: i === 0 || i === 4 ? '#fff' : INK.primary, fontSize: 12, formatter: (p: any) => (p.value >= 7 ? L : '') },
      })),
    }
  }, [r])

  if (!d || !inp || !r) return <Loading />

  const base = defaults(d)
  const changed = (['fleet', 'carbon', 'fuel', 'reaction'] as const).filter((k) => inp[k] !== base[k]).length
  const fleet = FLEET[inp.fleet] ?? { button: inp.fleet, plural: inp.fleet }
  const slower = inp.speed < -1e-9
  const faster = inp.speed > 1e-9
  const moved = slower || faster
  const knots = r.baseKnots !== null && r.newKnots !== null ? `${num(r.baseKnots, 1)} to ${num(r.newKnots, 1)} knots` : ''
  const gain = r.netEur >= 0

  // The answer to the page's question, from the speed with the highest net gain.
  const answer = r.best.net > 0 && r.best.speed < 0
    ? r.best.speed <= SPEED_MIN + 1e-9
      ? <>Yes. <em>{speedWords(r.best.speed)}</em> or more pays best.</>
      : <>Yes. About <em>{speedWords(r.best.speed)}</em> pays best.</>
    : r.best.net > 0 && r.best.speed > 0
      ? <>No. With these settings, sailing <em>faster</em> pays more.</>
      : <>No. Keeping the <em>2025 speed</em> pays best.</>

  const last = d.years[d.years.length - 1]
  const tries: { label: string; patch: Partial<Inputs>; spot: string }[] = [
    { label: 'cheaper ship time', patch: { dayCost: Math.round(d.day_cost / 2) }, spot: 'answer' },
    { label: 'dearer ship time', patch: { dayCost: Math.round(d.day_cost * 1.5) }, spot: 'answer' },
    { label: 'carbon at EUR 150', patch: { carbon: 150 }, spot: 'answer' },
    { label: 'ro-ro ships only', patch: { fleet: 'Ro-ro ship' }, spot: 'answer' },
    { label: `ratings in ${last}`, patch: { year: last }, spot: 'ratings' },
    { label: 'the cautious assumption', patch: { reaction: 'data' }, spot: 'answer' },
  ]
  const tryIt = (label: string, patch: Partial<Inputs>, spot: string) => {
    setInp({ ...defaults(d), ...patch })
    setTried(label)
    setPulse((p) => ({ n: p.n + 1, spot }))
  }
  const pulsing = (spot: string) => (pulse.spot === spot ? ' pulse' : '')

  const priceYear = d.carbon_price_basis.match(/\d{4}/)?.[0] ?? ''
  const reset = <button type="button" className="link-inline" onClick={() => { setInp(defaults(d)); setTried(null) }}>Reset everything</button>
  const shipsKnob = (
    <Segmented label="Ships" value={inp.fleet} onChange={set('fleet')}
      options={['All', ...d.segments.slice().reverse()].map((s) => ({ value: s, label: FLEET[s]?.button ?? s }))}
      info="Vehicle carriers move cars and trucks on many decks. Ro-ro ships move trailers and other rolling cargo." />
  )
  const carbonKnob = (
    <Knob label="Carbon price" value={inp.carbon} min={0} max={200} step={1} onChange={set('carbon')} format={(v) => `EUR ${v} per t`}
      info="Price of one EU emission allowance, which covers one tonne of CO2. Under the EU emissions trading system (EU ETS), shipping companies buy allowances for CO2 on voyages to, from and within Europe."
      ticks={[{ value: 0, label: '0' }, { value: 100, label: '100' }, { value: 200, label: '200' }]}
      hint={<>Default: the {priceYear} average so far, <button type="button" className="link-inline" onClick={() => set('carbon')(Math.round(d.carbon_price))}>EUR {num(d.carbon_price, 0)}</button></>} />
  )
  const fuelKnob = (
    <Knob label="Fuel price" value={inp.fuel} min={300} max={1000} step={10} onChange={set('fuel')} format={(v) => `EUR ${v} per t`}
      info="Price of one tonne of marine fuel. The default is a round planning figure, not a market quote."
      ticks={[{ value: 300, label: '300' }, { value: 650, label: '650' }, { value: 1000, label: '1,000' }]}
      hint={`Default: EUR ${num(d.fuel_price)}, a planning figure.`} />
  )
  const yearKnob = (label: string) => (
    <Knob label={label} value={inp.year} min={d.years[0]} max={d.years[d.years.length - 1]} step={1} onChange={set('year')} format={String}
      info="Sets two rules. The EU carbon charge: ships pay for a growing share of their CO2 until it reaches the full amount. The carbon rating (CII): the allowed carbon intensity gets stricter every year, set by IMO up to 2030."
      ticks={d.years.map((y) => ({ value: y, label: `'${String(y).slice(2)}` }))}
      hint={<>EU charges for {pct(r.etsShare, 0)} of the CO2 it covers. Rating limit {r.tighter > 0 ? `${pct(r.tighter, 1)} stricter than in ${d.base_year}` : `as in ${d.base_year}`}.</>} />
  )
  const reactionKnob = (
    <Segmented label="How fuel reacts to speed" value={inp.reaction} onChange={set('reaction')}
      options={(['engineering', 'data'] as Reaction[]).map((k) => ({ value: k, label: REACTION[k].button }))}
      info={`Engineering rule: fuel per mile rises with speed squared, the standard rule for a ship at sea. Cautious fit: the relation estimated across ships in the yearly EU reports (exponent ${num(d.elasticity.data, 2)}), a lower bound because yearly time at sea also counts waiting at anchor.`} />
  )

  const reasons = (
    <ul className="read why">
      {moved && (
        <li>
          <b>Where the {gain ? 'gain' : 'loss'} comes from.</b>{' '}
          {slower
            ? <>Fuel and carbon saved: {eur(r.savedEur, 0)} ({eur(r.fuelEur, 0)} fuel, {eur(r.etsEur, 0)} carbon). Cost of {num(r.extraDaysPerShip, 1)} more days at sea per ship, at {round100(inp.dayCost)} a day: {eur(r.timeEur, 0)}.</>
            : <>Time saved: {num(-r.extraDaysPerShip, 1)} days per ship, worth {eur(-r.timeEur, 0)}. Extra fuel and carbon: {eur(-r.savedEur, 0)}.</>}
        </li>
      )}
      <li>
        {r.best.net > 0 ? (
          <>
            <b>Best speed: {speedWords(r.best.speed)}</b>
            {r.baseKnots !== null && <> ({num(r.baseKnots * (1 + r.best.speed), 1)} knots)</>}, a net gain of {eur(r.best.net, 0)} a year.{' '}
            {Math.abs(r.best.speed - inp.speed) > 0.005
              ? <button type="button" className="link-inline" onClick={() => set('speed')(r.best.speed)}>Go there</button>
              : 'You are there.'}
          </>
        ) : (
          <><b>Best: keep the 2025 speed.</b> No speed change gains money with these settings.</>
        )}
      </li>
      {slower && r.breakEven !== null && (
        <li>
          <b>Break-even day cost: {round100(r.breakEven)}.</b> Slowing {pct(-inp.speed, 0)} pays while a day at sea costs less than that.
        </li>
      )}
      {moved && (
        <li>
          <b>How sure is this?</b> With the {REACTION[r.other].text}, the same setting would {r.otherNetEur >= 0 ? 'gain' : 'lose'}{' '}
          {eur(Math.abs(r.otherNetEur), 0)} a year.{' '}
          {inp.reaction === 'data' && <>The fit itself is uncertain: its 95% range gives a net result between {r.fitRange[0] < 0 ? '-' : ''}{eur(Math.abs(r.fitRange[0]), 0)} and {r.fitRange[1] < 0 ? '-' : ''}{eur(Math.abs(r.fitRange[1]), 0)} (dotted lines on the chart).{' '}</>}
          {inp.reaction === 'engineering'
            ? 'That fit lets fuel barely react to speed, so treat it as a lower bound. Ship physics supports the engineering rule.'
            : 'Ship physics supports the engineering rule; the fit you chose is a lower bound.'}
        </li>
      )}
    </ul>
  )

  return (
    <>
      <PageIntro
        compact
        title="Should ships sail slower?"
        lede={`Slower sailing burns less fuel and carbon, but each extra day at sea costs money. Based on the ${num(d.ships.length)} vehicle carriers and ro-ro ships that reported their ${d.base_year} fuel and CO2 to the EU.`}
        what="A simulator of the trade-off between fuel and carbon saved and the cost of more days at sea."
        how="Move the two sliders next to the chart. Switch to Detailed at the top right for all seven settings and the reasons behind the answer. Scroll down for CO2 and carbon ratings."
        notice="The curve has a peak: a little slower usually pays, much slower stops paying because the extra days cost more than the fuel saved."
      />

      <section className={`card hero${detailed ? ' detailed' : ''}`} data-tour="answer">
        <div className="hero-head">
          <h2 className={`answer${pulsing('answer')}`} key={`a${pulse.n}`}>{answer}</h2>
        </div>
        <p className="summary">
          <span className={`dot ${moved ? (gain ? 'good' : 'bad') : ''}`} aria-hidden="true" />
          {moved ? (
            <>
              Your setting ({speedText(inp.speed)}, {knots}): <b>{gain ? 'gains' : 'loses'} {eur(Math.abs(r.netEur), 0)} a year</b>
              <span className="sep">·</span>CO2 {slower ? '-' : '+'}{big(Math.abs(r.co2Saved))} t
              <span className="sep">·</span>{slower ? '+' : '-'}{num(Math.abs(r.extraDaysPerShip), 1)} days at sea per ship
            </>
          ) : (
            <>At the 2025 speed nothing changes. Move the speed slider.</>
          )}
          {!detailed && (
            <button type="button" className="why-link" aria-expanded={why} onClick={() => setWhy((w) => !w)}>
              {why ? 'Hide why' : 'Why?'}
            </button>
          )}
        </p>
        {(detailed || why) && reasons}
        <div className="hero-body">
          <div className="hero-chart">
            <div className="hero-chart-title">
              Net gain per year at every speed{' '}
              <Info text={`Fuel and carbon saved minus the cost of the extra days at sea, for every speed change, using the ${REACTION[inp.reaction].text}. Above the line it pays, below it loses money. The dot is your setting. Hover the curve for the breakdown.`} />
            </div>
            <Chart option={gainChart} height={300} ariaLabel="Net gain per year against speed change, with your setting and the best speed marked" />
            <p className="tries" data-tour="tries">
              <span>Try:</span>
              {tries.map((x, i) => (
                <span key={x.label}>
                  {i > 0 && <span className="sep">·</span>}
                  <button type="button" className={tried === x.label ? 'on' : ''} onClick={() => tryIt(x.label, x.patch, x.spot)}>{x.label}</button>
                </span>
              ))}
              {tried && <button type="button" className="undo" onClick={() => { setInp(defaults(d)); setTried(null) }}>back to the start</button>}
            </p>
          </div>
          <div className="hero-knobs" data-tour="sliders">
            <Knob label="Speed" value={inp.speed} min={SPEED_MIN} max={SPEED_MAX} step={0.01} onChange={set('speed')} format={speedText}
              info="Change in average speed against each ship's 2025 speed, for the same distance sailed. -10% means 10% slower."
              ticks={[{ value: -0.2, label: '-20%' }, { value: -0.1, label: '-10%' }, { value: 0, label: '0' }, { value: 0.1, label: '+10%' }]}
              hint={knots ? <>Average {knots}</> : undefined} />
            <Knob label="Cost of a day at sea" value={inp.dayCost} min={0} max={100000} step={1000} onChange={set('dayCost')} format={round100}
              info="What one extra day of a ship's time costs: charter hire or capital cost, crew and running costs, and later delivery of the cargo. The default is a round planning figure, not a market quote. Set your own."
              ticks={[{ value: 0, label: '0' }, { value: 50000, label: '50,000' }, { value: 100000, label: '100,000' }]}
              hint="Per ship per day. The default is a planning figure: set your own." />
            {!detailed && (
              <details className="more-settings" data-tour="more">
                <summary>
                  More settings{changed > 0 && <span className="changed">{changed} changed</span>}
                </summary>
                <div className="more-body">
                  {shipsKnob}
                  {carbonKnob}
                  {fuelKnob}
                  {reactionKnob}
                  {reset}
                </div>
              </details>
            )}
          </div>
        </div>
        {detailed && (
          <div className="all-settings" data-tour="more">
            <div className="all-head">
              <h3>All settings</h3>
              {reset}
            </div>
            <div className="all-grid">
              <div className="all-group">
                <h4>Ships and year</h4>
                {shipsKnob}
                {yearKnob('Year')}
              </div>
              <div className="all-group">
                <h4>Prices</h4>
                {carbonKnob}
                {fuelKnob}
              </div>
              <div className="all-group">
                <h4>Assumption</h4>
                {reactionKnob}
                <p className="note">The engineering rule is the standard for a ship at sea. The cautious fit, from the yearly reports, is a lower bound.</p>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className={`card step2${pulsing('ratings')}`} key={`s${pulse.spot === 'ratings' ? pulse.n : 0}`}>
        <h2>What it does to CO2 and carbon ratings</h2>
        <p className="answer-sub">
          {moved ? (
            <>
              At your speed the {fleet.plural} emit <b>{big(Math.abs(r.co2Saved))} tonnes {slower ? 'less' : 'more'} CO2</b> a year ({pct(Math.abs(r.co2Share), 0)} of their total).{' '}
            </>
          ) : null}
          {r.deBefore !== null && r.deAfter !== null && (
            <>
              Rated D or E in {inp.year}: <b>{pct(r.deBefore, 0)}</b> at the 2025 speed{moved && <>, <b>{pct(r.deAfter, 0)}</b> at yours</>}.
            </>
          )}
        </p>
        <div className="step2-body">
          <div className="step2-knob">
            {yearKnob('Rating year')}
          </div>
          <div className="step2-chart">
            <div className="hero-chart-title">
              Carbon ratings, {inp.year}{' '}
              <Info text={`CII: the IMO carbon intensity rating, from A (best) to E (worst), from each ship's ${d.base_year} report against the limit of the chosen year. A ship rated D three years in a row, or E once, must file a corrective plan. ${num(r.rated)} of the ${num(r.ships)} ships can be rated.`} />
            </div>
            <Legend items={LETTERS.map((L) => ({ label: L, color: RATING_COLOR[L] }))} />
            <Chart option={ratingChart} height={140} ariaLabel={`Share of ships by carbon rating in ${inp.year}, at the 2025 speed and at your speed`} />
          </div>
        </div>
      </section>

      <details className="card method">
        <summary>How is this calculated?</summary>
        <p>
          <b>Method.</b> Each ship sails the same distance as in {d.base_year}. Fuel and CO2 change with (1 + speed change) to the power of the speed
          relation. Fuel saved is priced at the fuel price. CO2 saved under the EU carbon charge (all CO2 on voyages within Europe and at berth, half on voyages
          into or out of Europe, {pct(r.etsShare, 0)} of it charged in {inp.year}) is priced at the carbon price. Extra days = hours at sea x (1 / (1 + speed
          change) - 1) / 24, priced at the cost of a day. Ratings use each ship's {d.base_year} carbon intensity against the IMO limit of the chosen year.
        </p>
      </details>

      <div className={`sim-sticky ${moved ? (gain ? 'good' : 'bad') : ''}`} aria-hidden="true">
        {moved ? (
          <>
            <b>{speedText(inp.speed)}</b>
            <span>Net <b>EUR {short(r.netEur)}</b>/yr</span>
            <span>CO2 {slower ? '-' : '+'}{short(Math.abs(r.co2Saved))} t</span>
          </>
        ) : (
          <span>Move the speed slider</span>
        )}
      </div>

      <nav className="more-links" aria-label="Explore further">
        <span>Go deeper:</span>
        <a href="#/findings">Key findings</a>
        <a href="#/fleet">Fleet efficiency</a>
        <a href="#/ratings">Carbon ratings over time</a>
        <a href="#/ports">Ports and weather</a>
        <a href="#/ship">One ship at a time</a>
      </nav>
    </>
  )
}
