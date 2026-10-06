import { useEffect, useRef, useState } from 'react'

// Tiny inline markup for assistant copy: **bold** and ~gradient~. Everything else is plain text.
const TOKEN_RE = /(\*\*[^*]+\*\*|~[^~]+~)/g

export function parseMarkup(text) {
  return String(text)
    .split(TOKEN_RE)
    .filter(Boolean)
    .map((part) => {
      if (part.startsWith('**')) return { text: part.slice(2, -2), kind: 'bold' }
      if (part.startsWith('~')) return { text: part.slice(1, -1), kind: 'grad' }
      return { text: part, kind: 'plain' }
    })
}

export function stripMarkup(text) {
  return parseMarkup(text)
    .map((t) => t.text)
    .join('')
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Renders the first `count` visible characters, keeping the markup intact mid-word.
function renderTokens(tokens, count) {
  let left = count
  const out = []
  tokens.forEach((t, i) => {
    if (left <= 0) return
    const shown = t.text.slice(0, left)
    left -= shown.length
    if (t.kind === 'bold') out.push(<strong key={i}>{shown}</strong>)
    else if (t.kind === 'grad') out.push(<span key={i} className="pilot-gradient-text">{shown}</span>)
    else out.push(<span key={i}>{shown}</span>)
  })
  return out
}

const MAX_TYPING_MS = 3200
const BASE_SPEED_MS = 22

// Types `text` out one character at a time. Long lines (agent-written replies) speed up so a
// line never takes more than ~3s; `complete` shows the whole line at once (skip / reduced motion).
export function PilotStream({ text, caret = true, complete = false, onDone }) {
  const tokens = parseMarkup(text)
  const total = tokens.reduce((n, t) => n + t.text.length, 0)
  const [count, setCount] = useState(0)
  const doneRef = useRef(onDone)
  doneRef.current = onDone
  const instant = complete || prefersReducedMotion()

  useEffect(() => {
    if (instant) return undefined
    setCount(0)
    const speed = Math.max(5, Math.min(BASE_SPEED_MS, MAX_TYPING_MS / Math.max(total, 1)))
    let n = 0
    const timer = setInterval(() => {
      n += 1
      setCount(n)
      if (n >= total) {
        clearInterval(timer)
        doneRef.current?.()
      }
    }, speed)
    return () => clearInterval(timer)
  }, [text, instant, total])

  useEffect(() => {
    if (instant) doneRef.current?.()
  }, [instant, text])

  const shown = instant ? total : count
  return (
    <>
      {renderTokens(tokens, shown)}
      {caret && shown < total && <span className="pilot-caret" />}
    </>
  )
}
