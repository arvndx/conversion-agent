import PlatformIcon from '../shared/PlatformIcon.jsx'

// A link to a site we do not read (LinkedIn, Instagram, X) that turned up on their pages: one question each.
// "Yes" counts it toward Connections; "Not mine" drops it.
function LinkScene({ item, index, total, busy, onSave }) {
  return (
    <div className="ob-focus pilot-rise" key={item.platform}>
      <div className="ob-focus__count">Link {index} of {total}</div>
      <PlatformIcon name={item.label} />
      <h2 className="ob-focus__title">Is this your {item.label}?</h2>
      <a className="ob-focus__sub" href={item.url} target="_blank" rel="noreferrer">{item.url.replace(/^https?:\/\/(www\.)?/, '')} ↗</a>
      <div className="ob-hint">We don&apos;t open this site. If it&apos;s yours, it counts toward your Connections score.</div>
      <div className="ob-focus__actions">
        <button className="claim-btn-primary ob-btn ob-btn--lg" disabled={busy} onClick={() => onSave(item.platform, item.url)}>Yes, it&apos;s mine</button>
        <button className="claim-btn-secondary ob-btn ob-btn--lg" disabled={busy} onClick={() => onSave(item.platform, '')}>Not mine</button>
      </div>
    </div>
  )
}

export default LinkScene
