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
import { claimProfile, getProfile, getRelatedProfiles } from '../api/profiles.js'

function ProfileDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [topRated, setTopRated] = useState([])
  const [topViewed, setTopViewed] = useState([])
  const [claiming, setClaiming] = useState(false)

  useEffect(() => {
    getProfile(id).then(setProfile)
    getRelatedProfiles(id, { sort: 'rating' }).then(setTopRated)
    getRelatedProfiles(id, { sort: 'views' }).then(setTopViewed)
  }, [id])

  async function onClaim() {
    setClaiming(true)
    try {
      await claimProfile(id)
      navigate('/inbox')
    } finally {
      setClaiming(false)
    }
  }

  if (!profile) return null

  return (
    <div>
      <TopNav />
      {profile.lifecycle_state === 'unclaimed' && (
        <UnclaimedNoticeBar onClaim={onClaim} claiming={claiming} />
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
