import { useState } from 'react'
import PlatformIcon from '../shared/PlatformIcon.jsx'

// One never-read platform (LinkedIn, Instagram, X): we do not open these pages, so the owner gives the link
// (or confirms the one we found) and it counts toward Connections once saved.
function LinkRow({ item, disabled, onSave }) {
  const saved = item.url || ''
  const [text, setText] = useState(saved)
  const [seen, setSeen] = useState(saved)
  const [phase, setPhase] = useState('idle') // idle | saving | failed
  if (saved !== seen) {
    setSeen(saved)
    setText(saved)
  }
  const changed = text.trim() !== saved.trim()
  const found = item.confirmed === false && saved && !changed // a link we hold, waiting for the owner's yes
  const canSave = changed || found

  async function save() {
    setPhase('saving')
    const next = await onSave(item.platform, text.trim())
    setPhase(next ? 'idle' : 'failed')
  }

  return (
    <div className={`sl-row${item.confirmed ? ' sl-row--on' : found ? ' sl-row--found' : ''}`} data-platform={item.platform}>
      <PlatformIcon name={item.label} />
      <div className="sl-main">
        <div className="sl-top">
          <b>{item.label}</b>
          <span className={`sl-state${item.confirmed ? ' sl-state--on' : ''}`}>
            {item.confirmed ? '✓ Counts toward Connections' : found ? 'Found on your pages — is this yours?' : 'Paste your profile link'}
          </span>
        </div>
        <input
          className="sl-input" value={text} disabled={disabled}
          placeholder={`https://${item.platform === 'x' ? 'x.com' : `${item.platform}.com`}/your-profile`} aria-label={`${item.label} link`}
          onChange={(e) => { setText(e.target.value); setPhase('idle') }}
          onKeyDown={(e) => e.key === 'Enter' && canSave && !disabled && save()}
        />
        {phase === 'failed' && <div className="pf-error">That doesn&apos;t look like a {item.label} profile address.</div>}
      </div>
      {canSave && (
        <button className="btn btn--primary btn--sm" disabled={disabled || phase === 'saving'} onClick={save}>
          {phase === 'saving' ? 'Saving…' : found ? 'Yes, mine' : 'Save'}
        </button>
      )}
    </div>
  )
}

function SocialLinks({ items, disabled, onSave, title = 'Your social links' }) {
  if (!items?.length) return null
  const open = items.filter((i) => !i.confirmed).length
  return (
    <section className="sl-card pilot-rise">
      <div className="sl-head">
        <span className="sl-head__icon" aria-hidden="true">🔗</span>
        <div>
          <div className="sl-head__title">{title}</div>
          <div className="ob-hint">
            {open > 0
              ? "We don't open these sites, so confirm the links yourself. Each one counts toward your Connections score."
              : 'All set — these links count toward your Connections score.'}
          </div>
        </div>
      </div>
      <div className="sl-list">{items.map((item) => <LinkRow key={item.platform} item={item} disabled={disabled} onSave={onSave} />)}</div>
    </section>
  )
}

export default SocialLinks
