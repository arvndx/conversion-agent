import { Link } from 'react-router-dom'
import ProgressBar from '../shared/ProgressBar.jsx'
import { CATEGORY_META } from '../../constants/categories.js'

const ICONS = { reviews: '💬', profile_completion: '👤', connections: '🔗', web_analytics: '🌐', listings: '📍' }

function CategoryCard({ card, profileId }) {
  const color = CATEGORY_META[card.key].color
  return (
    <Link to={`/dashboard/${profileId}/manage`} className="cat-card" data-agent-target={`category-${card.key}`}>
      <div className="cat-card__top">
        <span className="cat-card__icon" style={{ background: `${color}22` }}>{ICONS[card.key]}</span>
        <span className="cat-card__go" aria-hidden="true">›</span>
      </div>
      <div className="cat-card__label">{card.label}</div>
      <div className="cat-card__line">{card.status_line}</div>
      <ProgressBar percent={card.progress_pct} color={color} />
    </Link>
  )
}

export default CategoryCard
