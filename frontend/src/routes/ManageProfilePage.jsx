import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar.jsx'
import AppTopBar from '../components/layout/AppTopBar.jsx'
import PromoBanner from '../components/layout/PromoBanner.jsx'
import FieldGroups from '../components/fields/FieldGroups.jsx'
import ProfileField from '../components/fields/ProfileField.jsx'
import ProfileMeter from '../components/fields/ProfileMeter.jsx'
import Panel from '../components/shared/Panel.jsx'
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
      .catch((e) => e.status !== 401 && setError('not-claimed'))
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

  const { profile, score, suggestions, fields, slots } = data
  const filledFields = fields.filter((f) => profile[f.key]).length

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
    <div className="owner-shell">
      <Sidebar profileId={profileId} onboarding={null} />

      <div className="app-main">
        <PromoBanner />
        <AppTopBar
          title="Manage Profile"
          currentProfile={dashboardProfile}
          actions={
            profile.lifecycle_state !== 'pro' && (
              <button className="btn btn--pro btn--sm" onClick={() => navigate(`/dashboard/${profileId}/upgrade`)} data-agent-target="manage-upgrade-button">
                👑 Upgrade to Pro
              </button>
            )
          }
        />

        {searchParams.get('justClaimed') === '1' && (
          <div className="notice notice--ok">
            🎉 Your profile is set up. Here is where you raise your Search Rank Score — a quick tour starts now.
          </div>
        )}

        <div className="owner-grid owner-grid--manage">
          <div className="stack">
            <Panel
              icon="👤" title="Profile Details" subtitle="What searchers see, and what your Profile Completion score reads."
              target="manage-profile-details" aside={<ProfileMeter filled={filledFields} total={fields.length} />}
            >
              {suggestions.profile_completion.available && (
                <SuggestionCard
                  points={suggestions.profile_completion.points}
                  actionLabel="Fill it in"
                  onAction={() => scrollToAndFlash(`field-${suggestions.profile_completion.field}`)}
                >
                  {suggestions.profile_completion.label} — a quick win toward your Profile Completion score.
                </SuggestionCard>
              )}
              <FieldGroups fields={[{ key: 'phone_number', label: 'Phone Number' }, ...fields]}>
                {(f) => (
                  <ProfileField
                    key={f.key} fieldKey={f.key} label={f.label} value={profile[f.key]} wide={f.wide} inputId={`mf-${f.key}`}
                    target={f.key === 'phone_number' ? undefined : `field-${f.key}`}
                    onSave={(v) => saveField(f.key, v)}
                  />
                )}
              </FieldGroups>
            </Panel>

            <Panel icon="💬" tint="#e6f7ec" title="Reviews" subtitle="Reply to every review to earn Reviews & Replies points." target="manage-reviews-section">
              {suggestions.reviews.available && (
                <ReviewSuggestionCard items={suggestions.reviews.items} onReply={(reviewId) => scrollToAndFlash(`review-${reviewId}`)} />
              )}
              <ReviewReplyList profileId={profileId} reviews={profile.reviews} onReplied={reload} />
            </Panel>

            <Panel icon="🔗" tint="#dff6f2" title="Connections" subtitle="Link the profiles customers already use." target="manage-connections-section">
              {suggestions.connections.available && (
                <SuggestionCard
                  points={suggestions.connections.points}
                  actionLabel={`Connect ${suggestions.connections.platform}`}
                  onAction={() => toggleConnection(suggestions.connections.platform, true)}
                >
                  Connect {suggestions.connections.platform} to boost your Connections score.
                </SuggestionCard>
              )}
              <ConnectionsToggleList connections={profile.connections} slots={slots?.social} onToggle={toggleConnection} />
            </Panel>

            <Panel icon="📍" tint="#ffeedd" title="Listings" subtitle="Be found in the directories that matter for your category." target="manage-listings-section">
              {suggestions.listings.available && (
                <SuggestionCard
                  points={suggestions.listings.points}
                  actionLabel={`Publish to ${suggestions.listings.platform}`}
                  onAction={() => toggleListing(suggestions.listings.platform, true)}
                >
                  Publish your listing on {suggestions.listings.platform} to earn more Listings points.
                </SuggestionCard>
              )}
              <DirectoryListingsSection locked={Boolean(score.categories.listings?.locked)} slots={slots?.directory} listings={profile.directory_listings} onToggle={toggleListing} />
            </Panel>

            <Panel icon="🌐" tint="#e3eeff" title="Website Health" subtitle="How your site looks to search engines and visitors." target="manage-analytics-section">
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
            </Panel>
          </div>

          <div className="stack">
            <ScoreBreakdownPanel score={score} totalUnlock={suggestions.total_unlock} onUnlock={() => navigate(`/dashboard/${profileId}/upgrade`)} />
            {!['pro', 'enterprise'].includes(profile.lifecycle_state) && (
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
