function daysLeft(trialEndsAt) {
  if (!trialEndsAt) return null
  const ms = new Date(trialEndsAt).getTime() - Date.now()
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)))
}

function ProSlotStatus({ slotStatus, category, location, onUpgrade, onStartTrial, onJoinWaitlist, upgrading, joined }) {
  const { taken, total, remaining, is_full: isFull, is_trial: isTrial, trial_ends_at: trialEndsAt } = slotStatus

  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        background: '#fff',
        padding: 16,
        marginTop: 16,
      }}
      data-agent-target="pro-slot-status"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 8 }}>
        <span style={{ fontWeight: 600 }}>Pro Spots — {category} in {location}</span>
        <span>{taken} of {total} taken</span>
      </div>

      {isTrial && (
        <div style={{ background: '#fff7ed', color: '#9a3412', borderRadius: 6, padding: '8px 12px', fontSize: 13, marginBottom: 12 }}>
          🎉 You're on a free Pro trial — {daysLeft(trialEndsAt)} day(s) left. Subscribe to keep your spot.
        </div>
      )}

      {!isTrial && isFull && (
        <div style={{ background: '#111827', color: '#fff', borderRadius: 6, padding: '10px 12px', fontSize: 13, marginBottom: 12 }}>
          🔒 All {total} Pro spots in this market are taken right now.
        </div>
      )}

      {!isTrial && !isFull && (
        <div style={{ background: 'var(--surface-muted)', borderRadius: 6, padding: '8px 12px', fontSize: 13, marginBottom: 12 }}>
          🔥 Only {remaining} spot{remaining === 1 ? '' : 's'} left — grab yours before someone else does.
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        {isFull && !isTrial ? (
          <button
            onClick={onJoinWaitlist}
            disabled={joined}
            style={{
              flex: 1,
              background: joined ? 'var(--border)' : 'var(--brand)',
              color: joined ? 'var(--ink-soft)' : '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '10px 0',
              fontWeight: 700,
              cursor: joined ? 'default' : 'pointer',
            }}
          >
            {joined ? "You're on the waitlist" : 'Join Waitlist'}
          </button>
        ) : (
          !isTrial && (
            <>
              <button
                onClick={onUpgrade}
                disabled={upgrading}
                style={{
                  flex: 1,
                  background: 'var(--pro-badge)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  padding: '10px 0',
                  fontWeight: 700,
                  cursor: upgrading ? 'default' : 'pointer',
                }}
              >
                👑 Upgrade to Pro
              </button>
              <button
                onClick={onStartTrial}
                disabled={upgrading}
                style={{
                  flex: 1,
                  background: '#fff',
                  color: 'var(--brand)',
                  border: '1px solid var(--brand)',
                  borderRadius: 8,
                  padding: '10px 0',
                  fontWeight: 700,
                  cursor: upgrading ? 'default' : 'pointer',
                }}
              >
                Start Free Trial
              </button>
            </>
          )
        )}
      </div>
    </div>
  )
}

export default ProSlotStatus
