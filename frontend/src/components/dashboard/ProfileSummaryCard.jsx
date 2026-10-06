import AvatarCircle from '../shared/AvatarCircle.jsx'
import Badge from '../shared/Badge.jsx'

function ProfileSummaryCard({ profile }) {
  return (
    <div className="panel profile-card">
      <div className="profile-card__cover" />
      <div className="profile-card__body">
        <div className="profile-card__avatar"><AvatarCircle name={profile.name} avatarUrl={profile.avatar_url} size={68} /></div>
        <div className="profile-card__name">
          {profile.name}
          {profile.is_verified && <Badge variant="verified" />}
          {profile.is_pro && <Badge variant="pro" />}
        </div>
        <div className="panel__sub">{profile.category} · {profile.location}</div>

        <div className="rank-tile">
          <b>#{profile.rank_position}<small> / {profile.rank_total}</small></b>
          <span>
            You are ranked {profile.rank_position} of {profile.rank_total} {profile.category} Professionals in {profile.location}
          </span>
        </div>

        <button className="btn btn--ghost btn--block">▶ Play Game</button>
      </div>
    </div>
  )
}

export default ProfileSummaryCard
