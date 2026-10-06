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
  if (parseFloat(getComputedStyle(el).borderTopLeftRadius) === 0) el.style.borderRadius = '8px'
  setTimeout(() => {
    el.style.boxShadow = 'none'
  }, 1400)
}

function PointBadge({ points }) {
  return <div className="suggest__badge">+{points} pts</div>
}

export function SuggestionCard({ points, children, actionLabel, onAction }) {
  return (
    <div className="suggest">
      <PointBadge points={points} />
      <div className="suggest__kicker">💡 Quick win</div>
      <div className="suggest__text">{children}</div>
      <div>
        <button onClick={onAction} className="btn btn--primary btn--sm">{actionLabel}</button>
      </div>
    </div>
  )
}

export function ReviewSuggestionCard({ items, onReply }) {
  const [index, setIndex] = useState(0)
  const item = items[Math.min(index, items.length - 1)]
  if (!item) return null

  return (
    <div className="suggest">
      <PointBadge points={item.points} />
      <div className="suggest__kicker">Unreplied review {items.length > 1 ? `(${index + 1} of ${items.length})` : ''}</div>
      <div className="suggest__text">
        <strong>{item.reviewer_name}</strong> — "{item.review_body}"
      </div>
      <div className="suggest__actions">
        {items.length > 1 ? (
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={() => setIndex((i) => (i - 1 + items.length) % items.length)} className="btn btn--ghost btn--sm" aria-label="Previous suggestion">←</button>
            <button onClick={() => setIndex((i) => (i + 1) % items.length)} className="btn btn--ghost btn--sm" aria-label="Next suggestion">→</button>
          </div>
        ) : (
          <span />
        )}
        <button onClick={() => onReply(item.review_id)} className="btn btn--primary btn--sm">Reply</button>
      </div>
    </div>
  )
}
