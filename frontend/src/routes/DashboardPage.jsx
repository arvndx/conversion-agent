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
      .catch(() => setError('not-claimed'))
  }, [profileId])

  useEffect(() => {
    if (error) navigate(`/profile/${profileId}`)
  }, [error, profileId])

  function onUnlock() {
    navigate(`/dashboard/${profileId}/upgrade`)
  }

  if (error || !data) return null

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar profileId={profileId} onboarding={data.onboarding} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <PromoBanner />
        <AppTopBar
          title="Dashboard"
          currentProfile={data.profile}
          actions={
            data.profile.lifecycle_state !== 'pro' && (
              <button
                onClick={() => navigate(`/dashboard/${profileId}/upgrade`)}
                data-agent-target="dashboard-upgrade-button"
                style={{
                  background: 'linear-gradient(135deg, #f5b301, var(--pro-badge))',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 999,
                  padding: '8px 16px',
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: '0 2px 8px rgba(217, 119, 6, 0.3)',
                }}
              >
                👑 Upgrade to Pro
              </button>
            )
          }
        />

        {searchParams.get('justUpgraded') === '1' && (
          <div style={{ background: '#dcfce7', color: '#166534', padding: '10px 24px', fontSize: 13 }}>
            🎉 You're now Pro! Website Health and Listings are unlocked.
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 20, padding: 24 }}>
          <div>
            <TrialBadge trialEndsAt={data.profile.trial_ends_at} />
            <ProfileSummaryCard profile={data.profile} />
            <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 20, marginTop: 16, textAlign: 'center' }}>
              <ScoreGauge score={data.score.total} maxPossible={data.score.max_possible} deltaSinceLastWeek={data.profile.score_delta_last_week} />
              <button
                style={{
                  width: '100%',
                  marginTop: 12,
                  background: 'var(--brand)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  padding: '10px 0',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Request Review
              </button>
            </div>
            <AIWritingStudioCard studio={data.ai_writing_studio} />
          </div>

          <div>
            <PromoCarousel />
            <div style={{ marginTop: 16 }}>
              <ScoreOverviewCard score={data.score} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginTop: 16 }}>
              {data.category_cards.map((card) => (
                <CategoryCard key={card.key} card={card} profileId={profileId} />
              ))}
            </div>

            {data.upsell_cards.length > 0 && (
              <div style={{ display: 'flex', gap: 16, marginTop: 16, flexWrap: 'wrap' }}>
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
