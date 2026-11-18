import { useEffect, useLayoutEffect, useState } from 'react'

type Step = { target: string; title: string; text: string }

const STEPS: Step[] = [
  {
    target: 'answer',
    title: 'One question, one answer',
    text: 'Should ships sail slower? The answer at the top comes from public EU emission reports of vehicle carriers and ro-ro ships. The curve shows the net gain at every speed.',
  },
  {
    target: 'sliders',
    title: 'Move the two sliders',
    text: 'Speed changes how fast the ships sail. The cost of a day at sea decides whether slowing down pays, so try your own figure. The answer and the curve update at once.',
  },
  {
    target: 'view',
    title: 'Simple or detailed',
    text: 'Simple shows the answer and the main chart. Detailed adds every setting, number and table, here and on the Fleet, Ratings, Ports and Ships pages. Your choice is remembered.',
  },
  {
    target: 'help',
    title: 'Come back any time',
    text: 'The "?" button replays this tour. The tabs at the top lead to the fleet, ratings, ports and single ships.',
  },
]

const KEY = 'spa-tour-v6-done'

export function useTour() {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!localStorage.getItem(KEY)) setOpen(true)
  }, [])
  return { open, start: () => setOpen(true), close: () => { localStorage.setItem(KEY, '1'); setOpen(false) } }
}

export default function Tour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [i, setI] = useState(0)
  const [box, setBox] = useState<DOMRect | null>(null)

  useLayoutEffect(() => {
    if (!open) return
    const el = document.querySelector(`[data-tour="${STEPS[i].target}"]`)
    if (el) {
      el.scrollIntoView({ block: 'nearest' })
      setBox(el.getBoundingClientRect())
    } else setBox(null)
  }, [open, i])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight') setI((x) => Math.min(x + 1, STEPS.length - 1))
      if (e.key === 'ArrowLeft') setI((x) => Math.max(x - 1, 0))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (open) setI(0)
  }, [open])

  if (!open) return null
  const step = STEPS[i]
  const pad = 6
  // Tall targets (a settings panel) get the card beside them, so the card never covers what it points at.
  const beside = box !== null && box.height > window.innerHeight * 0.45 && box.right + 364 < window.innerWidth
  const top = box ? (beside ? Math.max(12, Math.min(box.top, window.innerHeight - 240)) : Math.min(box.bottom + 12, window.innerHeight - 220)) : window.innerHeight / 2 - 100
  const left = box ? (beside ? box.right + 16 : Math.max(12, Math.min(box.left, window.innerWidth - 352))) : window.innerWidth / 2 - 170
  return (
    <div className="tour" role="dialog" aria-modal="true" aria-label="Guided tour">
      {box && (
        <div
          className="tour-hole"
          style={{ top: box.top - pad, left: box.left - pad, width: box.width + pad * 2, height: box.height + pad * 2 }}
        />
      )}
      <div className="tour-card" style={{ top, left }}>
        <div className="tour-step">
          Step {i + 1} of {STEPS.length}
        </div>
        <h3>{step.title}</h3>
        <p>{step.text}</p>
        <div className="tour-actions">
          <button type="button" className="link" onClick={onClose}>
            Skip tour
          </button>
          <span>
            {i > 0 && (
              <button type="button" className="secondary" onClick={() => setI(i - 1)}>
                Back
              </button>
            )}
            {i < STEPS.length - 1 ? (
              <button type="button" className="primary" onClick={() => setI(i + 1)} autoFocus>
                Next
              </button>
            ) : (
              <button type="button" className="primary" onClick={onClose} autoFocus>
                Start exploring
              </button>
            )}
          </span>
        </div>
      </div>
    </div>
  )
}
