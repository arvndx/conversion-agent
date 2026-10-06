import { useState } from 'react'
import PilotOrb from '../pilot/PilotOrb.jsx'
import SearchPanel, { useRotating } from './SearchPanel.jsx'
import { ManualAdder } from './UrlScene.jsx'
import { iconFor, pluralize } from './sourceMeta.js'

const READ_STATUSES = ['scraping', 'done', 'blocked', 'failed', 'needs_identity']
const FINISHED = ['done', 'blocked', 'failed', 'needs_identity']

// What each page is doing right now, in words, so the wait shows real progress.
const PHASE = {
  queued: 'Waiting for its turn…',
  opening: 'Opening the page…',
  reading: 'Reading what is on it…',
  extracting: 'Picking out your details…',
}

// Friendly lines that rotate under the headline; later ones take over as more pages finish.
const LINES = {
  early: ['Opening your pages, all at the same time to keep this quick.', 'Sit tight, I am doing the typing for you.', 'Checking each page really is yours…'],
  mid: ['Pulling out your phone, address and hours…', 'Comparing what each page says about you…', 'Nice, your details are coming in.'],
  late: ['Almost there…', 'Just the last page to go…', 'Putting the finishing touches together…'],
}

// One line per page: its stage while it is being read, then a few of the details it gave (a compact row, so the
// board fits the screen without scrolling). The arrow opens everything that was found on the page.
function Row({ s, roomy }) {
  const [open, setOpen] = useState(false)
  const working = s.status === 'scraping' || s.status === 'confirmed'
  const state = working ? 'busy' : s.status === 'done' ? 'ok' : s.status === 'needs_identity' ? 'warn' : 'bad'
  const chips = (s.highlights || []).slice(0, roomy ? 3 : 2)
  const details = s.details || []
  return (
    <div className={`rd-item rd-item--${state} pilot-rise`}>
      <div className={`rd-row rd-row--${state}`}>
        <span className="rd-row__icon">{iconFor(s.platform)}</span>
        <div className="rd-row__main">
          <div className="rd-row__host">{s.host}</div>
          {working && <div className="rd-row__sub" key={s.phase}>{s.status === 'confirmed' ? 'Getting started…' : PHASE[s.phase] || PHASE.queued}</div>}
          {s.status === 'done' && (
            chips.length > 0 ? (
              <div className="rd-row__chips">{chips.map((h, i) => <span key={h.key} className="rd-pill" style={{ animationDelay: `${i * 70}ms` }} title={h.value}><b>{h.label}</b> {h.value}</span>)}</div>
            ) : <div className="rd-row__sub">Nothing new on this page</div>
          )}
          {(s.status === 'blocked' || s.status === 'failed') && <div className="rd-row__sub">Doesn&apos;t let us read it, so your link is saved and I moved on</div>}
          {s.status === 'needs_identity' && <div className="rd-row__sub">Your name wasn&apos;t on it, I&apos;ll ask you in a moment</div>}
        </div>
        <span className={`ob-chip ob-chip--${state}`}>
          {working && <span className="ob-spinner" />}
          {working ? (s.status === 'confirmed' ? 'Starting' : 'Reading') : s.status === 'done' ? '✓ Read' : s.status === 'needs_identity' ? 'Check' : 'Skipped'}
        </span>
        {s.status === 'done' && details.length > 0 && (
          <button className={`rd-toggle${open ? ' rd-toggle--open' : ''}`} aria-expanded={open} aria-label={`What we found on ${s.host}`} onClick={() => setOpen(!open)}>▾</button>
        )}
      </div>
      {open && (
        <dl className="rd-details">
          {details.map((d) => (
            <div key={d.key}><dt>{d.label}</dt><dd>{d.value}</dd></div>
          ))}
        </dl>
      )}
    </div>
  )
}

// The reading board: shown only when nothing is waiting on the owner. Progress and what each page gave.
function ReadingScene({ data, agentBusy, searching, finishing, onSearch, onAdd }) {
  // Pages the owner just said yes to show as "starting" while the agent kicks off the reading (a few seconds).
  const rows = data.sources.filter((s) => READ_STATUSES.includes(s.status) || s.status === 'confirmed')
  const done = rows.filter((s) => FINISHED.includes(s.status)).length
  const open = rows.length - done
  const pct = rows.length ? done / rows.length : 0
  const subline = useRotating(pct < 0.4 ? LINES.early : pct < 0.75 ? LINES.mid : LINES.late)

  let headline = open > 0 ? `Reading ${pluralize(rows.length, 'page')} at the same time…` : 'Pages read, putting it all together…'
  if (finishing) headline = 'Finishing your profile…'
  else if (open === 0 && data.stage === 'merge') headline = 'Putting together what I found…'

  return (
    <div className="ob-board">
      <div className="rd-hero pilot-rise">
        <div className="rd-hero__top">
          <PilotOrb size={32} />
          <div style={{ minWidth: 0 }}>
            <div className="rd-hero__title">{headline}</div>
            <div className="rd-hero__sub" key={subline}>{finishing ? 'Almost done, saving everything now.' : subline}</div>
          </div>
          {rows.length > 0 && <span className="rd-hero__count">{done}/{rows.length}</span>}
        </div>
        {rows.length > 0 && <div className="rd-bar"><i style={{ width: `${Math.max(Math.round(pct * 100), 6)}%` }} /></div>}
      </div>

      {searching && <SearchPanel data={data} />}
      <div className="rd-rows">{rows.map((s) => <Row key={s.id} s={s} roomy={rows.length <= 4 && !searching} />)}</div>

      {!finishing && (
        <div className="rd-actions">
          <button className="btn btn--ghost btn--sm" disabled={searching || agentBusy} onClick={onSearch}>🔎 Looking for more details from the internet</button>
          <ManualAdder labels={data.url_labels} busy={searching} onAdd={onAdd} trigger="btn btn--ghost btn--sm" />
        </div>
      )}
    </div>
  )
}

export default ReadingScene
