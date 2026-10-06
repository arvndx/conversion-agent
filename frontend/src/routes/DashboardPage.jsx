import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar.jsx'
import AppTopBar from '../components/layout/AppTopBar.jsx'
import PromoBanner from '../components/layout/PromoBanner.jsx'
import ProfileSummaryCard from '../components/dashboard/ProfileSummaryCard.jsx'
import TrialBadge from '../components/dashboard/TrialBadge.jsx'
import ScoreGauge from '../components/dashboard/ScoreGauge.jsx'
import AIWritingStudioCard from '../components/dashboard/AIWritingStudioCard.jsx'
import PromoCarousel from '../components/dashboard/PromoCarousel.jsx'
import ScoreOverviewCard from '../components/dashboard/ScoreOverviewCard.jsx'
import CategoryCard from '../components/dashboard/CategoryCard.jsx'
import UpsellCard from '../components/dashboard/UpsellCard.jsx'
import { getDashboard } from '../api/dashboard.js'
import { useActiveProfile } from '../context/ActiveProfileContext.jsx'

function DashboardPage() {
  const { profileId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { setActiveProfileId } = useActiveProfile()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setActiveProfileId(profileId)
    getDashboard(profileId)
      .then(setData)
      .catch((e) => e.status !== 401 && setError('not-claimed'))
  }, [profileId])

  useEffect(() => {
    if (error) navigate(`/profile/${profileId}`)
  }, [error, profileId])

  function onUnlock() {
    navigate(`/dashboard/${profileId}/upgrade`)
  }

  if (error || !data) return null

  return (
    <div className="owner-shell">
      <Sidebar profileId={profileId} onboarding={data.onboarding} />

      <div className="app-main">
        <PromoBanner />
        <AppTopBar
          title="Dashboard"
          currentProfile={data.profile}
          actions={
            data.profile.lifecycle_state !== 'pro' && (
              <button className="btn btn--pro btn--sm" onClick={() => navigate(`/dashboard/${profileId}/upgrade`)} data-agent-target="dashboard-upgrade-button">
                👑 Upgrade to Pro
              </button>
            )
          }
        />

        {searchParams.get('justUpgraded') === '1' && (
          <div className="notice notice--ok">🎉 You're now Pro! Website Health and Listings are unlocked.</div>
        )}

        <div className="owner-grid owner-grid--dash">
          <div className="stack">
            <TrialBadge trialEndsAt={data.profile.trial_ends_at} />
            <ProfileSummaryCard profile={data.profile} />
            <div className="panel">
              <ScoreGauge score={data.score.total} maxPossible={data.score.max_possible} deltaSinceLastWeek={data.profile.score_delta_last_week} />
              <button className="btn btn--primary btn--block" style={{ marginTop: 18 }}>Request Review</button>
            </div>
            <AIWritingStudioCard studio={data.ai_writing_studio} />
          </div>

          <div className="stack">
            <PromoCarousel />
            <ScoreOverviewCard score={data.score} />

            <div className="cat-grid">
              {data.category_cards.map((card) => (
                <CategoryCard key={card.key} card={card} profileId={profileId} />
              ))}
            </div>

            {data.upsell_cards.length > 0 && (
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {data.upsell_cards.map((card) => (
                  <UpsellCard key={card.key} card={card} onUnlock={onUnlock} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
