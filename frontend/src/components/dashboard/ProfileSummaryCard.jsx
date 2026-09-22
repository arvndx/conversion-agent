import AvatarCircle from '../shared/AvatarCircle.jsx'
import Badge from '../shared/Badge.jsx'

function ProfileSummaryCard({ profile }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 16 }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <AvatarCircle name={profile.name} avatarUrl={profile.avatar_url} size={48} />
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <strong>{profile.name}</strong>
            {profile.is_verified && <Badge variant="verified" />}
            {profile.is_pro && <Badge variant="pro" />}
          </div>
          <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>
            You are ranked {profile.rank_position} of {profile.rank_total} {profile.category} Professionals in {profile.location}
          </div>
        </div>
      </div>

      <button
        style={{
          width: '100%',
          marginTop: 16,
          border: '1px solid var(--border)',
          background: '#fff',
          borderRadius: 8,
          padding: '10px 0',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        ▶ Play Game
      </button>
    </div>
  )
}

export default ProfileSummaryCard
