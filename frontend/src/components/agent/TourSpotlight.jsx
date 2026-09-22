import { useEffect, useLayoutEffect, useRef, useState } from 'react'

const AUTO_FADE_MS = 6000
const PADDING = 8
const FIND_POLL_MS = 200
const FIND_TIMEOUT_MS = 4000 // covers a cross-page tour navigation's async data fetch before the target renders
const CALLOUT_WIDTH = 300
const VIEWPORT_MARGIN = 12

const STEP_ICONS = {
  overview: '🎯',
  reviews: '💬',
  profile_completion: '👤',
  connections: '🔗',
  web_analytics: '🌐',
  listings: '📍',
  wrap_up: '🏆',
}

// A dimmed backdrop with a cutout around the target element, plus either a small pointer
// label (ad-hoc highlight_ui) or a full anchored tour callout (guided tour) — used for
// every highlight so both feel like one consistent system.
function TourSpotlight({ target, reason, tourStep, doubtOpen, onNext, onEnd, onDone }) {
  const [rect, setRect] = useState(null)
  const calloutRef = useRef(null)
  const [calloutHeight, setCalloutHeight] = useState(0)

  useEffect(() => {
    if (!target) return
    setRect(null)

    let el = null
    let resizeObserver = null
    let measureTimer = null
    let fadeTimer = null
    let pollTimer = null
    const deadline = Date.now() + FIND_TIMEOUT_MS

    function measure() {
      if (!el) return
      const r = el.getBoundingClientRect()
      setRect({ top: r.top - PADDING, left: r.left - PADDING, width: r.width + PADDING * 2, height: r.height + PADDING * 2 })
    }

    function tryFind() {
      el = document.querySelector(`[data-agent-target="${target}"]`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        measureTimer = setTimeout(measure, 350)
        window.addEventListener('resize', measure)
        window.addEventListener('scroll', measure, true)
        // Re-measure whenever the highlighted element's own size changes — e.g. a
        // suggestion card loading in asynchronously and growing its section — not just
        // on window resize/scroll, so the ring never goes stale relative to real content.
        if (typeof ResizeObserver !== 'undefined') {
          resizeObserver = new ResizeObserver(measure)
          resizeObserver.observe(el)
        }
        // A tour step waits for the user (Next/End); an ad-hoc highlight fades on its own.
        if (!tourStep) fadeTimer = setTimeout(() => onDone?.(), AUTO_FADE_MS)
        return
      }
      if (Date.now() < deadline) {
        pollTimer = setTimeout(tryFind, FIND_POLL_MS)
      } else {
        onDone?.() // navigated page never rendered this target — give up quietly
      }
    }
    tryFind()

    return () => {
      clearTimeout(measureTimer)
      clearTimeout(fadeTimer)
      clearTimeout(pollTimer)
      resizeObserver?.disconnect()
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, Boolean(tourStep)])

  // Measures the callout's own real rendered height (text length varies) so placement can
  // be clamped precisely, instead of guessing with a fixed threshold that broke for longer text.
  useLayoutEffect(() => {
    if (calloutRef.current) setCalloutHeight(calloutRef.current.offsetHeight)
  })

  if (!target || !rect) return null

  const calloutLeft = Math.max(VIEWPORT_MARGIN, Math.min(rect.left, window.innerWidth - CALLOUT_WIDTH - VIEWPORT_MARGIN))
  const spaceBelow = window.innerHeight - (rect.top + rect.height)
  const spaceAbove = rect.top
  const neededSpace = (calloutHeight || 160) + 14
  const placeAbove = tourStep && spaceBelow < neededSpace && spaceAbove > spaceBelow
  // Clamp so the callout never runs off the top or bottom edge even when neither side has
  // quite enough room (a very short viewport, or a target near the very top/bottom).
  const calloutTop = placeAbove
    ? Math.max(VIEWPORT_MARGIN, rect.top - 14 - calloutHeight)
    : Math.min(rect.top + rect.height + 14, window.innerHeight - calloutHeight - VIEWPORT_MARGIN)

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 900, pointerEvents: 'none' }}>
      {/* Dimmed backdrop with a transparent cutout, built from 4 rectangles around the target */}
      <div style={{ position: 'fixed', top: 0, left: 0, right: 0, height: rect.top, background: 'rgba(15, 15, 20, 0.35)' }} />
      <div
        style={{
          position: 'fixed',
          top: rect.top,
          left: 0,
          width: rect.left,
          height: rect.height,
          background: 'rgba(15, 15, 20, 0.35)',
        }}
      />
      <div
        style={{
          position: 'fixed',
          top: rect.top,
          left: rect.left + rect.width,
          right: 0,
          height: rect.height,
          background: 'rgba(15, 15, 20, 0.35)',
        }}
      />
      <div
        style={{
          position: 'fixed',
          top: rect.top + rect.height,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(15, 15, 20, 0.35)',
        }}
      />
      {/* The spotlight ring itself */}
      <div
        style={{
          position: 'fixed',
          top: rect.top,
          left: rect.left,
          width: rect.width,
          height: rect.height,
          borderRadius: 10,
          boxShadow: '0 0 0 3px var(--brand), 0 0 24px 4px rgba(99, 91, 255, 0.5)',
          transition: 'top 0.2s ease, left 0.2s ease, width 0.2s ease, height 0.2s ease',
        }}
      />

      {tourStep ? (
        <div
          ref={calloutRef}
          style={{
            position: 'fixed',
            top: calloutTop,
            left: calloutLeft,
            width: CALLOUT_WIDTH,
            background: '#fff',
            borderRadius: 16,
            boxShadow: '0 20px 50px rgba(16,24,40,0.32), 0 0 0 1px rgba(124,92,255,0.12)',
            padding: '16px 18px',
            pointerEvents: 'auto',
            animation: 'agent-popup-in 0.2s ease',
          }}
        >
          {/* Pointer triangle toward the highlighted element */}
          <div
            style={{
              position: 'absolute',
              [placeAbove ? 'bottom' : 'top']: -7,
              left: Math.max(16, Math.min(rect.left + rect.width / 2 - calloutLeft, CALLOUT_WIDTH - 16)),
              width: 14,
              height: 14,
              background: '#fff',
              transform: 'rotate(45deg)',
              boxShadow: placeAbove ? '4px 4px 6px rgba(16,24,40,0.06)' : '-2px -2px 4px rgba(16,24,40,0.04)',
            }}
          />

          <div style={{ display: 'flex', gap: 4, marginBottom: 14 }}>
            {Array.from({ length: tourStep.totalSteps }, (_, i) => i + 1).map((n) => (
              <div
                key={n}
                style={{
                  flex: 1,
                  height: 5,
                  borderRadius: 999,
                  background: n <= tourStep.stepNumber ? 'linear-gradient(90deg, #7c5cff, var(--brand))' : 'var(--surface-muted)',
                  boxShadow: n === tourStep.stepNumber ? '0 0 8px rgba(124,92,255,0.6)' : 'none',
                  transition: 'background 0.2s ease',
                }}
              />
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <div
              style={{
                width: 34,
                height: 34,
                flexShrink: 0,
                borderRadius: 10,
                background: 'linear-gradient(135deg, #7c5cff, var(--brand))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 17,
                boxShadow: '0 4px 12px rgba(99,91,255,0.35)',
              }}
            >
              {STEP_ICONS[tourStep.id] || '✨'}
            </div>
            <div>
              <div style={{ fontSize: 9.5, fontWeight: 700, color: 'var(--ink-soft)', letterSpacing: 0.5 }}>
                STEP {tourStep.stepNumber} OF {tourStep.totalSteps}
              </div>
              <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--ink)', letterSpacing: 0.1 }}>{tourStep.title}</div>
            </div>
          </div>

          <div style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--ink)', marginBottom: 16, fontWeight: 500 }}>{tourStep.text}</div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button
              onClick={onEnd}
              style={{ background: 'none', border: 'none', color: 'var(--ink-soft)', fontSize: 12, fontWeight: 600, cursor: 'pointer', padding: 0 }}
            >
              End tour
            </button>
            <button
              onClick={onNext}
              disabled={doubtOpen}
              title={doubtOpen ? "Let's clear up your question first" : undefined}
              className="agent-btn-primary"
              style={{ padding: '8px 18px', fontSize: 13 }}
            >
              {doubtOpen ? 'Resolve first…' : tourStep.stepNumber === tourStep.totalSteps ? 'Finish ✓' : 'Next →'}
            </button>
          </div>
        </div>
      ) : (
        reason && (
          <div
            style={{
              position: 'fixed',
              top: rect.top + rect.height + 10,
              left: Math.max(12, Math.min(rect.left, window.innerWidth - 260)),
              maxWidth: 240,
              background: 'var(--brand)',
              color: '#fff',
              fontSize: 12,
              fontWeight: 600,
              padding: '6px 10px',
              borderRadius: 8,
              boxShadow: '0 6px 16px rgba(0,0,0,0.25)',
            }}
          >
            {reason}
          </div>
        )
      )}
    </div>
  )
}

export default TourSpotlight
