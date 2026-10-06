function TrialBadge({ trialEndsAt }) {
  if (!trialEndsAt) return null

  const daysLeft = Math.max(0, Math.ceil((new Date(trialEndsAt).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))

  return (
    <div className="trial-badge" data-agent-target="trial-badge">
      🎉 Pro Trial — {daysLeft} day{daysLeft === 1 ? '' : 's'} left
    </div>
  )
}

export default TrialBadge
