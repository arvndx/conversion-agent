function ScoreGauge({ score, maxPossible, deltaSinceLastWeek }) {
  const denom = maxPossible || 850
  const pct = Math.max(0, Math.min(1, score / denom))
  const needleRotation = pct * 180

  return (
    <div style={{ textAlign: 'center' }} data-agent-target="score-gauge">
      <svg viewBox="0 0 200 110" width="220" height="121">
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#dc2626" />
            <stop offset="50%" stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#16a34a" />
          </linearGradient>
        </defs>
        <path d="M 10 100 A 90 90 0 0 1 190 100" fill="none" stroke="#e4e6ea" strokeWidth="14" strokeLinecap="round" />
        <path d="M 10 100 A 90 90 0 0 1 190 100" fill="none" stroke="url(#gaugeGradient)" strokeWidth="14" strokeLinecap="round" opacity="0.9" />
        <line
          x1="100"
          y1="100"
          x2="30"
          y2="100"
          stroke="var(--ink)"
          strokeWidth="3"
          strokeLinecap="round"
          transform={`rotate(${needleRotation} 100 100)`}
        />
        <circle cx="100" cy="100" r="6" fill="var(--ink)" />
      </svg>

      <div style={{ marginTop: -8 }}>
        <div style={{ fontSize: 40, fontWeight: 800, lineHeight: 1 }}>{score}</div>
        <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 4 }}>Search Rank Score ⓘ</div>
        {typeof deltaSinceLastWeek === 'number' && (
          <div style={{ fontSize: 12, color: deltaSinceLastWeek >= 0 ? 'var(--success)' : 'var(--danger)', marginTop: 4 }}>
            {deltaSinceLastWeek >= 0 ? '+' : ''}
            {deltaSinceLastWeek} since last week
          </div>
        )}
      </div>
    </div>
  )
}

export default ScoreGauge
