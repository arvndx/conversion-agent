import { CATEGORY_META, CATEGORY_ORDER } from '../../constants/categories.js'

function ScoreOverviewCard({ score }) {
  const unlocked = CATEGORY_ORDER.filter((key) => !score.categories[key].locked)

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>Search Rank Score Overview ⓘ</h3>
        <span style={{ fontSize: 13, fontWeight: 700 }}>
          {score.total} of {score.max_possible || 850} Possible
        </span>
      </div>

      <div style={{ display: 'flex', height: 10, borderRadius: 999, overflow: 'hidden', background: 'var(--border)', marginTop: 12 }}>
        {unlocked.map((key) => {
          const cat = score.categories[key]
          const widthPct = (cat.earned / 850) * 100
          return <div key={key} style={{ width: `${widthPct}%`, background: CATEGORY_META[key].color }} />
        })}
      </div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 12 }}>
        {unlocked.map((key) => (
          <span key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--ink-soft)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: CATEGORY_META[key].color, display: 'inline-block' }} />
            {CATEGORY_META[key].label}
          </span>
        ))}
      </div>

      <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 12, background: 'var(--surface-muted)', borderRadius: 6, padding: '8px 12px' }}>
        {score.unlock_points > 0 ? (
          <>
            <strong>Pro Tip:</strong> Earn up to {score.unlock_points} more points toward your Search Rank Score by upgrading to Pro.
          </>
        ) : (
          <>
            <strong>Nice work:</strong> You&apos;ve unlocked your full Search Rank Score potential.
          </>
        )}
      </div>
    </div>
  )
}

export default ScoreOverviewCard
