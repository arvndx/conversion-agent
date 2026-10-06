const ARC = Math.PI * 90 // length of the half-circle below

function ScoreGauge({ score, maxPossible, deltaSinceLastWeek }) {
  const denom = maxPossible || 850
  const pct = Math.max(0, Math.min(1, score / denom))
  const arc = 'M 10 100 A 90 90 0 0 1 190 100'

  return (
    <div className="gauge-card" data-agent-target="score-gauge">
      <svg viewBox="0 0 200 112" width="240" height="134" role="img" aria-label={`Score ${score} of ${denom}`}>
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#7c5cff" />
            <stop offset="55%" stopColor="#4527d1" />
            <stop offset="100%" stopColor="#16a34a" />
          </linearGradient>
        </defs>
        <path d={arc} fill="none" stroke="#eef0f5" strokeWidth="16" strokeLinecap="round" />
        <path d={arc} fill="none" stroke="url(#gaugeGradient)" strokeWidth="16" strokeLinecap="round" strokeDasharray={`${pct * ARC} ${ARC}`} />
      </svg>

      <div style={{ marginTop: -50 }}>
        <div style={{ fontSize: 44, fontWeight: 800, lineHeight: 1, letterSpacing: '-0.03em' }}>{score}</div>
        <div className="panel__sub" style={{ marginTop: 6 }}>Search Rank Score · of {denom}</div>
        {typeof deltaSinceLastWeek === 'number' && (
          <span className={`delta ${deltaSinceLastWeek >= 0 ? 'delta--up' : 'delta--down'}`}>
            {deltaSinceLastWeek >= 0 ? '▲ +' : '▼ '}
            {deltaSinceLastWeek} since last week
          </span>
        )}
      </div>
    </div>
  )
}

export default ScoreGauge
