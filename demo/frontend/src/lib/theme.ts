// Colors by the role they play. Data colors come from a palette validated for
// color-vision deficiency; navy is used only for page chrome, never for data.
export const SEGMENT_COLOR: Record<string, string> = {
  'Vehicle carrier': '#eb6834',
  'Ro-ro ship': '#2a78d6',
}

// CII rating A (best) to E (worst): diverging blue, neutral gray, red.
export const RATING_COLOR: Record<string, string> = {
  A: '#1c5cab',
  B: '#86b6ef',
  C: '#c9c8c3',
  D: '#f0a09f',
  E: '#d03b3b',
}

export const INK = {
  primary: '#0b0b0b',
  secondary: '#52514e',
  muted: '#7a7975',
  grid: '#e7e6e1',
  surface: '#fcfcfb',
  chrome: '#1F4E79',
}

export const FONT = "'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
