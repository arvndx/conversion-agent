import ProgressBar from '../shared/ProgressBar.jsx'
import { CATEGORY_META, CATEGORY_ORDER } from '../../constants/categories.js'

function ScoreBreakdownPanel({ score, totalUnlock, onUnlock }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>Search Rank Score Breakdown</h3>
        <span style={{ fontWeight: 800, fontSize: 20 }}>
          {score.total} / {score.max_possible}
        </span>
      </div>

      {totalUnlock?.available && (
        <div
          style={{
            background: 'linear-gradient(135deg, #fffbeb, #fef3c7)',
            border: '1.5px solid #fde68a',
            borderRadius: 12,
            padding: '12px 14px',
            marginBottom: 16,
          }}
        >
          <div style={{ fontSize: 13, color: 'var(--ink)', marginBottom: 8, lineHeight: 1.45 }}>
            👑 Unlocking Pro adds <strong>+{totalUnlock.points} points</strong> — moving you from rank {totalUnlock.rank_from} to rank{' '}
            <strong>{totalUnlock.rank_to}</strong> of {totalUnlock.rank_total} in your market.
          </div>
          <button onClick={onUnlock} className="agent-btn-primary" style={{ padding: '6px 14px', fontSize: 12 }}>
            Unlock with Pro
          </button>
        </div>
      )}

      {CATEGORY_ORDER.map((key) => {
        const cat = score.categories[key]
        return (
          <div key={key} style={{ marginBottom: 16, opacity: cat.locked ? 0.6 : 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, marginBottom: 4 }}>
              <span>
                {CATEGORY_META[key].label}
                {cat.locked && ' 🔒'}
              </span>
              <span>
                {cat.earned} / {cat.max}
                {cat.locked && ' — unlocks with Pro'}
              </span>
            </div>
            <ProgressBar percent={(cat.earned / cat.max) * 100} color={CATEGORY_META[key].color} />
            {cat.opportunities.length > 0 && (
              <ul style={{ fontSize: 12, color: 'var(--ink-soft)', margin: '6px 0 0', paddingLeft: 18 }}>
                {cat.opportunities.map((op) => (
                  <li key={op}>{op}</li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default ScoreBreakdownPanel
