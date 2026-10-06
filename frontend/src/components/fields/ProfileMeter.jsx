// "9 / 12" with a bar: how many of the scored profile details are filled in.
function ProfileMeter({ filled, total, label = 'Profile completeness', className = '' }) {
  const pct = total ? Math.round((filled / total) * 100) : 0
  const done = total > 0 && filled >= total
  return (
    <div
      className={`pf-meter${done ? ' pf-meter--done' : ''} ${className}`.trim()}
      role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={filled}
    >
      <div className="pf-meter__row"><span>{label}</span><b>{done ? '✓ ' : ''}{filled} / {total}</b></div>
      <div className="pf-meter__bar"><div className="pf-meter__fill" style={{ width: `${pct}%` }} /></div>
    </div>
  )
}

export default ProfileMeter
