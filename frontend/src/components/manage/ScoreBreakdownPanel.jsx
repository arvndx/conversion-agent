import Panel from '../shared/Panel.jsx'
import ProgressBar from '../shared/ProgressBar.jsx'
import { CATEGORY_META, CATEGORY_ORDER } from '../../constants/categories.js'

function ScoreBreakdownPanel({ score, totalUnlock, onUnlock }) {
  return (
    <Panel
      icon="🎯" tint="#efecff" title="Score Breakdown" subtitle="Search Rank Score"
      aside={<span className="score-total"><b>{score.total}</b><span>/ {score.max_possible}</span></span>}
    >
      {totalUnlock?.available && (
        <div className="unlock-box">
          <p>
            👑 Unlocking Pro adds <strong>+{totalUnlock.points} points</strong> — moving you from rank {totalUnlock.rank_from} to rank{' '}
            <strong>{totalUnlock.rank_to}</strong> of {totalUnlock.rank_total} in your market.
          </p>
          <button onClick={onUnlock} className="btn btn--pro btn--sm">Unlock with Pro</button>
        </div>
      )}

      {CATEGORY_ORDER.map((key) => {
        const cat = score.categories[key]
        const color = CATEGORY_META[key].color
        return (
          <div key={key} className={`score-row${cat.locked ? ' score-row--locked' : ''}`}>
            <div className="score-row__top">
              <span className="score-row__dot" style={{ background: color }} />
              <span className="score-row__label">{CATEGORY_META[key].label}</span>
              {cat.locked && <span className="chip-pro">🔒 Pro</span>}
              <span className="score-row__pts">
                {cat.earned}<small> / {cat.max}</small>
              </span>
            </div>
            <ProgressBar percent={(cat.earned / cat.max) * 100} color={color} />
            {cat.locked && <div className="todo-list" style={{ marginTop: 8 }}><span className="panel__sub">Unlocks with Pro</span></div>}
            {cat.opportunities.length > 0 && (
              <ul className="todo-list">
                {cat.opportunities.map((op) => (
                  <li key={op}>{op}</li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </Panel>
  )
}

export default ScoreBreakdownPanel
