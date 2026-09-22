import { useState } from 'react'

// Scrolls to a data-agent-target element and gives it a brief glowing flash — the same
// "look here" language the tour's spotlight already uses, reused for suggestion actions
// that just need to point at an existing control rather than open a new page.
export function scrollToAndFlash(target) {
  const el = document.querySelector(`[data-agent-target="${target}"]`)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  const input = el.matches('input, textarea') ? el : el.querySelector('input, textarea')
  input?.focus()
  el.style.transition = 'box-shadow 0.2s ease'
  el.style.boxShadow = '0 0 0 3px var(--brand)'
  el.style.borderRadius = el.style.borderRadius || '8px'
  setTimeout(() => {
    el.style.boxShadow = 'none'
  }, 1400)
}

function PointBadge({ points }) {
  return (
    <div
      style={{
        position: 'absolute',
        top: -10,
        right: 16,
        background: 'linear-gradient(135deg, #16a34a, #22c55e)',
        color: '#fff',
        fontSize: 11.5,
        fontWeight: 800,
        borderRadius: 999,
        padding: '4px 11px',
        boxShadow: '0 3px 8px rgba(22,163,74,0.35)',
      }}
    >
      +{points} pts
    </div>
  )
}

export function SuggestionCard({ points, children, actionLabel, onAction }) {
  return (
    <div
      style={{
        position: 'relative',
        background: 'linear-gradient(135deg, #f8f6ff, #f0edff)',
        border: '1.5px solid #e0d9ff',
        borderRadius: 12,
        padding: '13px 15px',
        marginBottom: 16,
      }}
    >
      <PointBadge points={points} />
      <div style={{ fontSize: 13, color: 'var(--ink)', marginBottom: 10, paddingRight: 30, lineHeight: 1.45 }}>{children}</div>
      <button onClick={onAction} className="agent-btn-primary" style={{ padding: '6px 14px', fontSize: 12 }}>
        {actionLabel}
      </button>
    </div>
  )
}

export function ReviewSuggestionCard({ items, onReply }) {
  const [index, setIndex] = useState(0)
  const item = items[Math.min(index, items.length - 1)]
  if (!item) return null

  return (
    <div
      style={{
        position: 'relative',
        background: 'linear-gradient(135deg, #f8f6ff, #f0edff)',
        border: '1.5px solid #e0d9ff',
        borderRadius: 12,
        padding: '13px 15px',
        marginBottom: 16,
      }}
    >
      <PointBadge points={item.points} />
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--brand)', marginBottom: 4 }}>
        Unreplied review {items.length > 1 ? `(${index + 1} of ${items.length})` : ''}
      </div>
      <div style={{ fontSize: 13, color: 'var(--ink)', marginBottom: 10, paddingRight: 30, lineHeight: 1.45 }}>
        <strong>{item.reviewer_name}</strong> — "{item.review_body}"
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {items.length > 1 ? (
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={() => setIndex((i) => (i - 1 + items.length) % items.length)}
              className="agent-btn-secondary"
              style={{ padding: '5px 9px', fontSize: 12 }}
              aria-label="Previous suggestion"
            >
              ←
            </button>
            <button
              onClick={() => setIndex((i) => (i + 1) % items.length)}
              className="agent-btn-secondary"
              style={{ padding: '5px 9px', fontSize: 12 }}
              aria-label="Next suggestion"
            >
              →
            </button>
          </div>
        ) : (
          <span />
        )}
        <button onClick={() => onReply(item.review_id)} className="agent-btn-primary" style={{ padding: '6px 14px', fontSize: 12 }}>
          Reply
        </button>
      </div>
    </div>
  )
}
