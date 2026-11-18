import { useEffect, useState } from 'react'
import { load } from '../lib/data'
import { big, num, pct } from '../lib/format'
import { Loading, PageIntro } from '../components/ui'

type Analysis = Record<string, any>
type Meta = { counts: Record<string, number>; snapshot: string }

export default function Findings() {
  const [a, setA] = useState<Analysis | null>(null)
  const [m, setM] = useState<Meta | null>(null)
  useEffect(() => {
    load<Analysis>('analysis').then(setA)
    load<Meta>('meta').then(setM)
  }, [])
  if (!a || !m) return <Loading />

  const q1 = a.q1_drivers
  const q2 = a.q2_scenarios
  const ten = (rel: any) => rel.scenarios.find((s: any) => Math.abs(s.speed_change + 0.1) < 1e-9)
  const mrv10 = ten(q2.relations.mrv_estimate)
  const eng10 = ten(q2.relations.engineering)
  const q3 = a.q3_ratings
  const q4 = a.q4_ports_weather
  const q5 = a.q5_deviations
  const bands = [...q4.speed_by_wind, ...q4.speed_by_waves]
  const spread = Math.max(...bands.map((b: any) => b.speed_change)) - Math.min(...bands.map((b: any) => b.speed_change))

  const answers = [
    {
      q: '1. What drives fuel efficiency differences between ships?',
      big: `Size, then design generation`,
      text: `Across ${num(q1.ships)} ships and ${num(q1.ship_years)} ship-years, doubling gross tonnage goes with ${num(q1.size_effect_doubling_gt_pct, 1)}% more CO2 per nautical mile, and ships of the newer EEDI design generation emit ${num(Math.abs(q1.eedi_generation_effect_pct), 1)}% less per mile than older ships of the same size and speed. Annual averages show only a weak speed effect (exponent ${num(q1.cross_sectional.log_speed.estimate, 2)}, 95% interval ${num(q1.cross_sectional.log_speed.low, 2)} to ${num(q1.cross_sectional.log_speed.high, 2)}), because MRV time at sea also counts waiting at anchor.`,
      link: '#/fleet',
      linkText: 'Explore fleet efficiency',
    },
    {
      q: '2. What would slower steaming save?',
      big: `${pct(mrv10.co2_saved_share)} to ${pct(eng10.co2_saved_share)} less CO2 at 10% slower`,
      text: `For the ${num(q2.ships)} ships in ${q2.base_year}, a 10% lower speed saves between ${big(mrv10.co2_saved_t)} tonnes of CO2 (the conservative estimate from MRV data) and ${big(eng10.co2_saved_t)} tonnes (the engineering rule that fuel per mile rises with speed squared). The price is about ${num(eng10.extra_days_per_ship, 1)} extra days at sea per ship per year.`,
      link: '#/simulator',
      linkText: 'Try it in the simulator',
    },
    {
      q: '3. Which ships drift toward poor carbon ratings?',
      big: `${pct(q3.share_d_or_e_latest)} rated D or E in ${q3.latest_year}`,
      text: `In ${q3.latest_year}, ${pct(q3.share_d_or_e_latest)} of rated ship-years were D or E (95% interval ${pct(q3.share_d_or_e_latest_interval[0])} to ${pct(q3.share_d_or_e_latest_interval[1])}). Of ${num(q3.ships_compared)} ships rated in both ${q3.first_official_year} and ${q3.latest_year}, ${num(q3.ships_worse_than_first_year)} got a worse letter and ${num(q3.ships_better_than_first_year)} a better one.`,
      link: '#/ratings',
      linkText: 'See the carbon ratings',
    },
    {
      q: '4. How much time is lost waiting at Norwegian ports?',
      big: `${pct(q4.share_with_waiting)} of calls waited at anchor`,
      text: `Of ${num(q4.calls)} port calls by ${num(q4.ships)} fleet ships in August and September 2026, ${pct(q4.share_with_waiting)} waited at anchor before berthing; the median call spent ${num(q4.median_berth_h, 1)} hours alongside. Weather explains little of the leg speeds: across wind and wave bands, mean speed differs by at most ${pct(spread)} and the 95% intervals overlap.`,
      link: '#/ports',
      linkText: 'Open the port map',
    },
    {
      q: '5. Which ship-years deviate from what speed, size and age predict?',
      big: `${num(q5.flagged)} ship-years flagged`,
      text: `Of ${num(q5.ship_years_tested)} ship-years, ${num(q5.flagged_above)} burn far more per mile than ships of the same speed, size, age and segment, and ${num(q5.flagged_below)} far less. They are candidates for a closer look, not proven problems.`,
      link: '#/ship',
      linkText: 'Drill into a ship',
    },
  ]

  return (
    <>
      <PageIntro
        title="Key findings"
        what="Five business questions about vehicle carriers and ro-ro ships, each answered in one line from public data: EU emission reports for 2018 to 2025 and ship tracks along the Norwegian coast in August and September 2026."
        how="Read the bold answers. Open a question for the numbers behind it, or follow its link to explore."
        notice="Every number here is computed by the project's pipeline. Ships appear under pseudonyms such as Carrier 017."
      />
      <ol className="findings">
        {answers.map((x, i) => (
          <li key={x.q}>
            <details open={i === 0}>
              <summary>
                <span className="f-q">{x.q.replace(/^\d\. /, '')}</span>
                <span className="f-a">{x.big}</span>
              </summary>
              <p>{x.text}</p>
              <a href={x.link}>{x.linkText} &rarr;</a>
            </details>
          </li>
        ))}
      </ol>
      <section className="about card">
        <h2>About</h2>
        <p>
          An independent analytics and research project on the fuel use, emissions, carbon cost and port time of vehicle carriers and ro-ro ships, built
          only on open data and free tools. Developed by <strong>Reza Azad Gholami</strong>. Code, the Power BI project and documentation:{' '}
          <a href="https://github.com/eigenreza/shipping-performance-analytics" target="_blank" rel="noreferrer">github.com/eigenreza/shipping-performance-analytics</a>
        </p>
        <h3 className="flow-title">How it works</h3>
        <div className="flow">
          <div>
            <h3>1. Collect</h3>
            <p>Python downloads EU emission reports, Norwegian ship tracks, weather and carbon prices, all open data.</p>
          </div>
          <div>
            <h3>2. Model</h3>
            <p>dbt builds a tested star schema in DuckDB, with a Power BI semantic model on top.</p>
          </div>
          <div>
            <h3>3. Explain</h3>
            <p>Statistics with uncertainty intervals, an AI analyst checked against SQL, and this site.</p>
          </div>
        </div>
        <div className="buttons">
          <a className="btn" href="#/simulator">Try the simulator</a>
          <a className="btn secondary" href="#/fleet">Fleet</a>
          <a className="btn secondary" href="#/ratings">Ratings</a>
          <a className="btn secondary" href="#/ports">Ports</a>
          <a className="btn secondary" href="#/ship">Ships</a>
          <a className="btn secondary" href="#/powerbi">Inside the Power BI solution</a>
        </div>
        <p className="note">
          {num(m.counts.ships)} ships, {num(m.counts.ship_years)} yearly EU reports, {num(m.counts.ais_positions)} ship positions, {num(m.counts.port_calls)} port
          calls. Data snapshot {m.snapshot}.
        </p>
      </section>
    </>
  )
}
