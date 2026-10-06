import { Link } from 'react-router-dom'
import AvatarCircle from '../shared/AvatarCircle.jsx'
import Badge from '../shared/Badge.jsx'
import StarRating from '../shared/StarRating.jsx'
import { useClaimCard } from '../claim/ClaimCard.jsx'

function ResultCard({ profile }) {
  const { openClaim } = useClaimCard()
  const isUnclaimed = profile.lifecycle_state === 'unclaimed'

  return (
    <div
      className="result-card"
      style={{
        display: 'flex',
        gap: 16,
        padding: 16,
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        background: '#fff',
        marginBottom: 12,
      }}
    >
      <AvatarCircle name={profile.name} avatarUrl={profile.avatar_url} size={64} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <Link to={`/profile/${profile.id}`} style={{ fontWeight: 700, fontSize: 16, textDecoration: 'none', color: 'var(--ink)' }}>
            {profile.name}
          </Link>
          {profile.is_verified && <Badge variant="verified" />}
          {profile.is_pro && <Badge variant="pro" />}
          {isUnclaimed && (
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-soft)', background: 'var(--surface-muted)', padding: '2px 8px', borderRadius: 999 }}>
              Unclaimed
            </span>
          )}
        </div>

        {profile.top_5_percent && (
          <div style={{ marginTop: 4 }}>
            <Badge variant="top5" />
          </div>
        )}

        <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 4 }}>
          {profile.business_name} · {profile.location}
        </div>

        {profile.tags?.length > 0 && (
          <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
            {profile.tags.map((tag) => (
              <span
                key={tag}
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  background: 'var(--surface-muted)',
                  color: 'var(--ink-soft)',
                  padding: '3px 8px',
                  borderRadius: 4,
                }}
              >
                {tag.toUpperCase()}
              </span>
            ))}
          </div>
        )}

        {profile.review_snippet && (
          <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 8, fontStyle: 'italic' }}>
            &ldquo;{profile.review_snippet}&rdquo;
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
          {profile.review_count > 0 ? (
            <StarRating rating={profile.avg_rating} count={profile.review_count} />
          ) : (
            <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No reviews yet</span>
          )}
          {isUnclaimed ? (
            <button
              onClick={() => openClaim({ profileId: profile.id })}
              style={{
                marginLeft: 'auto',
                background: 'var(--pro-badge)',
                color: '#fff',
                border: 'none',
                padding: '8px 20px',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Claim now
            </button>
          ) : (
            <Link
              to={`/profile/${profile.id}`}
              style={{
                marginLeft: 'auto',
                background: 'var(--brand)',
                color: '#fff',
                padding: '8px 20px',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              Contact
            </Link>
          )}
        </div>
      </div>

      <div className="result-score" style={{ textAlign: 'right', flexShrink: 0, minWidth: 70 }}>
        <div style={{ fontSize: 11, color: 'var(--ink-soft)' }}>Search Rank Score</div>
        <div style={{ fontWeight: 800, fontSize: 20, color: profile.search_rank_score > 0 ? 'var(--ink)' : 'var(--ink-soft)' }}>
          {profile.search_rank_score > 0 ? profile.search_rank_score : 'Not yet ranked'}
        </div>
      </div>
    </div>
  )
}

export default ResultCard
