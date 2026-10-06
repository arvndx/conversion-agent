import { useCallback, useEffect, useRef, useState } from 'react'

// How long a finished line is held before the next one replaces it. Shorter than a staged demo
// would use — this is a real task flow — and any line can be skipped by clicking the card.
export const PILOT_HOLD_MS = 650

// Drives a sequence of typed lines: types line N, holds, moves to N+1. `done` flips true as soon
// as the last line has finished typing (so the controls under it can appear immediately).
export function usePilotScript(lines, { paused = false, onDone } = {}) {
  const key = lines.join('\u0001')
  const [index, setIndex] = useState(0)
  const [typing, setTyping] = useState(true)
  const [done, setDone] = useState(false)
  const doneRef = useRef(onDone)
  doneRef.current = onDone

  // A different set of lines is a new script.
  useEffect(() => {
    setIndex(0)
    setTyping(true)
    setDone(false)
  }, [key])

  useEffect(() => {
    setTyping(true)
  }, [index])

  const settle = useCallback(() => setTyping(false), [])

  useEffect(() => {
    if (typing || paused || lines.length === 0) return undefined
    const last = lines.length - 1
    if (index >= last) {
      if (!done) {
        setDone(true)
        doneRef.current?.()
      }
      return undefined
    }
    const timer = setTimeout(() => setIndex((i) => Math.min(i + 1, last)), PILOT_HOLD_MS)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typing, paused, index, key, done])

  return { index, line: lines[Math.min(index, Math.max(lines.length - 1, 0))] ?? '', typing, done, settle, total: lines.length }
}
