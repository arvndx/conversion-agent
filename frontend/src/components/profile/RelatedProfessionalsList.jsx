import { Link } from 'react-router-dom'
import AvatarCircle from '../shared/AvatarCircle.jsx'
import StarRating from '../shared/StarRating.jsx'

function RelatedProfessionalsList({ title, items }) {
  if (!items?.length) return null

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 15 }}>{title}</h3>
      {items.map((p) => (
        <Link
          key={p.id}
          to={`/profile/${p.id}`}
          style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12, textDecoration: 'none', color: 'inherit' }}
        >
          <AvatarCircle name={p.name} avatarUrl={p.avatar_url} size={36} />
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{p.name}</div>
            <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{p.category}</div>
            {p.review_count > 0 && <StarRating rating={p.avg_rating} count={p.review_count} />}
          </div>
        </Link>
      ))}
    </div>
  )
}

export default RelatedProfessionalsList
