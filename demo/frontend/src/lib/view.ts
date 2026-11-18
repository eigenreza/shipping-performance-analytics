// Simple or Detailed view, chosen once in the header and remembered on every page.
import { useEffect, useState } from 'react'

const KEY = 'spa-view'
const EVENT = 'spa-view-change'

export function getDetailed() {
  return localStorage.getItem(KEY) === 'detailed'
}

export function setDetailed(on: boolean) {
  localStorage.setItem(KEY, on ? 'detailed' : 'simple')
  window.dispatchEvent(new Event(EVENT))
}

export function useDetailed() {
  const [detailed, set] = useState(getDetailed)
  useEffect(() => {
    const on = () => set(getDetailed())
    window.addEventListener(EVENT, on)
    window.addEventListener('storage', on)
    return () => {
      window.removeEventListener(EVENT, on)
      window.removeEventListener('storage', on)
    }
  }, [])
  return detailed
}
