import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import Tour, { useTour } from './components/Tour'
import { setDetailed, useDetailed } from './lib/view'
import { Loading } from './components/ui'

const REPO = 'https://github.com/eigenreza/shipping-performance-analytics'

// After a new deployment the old page chunks are gone. Reload once to pick up the new build.
function page(load: () => Promise<{ default: React.ComponentType<{ param: string }> }>) {
  return lazy(() =>
    load().catch((e) => {
      if (!sessionStorage.getItem('spa-reloaded')) {
        sessionStorage.setItem('spa-reloaded', '1')
        window.location.reload()
      }
      throw e
    }),
  )
}

const PAGES = [
  { path: 'simulator', label: 'Simulator', main: true, Component: page(() => import('./pages/Simulator')) },
  { path: 'findings', label: 'Key findings', main: true, Component: page(() => import('./pages/Findings')) },
  { path: 'fleet', label: 'Fleet', main: true, Component: page(() => import('./pages/Fleet')) },
  { path: 'ratings', label: 'Ratings', main: true, Component: page(() => import('./pages/Ratings')) },
  { path: 'ports', label: 'Ports', main: true, Component: page(() => import('./pages/Ports')) },
  { path: 'ship', label: 'Ships', main: true, Component: page(() => import('./pages/Ship')) },
  { path: 'ask', label: 'Ask the data (AI check)', main: false, Component: page(() => import('./pages/Ask')) },
  { path: 'powerbi', label: 'Inside the Power BI solution', main: false, Component: page(() => import('./pages/PowerBI')) },
  { path: 'built', label: 'How it is built', main: false, Component: page(() => import('./pages/Built')) },
]

// Pages with a Simple and a Detailed view.
const VIEW_PAGES = new Set(['simulator', 'fleet', 'ratings', 'ports', 'ship'])

// Older links keep working.
const ALIASES: Record<string, string> = { start: 'findings', scenarios: 'simulator', '': 'simulator' }

function MoreMenu({ current }: { current: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [])
  const extra = PAGES.filter((p) => !p.main)
  const active = extra.some((p) => p.path === current)
  return (
    <div className="more" ref={ref}>
      <button type="button" aria-expanded={open} aria-haspopup="true" className={active ? 'active' : ''} onClick={() => setOpen((o) => !o)}>
        Behind the scenes <span aria-hidden="true">&#9662;</span>
      </button>
      {open && (
        <div className="more-menu" role="menu">
          {extra.map((p) => (
            <a key={p.path} role="menuitem" href={`#/${p.path}`} aria-current={p.path === current ? 'page' : undefined} onClick={() => setOpen(false)}>
              {p.label}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

function useRoute() {
  const read = () => window.location.hash.replace(/^#\/?/, '')
  const [route, setRoute] = useState(read())
  useEffect(() => {
    const on = () => {
      setRoute(read())
      window.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
      />
    </svg>
  )
}

export default function App() {
  useEffect(() => sessionStorage.removeItem('spa-reloaded'), [])
  const route = useRoute()
  const tour = useTour()
  const detailed = useDetailed()
  const [first, ...rest] = route.split('/')
  const base = ALIASES[first] ?? first
  const page = PAGES.find((p) => p.path === base) ?? PAGES[0]
  const Page = page.Component

  return (
    <>
      <a href="#main" className="skip">Skip to content</a>
      <header className="top">
        <div className="top-inner">
          <a className="brand" href="#/simulator" data-tour="brand">
            <img src="/favicon.svg" alt="" width="28" height="28" />
            <span>
              <strong>Shipping performance analytics</strong>
              <small>Fuel, CO2, EU carbon cost and port time of vehicle carriers and ro-ro ships</small>
            </span>
          </a>
          <div className="top-actions" data-tour="help">
            {VIEW_PAGES.has(page.path) && (
              <div className="view-switch dark" role="group" aria-label="How much to show" data-tour="view"
                title="Simple shows the answer and the main chart. Detailed adds every setting, number and table.">
                <button type="button" aria-pressed={!detailed} onClick={() => setDetailed(false)}>Simple</button>
                <button type="button" aria-pressed={detailed} onClick={() => setDetailed(true)}>Detailed</button>
              </div>
            )}
            <a className="gh" href={REPO} target="_blank" rel="noreferrer" title="Source code, Power BI files and documentation on GitHub">
              <GitHubIcon /> <span>GitHub</span>
            </a>
            <button type="button" className="help" onClick={tour.start} aria-label="Replay the guided tour" title="Replay the guided tour">
              ?
            </button>
          </div>
        </div>
        <nav className="tabs" data-tour="nav" aria-label="Pages">
          {PAGES.filter((p) => p.main).map((p) => (
            <a key={p.path} href={`#/${p.path}`} aria-current={p === page ? 'page' : undefined}>
              {p.label}
            </a>
          ))}
          <MoreMenu current={page.path} />
        </nav>
      </header>
      <main id="main">
        <Suspense fallback={<Loading />}>
          <Page param={rest.join('/')} />
        </Suspense>
      </main>
      <footer className="foot">
        <span>
          Developed by <strong>Reza Azad Gholami</strong>
        </span>
        <a href={REPO} target="_blank" rel="noreferrer">
          <GitHubIcon /> github.com/eigenreza/shipping-performance-analytics
        </a>
        <span className="foot-data">
          Data: EU MRV (EMSA), Kystverket AIS (NLOD), weather by <a href="https://open-meteo.com" target="_blank" rel="noreferrer">Open-Meteo.com</a> (CC BY 4.0), carbon price by Ember (CC BY 4.0). Ships are shown under pseudonyms.
        </span>
      </footer>
      <Tour open={tour.open} onClose={tour.close} />
    </>
  )
}
