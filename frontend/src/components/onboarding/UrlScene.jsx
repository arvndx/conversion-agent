import { useState } from 'react'
import PilotAction from '../pilot/PilotAction.jsx'
import SearchPanel from './SearchPanel.jsx'
import { hostOf, iconFor, pluralize } from './sourceMeta.js'

// "I know another page": a typed address with a label from the category's list.
export function ManualAdder({ labels, busy, onAdd, trigger = 'ob-link' }) {
  const [open, setOpen] = useState(false)
  const [url, setUrl] = useState('')
  const [label, setLabel] = useState('')
  if (!open) {
    return <button className={trigger} onClick={() => setOpen(true)}>＋ Add a webpage manually</button>
  }
  async function submit(e) {
    e.preventDefault()
    if (!url.trim()) return
    const result = await onAdd(url.trim(), label || undefined)
    if (result) { setUrl(''); setLabel(''); setOpen(false) }
  }
  return (
    <form onSubmit={submit} className="ob-source" style={{ display: 'grid', gap: 10, textAlign: 'left' }}>
      <input className="claim-input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.facebook.com/yourpage" aria-label="Web address" disabled={busy} autoFocus />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <select className="ob-select" value={label} onChange={(e) => setLabel(e.target.value)} aria-label="What kind of page is this?" disabled={busy}>
          <option value="">What is this page?</option>
          {labels.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        <button type="submit" className="claim-btn-primary ob-btn" disabled={busy || !url.trim()}>Add</button>
        <button type="button" className="ob-link" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  )
}

// One page, one question: is this you? The next page appears when this one is answered.
function PageQuestion({ source, index, total, busy, onDecide }) {
  const confident = (source.confidence ?? 0) >= 60
  const name = source.title && source.title !== source.host ? source.title : source.host
  return (
    <div className="ob-focus pilot-rise" key={source.id}>
      <div className="ob-focus__count">Page {index} of {total}</div>
      <span className="ob-focus__icon">{iconFor(source.platform)}</span>
      <h2 className="ob-focus__title">{name}</h2>
      <a className="ob-focus__sub" href={source.url} target="_blank" rel="noreferrer">{hostOf(source.url)} ↗</a>
      {source.confidence != null && (
        <span className={`ob-chip ${confident ? 'ob-chip--ok' : 'ob-chip--warn'}`}>{source.confidence}% match</span>
      )}
      <div className="ob-focus__q">Is this your page?</div>
      <div className="ob-focus__actions">
        <button className="claim-btn-primary ob-btn ob-btn--lg" disabled={busy} onClick={() => onDecide(source.id, 'confirm', source.label || undefined)}>Yes, this is mine</button>
        <button className="claim-btn-secondary ob-btn ob-btn--lg" disabled={busy} onClick={() => onDecide(source.id, 'deny')}>Not mine</button>
      </div>
    </div>
  )
}

// Stage 1: which of the web addresses we hold (or the agent found) really are the person's, one at a time.
// Reading starts by itself when every page is answered (only confirmed pages are ever read); this screen is what
// remains when nothing is confirmed: search for pages, or add one by hand.
function UrlScene({ data, busy, agentBusy, searching, readFailed, onDecide, onAdd, onRetry, onSearch }) {
  const proposed = data.sources.filter((s) => s.status === 'proposed')
  const confirmed = data.sources.filter((s) => s.status === 'confirmed')
  const answered = data.sources.filter((s) => ['confirmed', 'denied'].includes(s.status)).length
  const locked = busy || agentBusy

  if (proposed.length > 0 && !searching) {
    return <PageQuestion source={proposed[0]} index={answered + 1} total={answered + proposed.length} busy={locked} onDecide={onDecide} />
  }

  return (
    <div className="ob-focus pilot-rise">
      {searching ? (
        <SearchPanel data={data} found={proposed.length} />
      ) : (
        <>
          <span className="ob-focus__icon">{readFailed && confirmed.length > 0 ? '⚠️' : '🔎'}</span>
          <h2 className="ob-focus__title">{readFailed && confirmed.length > 0 ? "I couldn't start reading" : 'No pages confirmed yet'}</h2>
          <div className="ob-focus__sub">
            {readFailed && confirmed.length > 0
              ? `${pluralize(confirmed.length, 'page')} confirmed. Try again, or look for more.`
              : 'I can search the web for your pages, or you can add the ones you know.'}
          </div>
          <div className="ob-focus__actions ob-focus__actions--col">
            {readFailed && confirmed.length > 0 && <PilotAction disabled={locked} onClick={onRetry}>Try reading again →</PilotAction>}
            <PilotAction variant={readFailed && confirmed.length > 0 ? 'quiet' : 'primary'} disabled={locked} onClick={onSearch}>🔎 Looking for more details from the internet</PilotAction>
          </div>
          <ManualAdder labels={data.url_labels} busy={locked} onAdd={onAdd} />
        </>
      )}
    </div>
  )
}

export default UrlScene
