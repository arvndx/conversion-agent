function daysLeft(trialEndsAt) {
  if (!trialEndsAt) return null
  const ms = new Date(trialEndsAt).getTime() - Date.now()
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)))
}

function ProSlotStatus({ slotStatus, category, location, onUpgrade, onStartTrial, onJoinWaitlist, upgrading, joined }) {
  const { taken, total, remaining, is_full: isFull, is_trial: isTrial, trial_ends_at: trialEndsAt } = slotStatus

  return (
    <div className="panel" data-agent-target="pro-slot-status">
      <div className="slot-head">
        <b>Pro Spots — {category} in {location}</b>
        <span style={{ whiteSpace: 'nowrap', color: 'var(--ink-soft)', fontWeight: 600 }}>{taken} of {total} taken</span>
      </div>
      <div className="slot-dots" aria-hidden="true">
        {Array.from({ length: total }, (_, i) => <i key={i} className={i < taken ? 'on' : ''} />)}
      </div>

      {isTrial && (
        <div className="callout callout--warm">
          🎉 You're on a free Pro trial — {daysLeft(trialEndsAt)} day(s) left. Subscribe to keep your spot.
        </div>
      )}

      {!isTrial && isFull && <div className="callout callout--dark">🔒 All {total} Pro spots in this market are taken right now.</div>}

      {!isTrial && !isFull && (
        <div className="callout callout--soft">
          🔥 Only {remaining} spot{remaining === 1 ? '' : 's'} left — grab yours before someone else does.
        </div>
      )}

      <div className="btn-row">
        {isFull && !isTrial ? (
          <button onClick={onJoinWaitlist} disabled={joined} className={`btn ${joined ? 'btn--ghost' : 'btn--primary'}`}>
            {joined ? "You're on the waitlist" : 'Join Waitlist'}
          </button>
        ) : (
          !isTrial && (
            <>
              <button onClick={onUpgrade} disabled={upgrading} className="btn btn--pro">👑 Upgrade to Pro</button>
              <button onClick={onStartTrial} disabled={upgrading} className="btn btn--outline">Start Free Trial</button>
            </>
          )
        )}
      </div>
    </div>
  )
}

export default ProSlotStatus
