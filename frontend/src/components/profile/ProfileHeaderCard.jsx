import { Link } from 'react-router-dom'
import AvatarCircle from '../shared/AvatarCircle.jsx'
import Badge from '../shared/Badge.jsx'
import StarRating from '../shared/StarRating.jsx'

function ProfileHeaderCard({ profile }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden', background: '#fff' }}>
      <div
        style={{
          background: 'linear-gradient(90deg, #5b3df5, #7c5cff)',
          color: '#fff',
          padding: '10px 20px',
          fontSize: 13,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span>Get found as the Top {profile.category} in {profile.location}</span>
        <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>Learn More</span>
      </div>

      <div style={{ padding: 20 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <AvatarCircle name={profile.name} avatarUrl={profile.avatar_url} size={80} />

          <div style={{ flex: 1, minWidth: 220 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <h1 style={{ fontSize: 22, margin: 0 }}>{profile.name}</h1>
              {profile.is_claimed_or_pro && <Badge variant="verified" />}
              {profile.is_pro && <Badge variant="pro" />}
            </div>
            <div style={{ color: 'var(--ink-soft)', fontSize: 14 }}>{profile.category}</div>
            <div style={{ color: 'var(--ink-soft)', fontSize: 14, marginTop: 2 }}>
              {profile.business_name} · {profile.location}
            </div>

            {profile.review_count > 0 && (
              <div style={{ marginTop: 8 }}>
                <StarRating rating={profile.avg_rating} count={profile.review_count} />
              </div>
            )}

            {profile.bio && <p style={{ fontSize: 14, color: 'var(--ink)', maxWidth: 640, marginTop: 12 }}>{profile.bio}</p>}

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
                    {tag}
                  </span>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
              <button style={{ border: '1px solid var(--border)', background: '#fff', borderRadius: 6, padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}>
                Share Profile
              </button>
              <button style={{ border: '1px solid var(--border)', background: '#fff', borderRadius: 6, padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}>
                Refer {profile.name.split(' ')[1] || profile.name}
              </button>
            </div>
          </div>

          <div style={{ textAlign: 'right', minWidth: 140 }}>
            <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>Search Rank Score</div>
            <div style={{ fontSize: 28, fontWeight: 800 }}>{profile.search_rank_score}</div>
            {profile.is_claimed_or_pro ? (
              <Link
                to={`/dashboard/${profile.id}/manage`}
                style={{ fontSize: 13, color: 'var(--brand)', textDecoration: 'none' }}
              >
                Manage this profile →
              </Link>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>Claim to manage &amp; improve</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProfileHeaderCard
