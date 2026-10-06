import Panel from '../shared/Panel.jsx'
import { CATEGORY_META, CATEGORY_ORDER } from '../../constants/categories.js'

function ScoreOverviewCard({ score }) {
  // Sections come from the profile's category (their order, labels and which are Pro-locked vary).
  const order = (score.section_order || CATEGORY_ORDER).filter((key) => score.categories[key])
  const unlocked = order.filter((key) => !score.categories[key].locked)
  const lockedLabels = order.filter((key) => score.categories[key].locked).map((key) => score.categories[key].label)
  const proMax = score.pro_max || 850

  return (
    <Panel
      icon="📊" tint="#e9f0ff" title="Search Rank Score Overview" subtitle="Where your points come from"
      aside={<span className="score-total"><b>{score.total}</b><span>of {score.max_possible || proMax} possible</span></span>}
    >
      <div className="seg">
        {unlocked.map((key) => (
          <div key={key} style={{ width: `${(score.categories[key].earned / proMax) * 100}%`, background: CATEGORY_META[key].color }} />
        ))}
      </div>

      <div className="legend">
        {unlocked.map((key) => (
          <span key={key}><i style={{ background: CATEGORY_META[key].color }} />{score.categories[key].label}</span>
        ))}
      </div>

      <div className="tip">
        {lockedLabels.length > 0 ? (
          <>
            💡 <strong>Pro Tip:</strong> Unlock {lockedLabels.join(' and ')} to earn up to {score.locked_max ?? score.unlock_points} more
            points toward your Search Rank Score.
          </>
        ) : (
          <>
            🎉 <strong>Nice work:</strong> You&apos;ve unlocked your full Search Rank Score potential.
          </>
        )}
      </div>
    </Panel>
  )
}

export default ScoreOverviewCard
