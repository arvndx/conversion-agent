import { useEffect, useRef, useState } from 'react'
import PilotOrb from './PilotOrb.jsx'
import AgentMessageBubble from '../agent/AgentMessageBubble.jsx'
import TypingIndicator from '../agent/TypingIndicator.jsx'

// The assistant's conversation, docked on the right of the page. Suggestion pills sit above the
// input until the user has said something. (On narrow screens the panel stacks under the page.)
function PilotChatPanel({ messages, sending, onSend, suggestions = [], placeholder = 'Ask me anything…', emptyText = 'Ask me anything along the way.' }) {
  const [draft, setDraft] = useState('')
  const listRef = useRef(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, sending])

  function send(text) {
    const value = text.trim()
    if (!value || sending) return
    onSend(value)
    setDraft('')
  }

  // The agent also replies to card clicks and field requests behind the scenes; only count it as
  // a conversation once the user has actually typed something.
  const userHasChatted = messages.some((m) => m.role === 'user')

  return (
    <aside className="pilot-side">
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <PilotOrb size={26} animate={false} />
        <span style={{ fontWeight: 800, fontSize: 14 }}>Profile Pilot</span>
      </div>

      <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '18px 16px' }}>
        {messages.length === 0 && !sending && (
          <div style={{ fontSize: 13, color: 'var(--ink-soft)', lineHeight: 1.5 }}>
            {emptyText}
          </div>
        )}
        {messages.map((m, i) => (
          <AgentMessageBubble key={i} role={m.role} text={m.text} />
        ))}
        {sending && <TypingIndicator />}
      </div>

      {!userHasChatted && suggestions.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '0 14px 10px' }}>
          {suggestions.map((s) => (
            <button key={s} type="button" className="pilot-chip" style={{ fontSize: 11.5, padding: '5px 11px' }} onClick={() => send(s)} disabled={sending}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send(draft)
        }}
        style={{ display: 'flex', gap: 8, padding: 14, borderTop: '1px solid var(--border)', flexShrink: 0 }}
      >
        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={placeholder} className="agent-input" style={{ flex: 1, minWidth: 0 }} />
        <button type="submit" disabled={sending || !draft.trim()} aria-label="Send" className="agent-send-btn">
          →
        </button>
      </form>
    </aside>
  )
}

export default PilotChatPanel
