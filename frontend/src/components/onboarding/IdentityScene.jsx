import { useState } from 'react'
import { iconFor } from './sourceMeta.js'

// A page that did not show the person's name, one at a time. Its details stay unused until they say it is theirs.
function IdentityScene({ data, busy, agentBusy, onAnswer }) {
  const [working, setWorking] = useState(null) // the page being confirmed (the read after "yes" takes a few seconds)
  const waiting = data.sources.filter((s) => s.status === 'needs_identity')
  const source = waiting[0]
  if (!source) return null
  const locked = busy || agentBusy || working !== null

  async function answer(isMine) {
    setWorking(source.id)
    await onAnswer(source.id, isMine)
    setWorking(null)
  }

  return (
    <div className="ob-focus pilot-rise" key={source.id}>
      {waiting.length > 1 && <div className="ob-focus__count">1 of {waiting.length}</div>}
      <span className="ob-focus__icon">{iconFor(source.platform)}</span>
      <h2 className="ob-focus__title">Is this you?</h2>
      <div className="ob-focus__sub">{source.host} — I couldn&apos;t find <strong>{data.profile.name}</strong> on it.</div>
      {source.preview && <blockquote className="ob-quote">{source.preview}</blockquote>}
      <div className="ob-focus__actions">
        <button className="claim-btn-primary ob-btn ob-btn--lg" disabled={locked} onClick={() => answer(true)}>Yes, this is my page</button>
        <button className="claim-btn-secondary ob-btn ob-btn--lg" disabled={locked} onClick={() => answer(false)}>No, not mine</button>
      </div>
      {working !== null && <div className="ob-hint">Reading that page…</div>}
    </div>
  )
}

export default IdentityScene
