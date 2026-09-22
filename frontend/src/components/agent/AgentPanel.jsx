import { useEffect, useRef, useState } from 'react'
import AgentMessageBubble from './AgentMessageBubble.jsx'
import TypingIndicator from './TypingIndicator.jsx'

const QUICK_REPLIES_BY_PREFIX = [
  {
    prefix: '/dashboard/',
    replies: [
      'Take me on a full tour',
      'Why is my score low?',
      'What does Pro unlock?',
      'Help me reply to a review',
      'Are there Pro spots left?',
    ],
  },
  { prefix: '/profile/', replies: ['Why is my score low?', 'Is this profile Pro?'] },
]

function quickRepliesFor(route) {
  const match = QUICK_REPLIES_BY_PREFIX.find((entry) => route?.startsWith(entry.prefix))
  return match?.replies ?? []
}

function TourOfferMessage({ resolved, onSure, onNotNow }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
      <div
        style={{
          maxWidth: '90%',
          background: 'linear-gradient(135deg, #f8f6ff, #f0edff)',
          border: '1.5px solid #e0d9ff',
          color: 'var(--ink)',
          borderRadius: 14,
          borderBottomLeftRadius: 3,
          padding: '12px 14px',
        }}
      >
        <div style={{ marginBottom: resolved ? 0 : 10, fontSize: 13.5, lineHeight: 1.5 }}>🧭 Can I take you on a quick product tour?</div>
        {!resolved && (
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onSure} className="agent-btn-primary" style={{ padding: '6px 14px', fontSize: 12.5 }}>
              Sure
            </button>
            <button onClick={onNotNow} className="agent-btn-secondary" style={{ padding: '6px 14px', fontSize: 12.5 }}>
              Not now
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function AgentPanel({
  messages,
  sending,
  onSend,
  route,
  tourProgress,
  onTourOfferSure,
  onTourOfferNotNow,
  onStartTour,
  preparingTour,
}) {
  const [draft, setDraft] = useState('')
  const listRef = useRef(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, sending])

  function submit(text) {
    const value = (text ?? draft).trim()
    if (!value || sending) return
    onSend(value)
    setDraft('')
  }

  // Gated on the user's OWN messages, not the total count — the proactive greeting adds
  // an assistant message before the user has typed anything, and that used to hide these
  // chips (including the tour entry point) before the user ever got a chance to see them.
  const userHasSentAnything = messages.some((m) => m.role === 'user')
  const hasUnresolvedTourOffer = messages.some((m) => m.kind === 'tour_offer' && !m.resolved)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '18px 16px' }}>
        {messages.map((m, i) => {
          if (m.kind === 'tour_offer') {
            return <TourOfferMessage key={i} resolved={m.resolved} onSure={onTourOfferSure} onNotNow={onTourOfferNotNow} />
          }
          return <AgentMessageBubble key={i} role={m.role} text={m.text} />
        })}
        {sending &&
          (preparingTour ? (
            <div style={{ fontSize: 12, color: 'var(--ink-soft)', padding: '4px 0' }}>🧭 Preparing your tour…</div>
          ) : (
            <TypingIndicator />
          ))}
      </div>

      {tourProgress && !sending && (
        <div style={{ padding: '0 16px 12px', fontSize: 11.5, color: 'var(--ink-soft)', textAlign: 'center' }}>
          🧭 Tour step {tourProgress.stepNumber}/{tourProgress.totalSteps} is shown on the page — ask me anything here too.
        </div>
      )}

      {!tourProgress && !userHasSentAnything && !sending && quickRepliesFor(route).length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, padding: '0 16px 12px' }}>
          {quickRepliesFor(route)
            // Already offered above via the tour_offer bubble's own Sure/Not-now buttons.
            .filter((q) => !(hasUnresolvedTourOffer && q === 'Take me on a full tour'))
            .map((q) => (
              <button key={q} onClick={() => (q === 'Take me on a full tour' ? onStartTour() : submit(q))} className="agent-chip">
                {q === 'Take me on a full tour' ? `🧭 ${q}` : q}
              </button>
            ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
        style={{ display: 'flex', gap: 10, padding: '14px 16px', borderTop: '1px solid var(--border)' }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask me anything…"
          className="agent-input"
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={sending || !draft.trim()} className="agent-send-btn" aria-label="Send">
          →
        </button>
      </form>
    </div>
  )
}

export default AgentPanel
