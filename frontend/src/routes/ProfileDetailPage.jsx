import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import TopNav from '../components/layout/TopNav.jsx'
import Breadcrumb from '../components/layout/Breadcrumb.jsx'
import UnclaimedNoticeBar from '../components/profile/UnclaimedNoticeBar.jsx'
import ProfileHeaderCard from '../components/profile/ProfileHeaderCard.jsx'
import ContactInfoCard from '../components/profile/ContactInfoCard.jsx'
import BusinessHoursCard from '../components/profile/BusinessHoursCard.jsx'
import RelatedProfessionalsList from '../components/profile/RelatedProfessionalsList.jsx'
import ReviewsList from '../components/profile/ReviewsList.jsx'
import { getProfile, getRelatedProfiles } from '../api/profiles.js'
import { useClaimCard } from '../components/claim/ClaimCard.jsx'

function ProfileDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { openClaim } = useClaimCard()
  const [profile, setProfile] = useState(null)
  const [topRated, setTopRated] = useState([])
  const [topViewed, setTopViewed] = useState([])

  useEffect(() => {
    getProfile(id)
      .then(setProfile)
      .catch(() => navigate('/not-found?what=profile', { replace: true })) // off the profile route, so the assistant is not offered
    // The side lists are a nicety: if they fail the profile is still worth showing.
    getRelatedProfiles(id, { sort: 'rating' }).then(setTopRated).catch(() => {})
    getRelatedProfiles(id, { sort: 'views' }).then(setTopViewed).catch(() => {})
  }, [id, navigate])

  if (!profile) return null

  return (
    <div>
      <TopNav />
      {profile.lifecycle_state === 'unclaimed' && (
        <UnclaimedNoticeBar onClaim={() => openClaim({ profileId: Number(id) })} />
      )}
      <Breadcrumb
        items={[{ label: 'Search', to: '/search' }, { label: profile.category, to: `/search?category=${profile.category}` }, { label: profile.name }]}
      />

      <div style={{ display: 'flex', gap: 24, padding: '0 24px 40px', maxWidth: 1280, margin: '0 auto' }}>
        <main style={{ flex: 1, minWidth: 0 }}>
          <ProfileHeaderCard profile={profile} />

          <div style={{ display: 'flex', gap: 16, marginTop: 16 }}>
            <ContactInfoCard profile={profile} />
            <BusinessHoursCard address={profile.address} hours={profile.business_hours} location={profile.location} />
          </div>

          <div style={{ marginTop: 24, background: '#fff', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 16 }}>
            <h3 style={{ marginTop: 0, fontSize: 16 }}>Reviews</h3>
            <ReviewsList reviews={profile.reviews} />
          </div>
        </main>

        <aside style={{ width: 260, flexShrink: 0 }}>
          <RelatedProfessionalsList title="Top Rated professionals" items={topRated} />
          <RelatedProfessionalsList title="Top Viewed professionals" items={topViewed} />
        </aside>
      </div>
    </div>
  )
}

export default ProfileDetailPage
