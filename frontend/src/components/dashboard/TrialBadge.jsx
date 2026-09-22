function TrialBadge({ trialEndsAt }) {
  if (!trialEndsAt) return null

  const daysLeft = Math.max(0, Math.ceil((new Date(trialEndsAt).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))

  return (
    <div
      style={{
        background: '#fff7ed',
        color: '#9a3412',
        borderRadius: 8,
        padding: '10px 14px',
        fontSize: 13,
        fontWeight: 600,
        marginBottom: 12,
      }}
      data-agent-target="trial-badge"
    >
      🎉 Pro Trial — {daysLeft} day{daysLeft === 1 ? '' : 's'} left
    </div>
  )
}

export default TrialBadge
