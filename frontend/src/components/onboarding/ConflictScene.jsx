import { useMemo, useState } from 'react'

const seenOn = (option) => (option.sources?.length ? `Seen on ${option.sources.join(', ')}` : '')

// Pick one value (title, company, website, hours, ...), or type your own. Choosing a listed value settles it at
// once; only a typed answer needs a Save, since it is not finished until the owner says so.
function PickOneCard({ conflict, label, busy, onResolve }) {
  const [typing, setTyping] = useState(false)
  const [own, setOwn] = useState('')
  const name = `c${conflict.id}`
  return (
    <>
      <div className="ob-list">
        {conflict.options.map((o, i) => (
          <label key={i} className="ob-option">
            <input type="radio" name={name} checked={false} disabled={busy} onChange={() => onResolve({ choice: i })} />
            <span><div className="ob-option__value">{o.value}</div><div className="ob-option__seen">{seenOn(o)}</div></span>
          </label>
        ))}
        <label className={`ob-option${typing ? ' ob-option--on' : ''}`}>
          <input type="radio" name={name} checked={typing} disabled={busy} onChange={() => setTyping(true)} />
          <span style={{ flex: 1 }}>
            <div className="ob-option__value">Something else</div>
            {typing && (
              <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                <input
                  className="claim-input" style={{ flex: '1 1 200px', width: 'auto' }} autoFocus value={own} onChange={(e) => setOwn(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && own.trim() && !busy && onResolve({ value: own.trim() })}
                  placeholder={`Type your ${label.toLowerCase()}`}
                />
                <button className="claim-btn-primary ob-btn" disabled={busy || !own.trim()} onClick={() => onResolve({ value: own.trim() })}>Save</button>
              </div>
            )}
          </span>
        </label>
      </div>
    </>
  )
}

// More than one license can be real, so each can be kept, and one can be typed in.
function LicenseCard({ conflict, busy, onResolve }) {
  const [keep, setKeep] = useState([])
  const [manual, setManual] = useState('')
  const toggle = (i) => setKeep((k) => (k.includes(i) ? k.filter((x) => x !== i) : [...k, i]))
  return (
    <>
      <div className="ob-list">
        {conflict.options.map((o, i) => (
          <label key={i} className={`ob-option${keep.includes(i) ? ' ob-option--on' : ''}`}>
            <input type="checkbox" checked={keep.includes(i)} onChange={() => toggle(i)} />
            <span><div className="ob-option__value">{o.value}</div><div className="ob-option__seen">{seenOn(o)}</div></span>
          </label>
        ))}
      </div>
      <input className="claim-input" value={manual} onChange={(e) => setManual(e.target.value)} placeholder="Add a license number that isn't listed (optional)" aria-label="Another license" />
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <button className="claim-btn-primary ob-btn" disabled={busy || (keep.length === 0 && !manual.trim())} onClick={() => onResolve({ keep, manual: manual.trim() })}>
          Keep {keep.length > 1 ? 'these' : 'this'}
        </button>
        {conflict.options.length > 1 && keep.length < conflict.options.length && (
          <button className="ob-link" onClick={() => setKeep(conflict.options.map((_, i) => i))}>Both are real</button>
        )}
      </div>
    </>
  )
}

// Each address is the primary one, a secondary one, or no longer current; a different one can be typed.
const ROLES = { primary: 'Primary', secondary: 'Secondary', old: 'Not current' }

function AddressCard({ conflict, busy, onResolve }) {
  const [roles, setRoles] = useState(() => Object.fromEntries(conflict.options.map((_, i) => [i, i === 0 ? 'primary' : 'secondary'])))
  const [manualPrimary, setManualPrimary] = useState('')
  const [extra, setExtra] = useState('')
  const typed = manualPrimary.trim() !== ''

  function setRole(i, role) {
    // Only one address can be primary: picking it demotes the previous one.
    setRoles((prev) => {
      const next = { ...prev, [i]: role }
      if (role === 'primary') for (const k of Object.keys(next)) if (Number(k) !== i && next[k] === 'primary') next[k] = 'secondary'
      return next
    })
  }
  const primaries = Object.entries(roles).filter(([, r]) => r === 'primary')
  const ready = typed || primaries.length === 1

  function submit() {
    // A typed primary replaces the listed one, which then stays on as a secondary address.
    const secondary = Object.entries(roles).filter(([, r]) => r === 'secondary' || (typed && r === 'primary')).map(([i]) => Number(i))
    onResolve({
      primary: typed ? { manual: manualPrimary.trim() } : Number(primaries[0][0]),
      secondary,
      manual_secondary: extra.trim() ? [extra.trim()] : [],
    })
  }

  return (
    <>
      <div className="ob-list">
        {conflict.options.map((o, i) => (
          <div key={i} className="ob-option" style={{ cursor: 'default', alignItems: 'center' }}>
            <span style={{ flex: 1 }}><div className="ob-option__value">{o.value}</div><div className="ob-option__seen">{seenOn(o)}</div></span>
            <select className="ob-select" value={typed && roles[i] === 'primary' ? 'secondary' : roles[i]} onChange={(e) => setRole(i, e.target.value)} aria-label={`Role of ${o.value}`}>
              {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        ))}
      </div>
      <input className="claim-input" value={manualPrimary} onChange={(e) => setManualPrimary(e.target.value)} placeholder="Or type a different primary address" aria-label="A different primary address" />
      <input className="claim-input" value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Another address to keep as secondary (optional)" aria-label="A secondary address" />
      {!ready && <div className="ob-hint">Choose exactly one primary address, or type one.</div>}
      <button className="claim-btn-primary ob-btn" disabled={busy || !ready} onClick={submit}>Save addresses</button>
    </>
  )
}

const TITLES = {
  license: () => 'Which license is real?',
  address: () => 'Which address is your primary one?',
  pick_one: (label) => `Which ${label.toLowerCase()} is right?`,
}

function ConflictCard({ conflict, label, busy, onResolve }) {
  const props = { conflict, busy, onResolve: (resolution) => onResolve(conflict.id, resolution) }
  return (
    <div style={{ display: 'grid', gap: 12, textAlign: 'left' }}>
      <h2 className="ob-focus__title" style={{ textAlign: 'center' }}>{(TITLES[conflict.kind] || TITLES.pick_one)(label)}</h2>
      <div className="ob-hint" style={{ textAlign: 'center' }}>Your pages don&apos;t agree. You decide what goes on your profile.</div>
      {conflict.kind === 'license' && <LicenseCard {...props} />}
      {conflict.kind === 'address' && <AddressCard {...props} />}
      {conflict.kind !== 'license' && conflict.kind !== 'address' && <PickOneCard {...props} label={label} />}
    </div>
  )
}

// Stage "conflicts": every field the pages disagreed on, asked once the pages are all read, one at a time.
function ConflictScene({ data, busy, agentBusy, onResolve }) {
  const labelOf = useMemo(() => Object.fromEntries(data.fields.map((f) => [f.key, f.label])), [data.fields])
  const open = data.conflicts.filter((c) => c.status === 'open')
  const total = data.conflicts.length
  const current = open[0]
  if (!current) return null
  return (
    <div className="ob-focus ob-focus--wide pilot-rise" key={current.id}>
      <div className="ob-focus__count">Difference {total - open.length + 1} of {total}</div>
      <ConflictCard conflict={current} label={labelOf[current.field] || current.field} busy={busy || agentBusy} onResolve={onResolve} />
    </div>
  )
}

export default ConflictScene
