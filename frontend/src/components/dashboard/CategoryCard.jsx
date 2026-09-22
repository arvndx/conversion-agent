import { Link } from 'react-router-dom'
import ProgressBar from '../shared/ProgressBar.jsx'
import { CATEGORY_META } from '../../constants/categories.js'

const ICONS = { reviews: '💬', profile_completion: '👤', connections: '🔗' }

function CategoryCard({ card, profileId }) {
  return (
    <Link
      to={`/dashboard/${profileId}/manage`}
      style={{
        display: 'block',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        background: '#fff',
        padding: 16,
        textDecoration: 'none',
        color: 'inherit',
      }}
      data-agent-target={`category-${card.key}`}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 20 }}>{ICONS[card.key]}</span>
        <span style={{ color: 'var(--ink-soft)' }}>›</span>
      </div>
      <div style={{ fontWeight: 600, fontSize: 14, marginTop: 8 }}>{CATEGORY_META[card.key].label} ⓘ</div>
      <div style={{ fontSize: 13, color: 'var(--ink-soft)', margin: '4px 0 8px' }}>{card.status_line}</div>
      <ProgressBar percent={card.progress_pct} color={CATEGORY_META[card.key].color} />
    </Link>
  )
}

export default CategoryCard
