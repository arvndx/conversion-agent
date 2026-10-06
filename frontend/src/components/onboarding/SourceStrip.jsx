import { iconFor, pluralize, STATUS_CHIPS } from './sourceMeta.js'

// Every confirmed page with its live status. Used while the pages are being read (rows update as the
// server finishes each one) and, quieter, above the later steps as a record of what was read.
function SourceStrip({ sources, compact = false }) {
  const rows = sources.filter((s) => s.status in STATUS_CHIPS)
  if (rows.length === 0) return null
  return (
    <div className="ob-list">
      {rows.map((s) => {
        const [label, tone] = STATUS_CHIPS[s.status]
        const found = s.fields_found?.length || 0
        return (
          <div key={s.id} className="ob-source" style={compact ? { padding: '9px 12px' } : undefined}>
            <div className="ob-source__head">
              <span className="ob-source__icon" style={compact ? { width: 26, height: 26, fontSize: 14 } : undefined}>{iconFor(s.platform)}</span>
              <div style={{ minWidth: 0 }}>
                <div className="ob-source__host">{s.host}</div>
                {!compact && s.error && s.status !== 'done' && <div className="ob-source__url">{s.error}</div>}
              </div>
              <span className={`ob-chip ob-chip--grow ob-chip--${tone}`}>
                {s.status === 'scraping' && <span className="ob-spinner" />}
                {s.status === 'done' ? `✓ ${found ? `Read · ${pluralize(found, 'detail')}` : 'Read'}` : label}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default SourceStrip
