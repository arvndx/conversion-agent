import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar.jsx'
import AppTopBar from '../components/layout/AppTopBar.jsx'
import PromoBanner from '../components/layout/PromoBanner.jsx'
import EditableField from '../components/manage/EditableField.jsx'
import ConnectionsToggleList from '../components/manage/ConnectionsToggleList.jsx'
import DirectoryListingsSection from '../components/manage/DirectoryListingsSection.jsx'
import AnalyticsReadout from '../components/manage/AnalyticsReadout.jsx'
import ScoreBreakdownPanel from '../components/manage/ScoreBreakdownPanel.jsx'
import ProSlotStatus from '../components/manage/ProSlotStatus.jsx'
import ReviewReplyList from '../components/manage/ReviewReplyList.jsx'
import { SuggestionCard, ReviewSuggestionCard, scrollToAndFlash } from '../components/manage/SuggestionCard.jsx'
import {
  getDashboard,
  getManage,
  joinWaitlist,
  updateConnection,
  updateListing,
  updateProfile,
} from '../api/dashboard.js'
import { useActiveProfile } from '../context/ActiveProfileContext.jsx'

function ManageProfilePage() {
  const { profileId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { setActiveProfileId } = useActiveProfile()
  const [data, setData] = useState(null)
  const [dashboardProfile, setDashboardProfile] = useState(null)
  const [error, setError] = useState(null)
  const [joined, setJoined] = useState(false)

  function reload() {
    getManage(profileId)
      .then(setData)
      .catch(() => setError('not-claimed'))
  }

  useEffect(() => {
    setActiveProfileId(profileId)
    reload()
    getDashboard(profileId).then((d) => setDashboardProfile(d.profile))
  }, [profileId])

  useEffect(() => {
    if (error) navigate(`/profile/${profileId}`)
  }, [error, profileId])

  if (error || !data) return null

  const { profile, score, suggestions } = data

  async function saveField(field, value) {
    const result = await updateProfile(profileId, { [field]: value })
    setData(result)
  }

  async function toggleConnection(platform, isConnected) {
    const result = await updateConnection(profileId, platform, isConnected)
    setData(result)
  }

  async function toggleListing(platform, isPublished) {
    const result = await updateListing(profileId, platform, isPublished)
    setData(result)
  }

  // Both real-consequence actions now route through the Pricing page for a proper look-
  // before-you-buy screen, rather than upgrading instantly on a single sidebar click.
  function onUpgrade() {
    navigate(`/dashboard/${profileId}/upgrade`)
  }

  function onStartTrial() {
    navigate(`/dashboard/${profileId}/upgrade`)
  }

  async function onJoinWaitlist() {
    await joinWaitlist(profileId)
    setJoined(true)
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar profileId={profileId} onboarding={null} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <PromoBanner />
        <AppTopBar
          title="Manage Profile"
          currentProfile={dashboardProfile}
          actions={
            profile.lifecycle_state !== 'pro' && (
              <button
                onClick={() => navigate(`/dashboard/${profileId}/upgrade`)}
                data-agent-target="manage-upgrade-button"
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

        {searchParams.get('justClaimed') === '1' && (
          <div style={{ background: '#dcfce7', color: '#166534', padding: '10px 24px', fontSize: 13 }}>
            🎉 You've claimed this profile! Fill in the fields below to start earning your Search Rank Score.
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 20, padding: 24, maxWidth: 1200 }}>
          <div>
            <div
              style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 20, marginBottom: 20 }}
              data-agent-target="manage-profile-details"
            >
              <h3 style={{ marginTop: 0, fontSize: 16 }}>Profile Details</h3>
              {suggestions.profile_completion.available && (
                <SuggestionCard
                  points={suggestions.profile_completion.points}
                  actionLabel="Fill it in"
                  onAction={() => scrollToAndFlash('field-license_number')}
                >
                  {suggestions.profile_completion.label} — a quick win toward your Profile Completion score.
                </SuggestionCard>
              )}
              <EditableField label="Phone Number" value={profile.phone_number} onSave={(v) => saveField('phone_number', v)} />
              <EditableField
                label="License Number"
                value={profile.license_number}
                onSave={(v) => saveField('license_number', v)}
                target="field-license_number"
              />
              <EditableField label="Website URL" value={profile.website_url} onSave={(v) => saveField('website_url', v)} />
              <EditableField label="Bio" value={profile.bio} onSave={(v) => saveField('bio', v)} multiline />
            </div>

            <div
              style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 20, marginBottom: 20 }}
              data-agent-target="manage-reviews-section"
            >
              <h3 style={{ marginTop: 0, fontSize: 16 }}>Reviews</h3>
              {suggestions.reviews.available && (
                <ReviewSuggestionCard items={suggestions.reviews.items} onReply={(reviewId) => scrollToAndFlash(`review-${reviewId}`)} />
              )}
              <ReviewReplyList profileId={profileId} reviews={profile.reviews} onReplied={reload} />
            </div>

            <div
              style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 20, marginBottom: 20 }}
              data-agent-target="manage-connections-section"
            >
              <h3 style={{ marginTop: 0, fontSize: 16 }}>Connections</h3>
              {suggestions.connections.available && (
                <SuggestionCard
                  points={suggestions.connections.points}
                  actionLabel={`Connect ${suggestions.connections.platform}`}
                  onAction={() => toggleConnection(suggestions.connections.platform, true)}
                >
                  Connect {suggestions.connections.platform} to boost your Connections score.
                </SuggestionCard>
              )}
              <ConnectionsToggleList connections={profile.connections} onToggle={toggleConnection} />
            </div>

            <div
              style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 20, marginBottom: 20 }}
              data-agent-target="manage-listings-section"
            >
              <h3 style={{ marginTop: 0, fontSize: 16 }}>Listings</h3>
              {suggestions.listings.available && (
                <SuggestionCard
                  points={suggestions.listings.points}
                  actionLabel={`Publish to ${suggestions.listings.platform}`}
                  onAction={() => toggleListing(suggestions.listings.platform, true)}
                >
                  Publish your listing on {suggestions.listings.platform} to earn more Listings points.
                </SuggestionCard>
              )}
              <DirectoryListingsSection isPro={profile.is_pro} listings={profile.directory_listings} onToggle={toggleListing} />
            </div>

            <div
              style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 20 }}
              data-agent-target="manage-analytics-section"
            >
              <h3 style={{ marginTop: 0, fontSize: 16 }}>Website Health</h3>
              {suggestions.web_analytics.available && (
                <SuggestionCard
                  points={suggestions.web_analytics.points}
                  actionLabel="Unlock with Pro"
                  onAction={() => navigate(`/dashboard/${profileId}/upgrade`)}
                >
                  Unlocking Website Health moves you from rank {suggestions.web_analytics.rank_from} to rank{' '}
                  {suggestions.web_analytics.rank_to} of {suggestions.web_analytics.rank_total} in your market.
                </SuggestionCard>
              )}
              <AnalyticsReadout isPro={profile.is_pro} websiteUrl={profile.website_url} websiteAudit={profile.website_audit} />
            </div>
          </div>

          <div>
            <ScoreBreakdownPanel score={score} totalUnlock={suggestions.total_unlock} onUnlock={() => navigate(`/dashboard/${profileId}/upgrade`)} />
            {profile.lifecycle_state !== 'pro' && (
              <ProSlotStatus
                slotStatus={data.slot_status}
                category={dashboardProfile?.category}
                location={dashboardProfile?.location}
                onUpgrade={onUpgrade}
                onStartTrial={onStartTrial}
                onJoinWaitlist={onJoinWaitlist}
                upgrading={false}
                joined={joined}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ManageProfilePage
