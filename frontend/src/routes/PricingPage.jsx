import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar.jsx'
import AppTopBar from '../components/layout/AppTopBar.jsx'
import { getDashboard, joinWaitlist, startTrial, upgradeToPro } from '../api/dashboard.js'
import { getPricing, trackPricingVisit } from '../api/pricing.js'
import { errorMessage } from '../api/client.js'
import { useActiveProfile } from '../context/ActiveProfileContext.jsx'

function PricingPage() {
  const { profileId } = useParams()
  const navigate = useNavigate()
  const { setActiveProfileId } = useActiveProfile()
  const [pricing, setPricing] = useState(null)
  const [dashboardProfile, setDashboardProfile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [joined, setJoined] = useState(false)
  const [actionError, setActionError] = useState(null)
  const trackedFor = useRef(null)

  useEffect(() => {
    setActiveProfileId(profileId)
    // A 401 is the client's sign-in redirect; any other failure (not claimed, not found) goes back to the profile.
    const failed = (e) => e.status !== 401 && navigate(`/profile/${profileId}`, { replace: true })
    // One visit per time the page is opened (React runs this effect twice in development; that must not count twice).
    const first = trackedFor.current !== profileId
    trackedFor.current = profileId
    ;(first ? trackPricingVisit(profileId) : Promise.resolve()).then(() => getPricing(profileId)).then(setPricing).catch(failed)
    getDashboard(profileId).then((d) => setDashboardProfile(d.profile)).catch(failed)
  }, [profileId])

  if (!pricing || !dashboardProfile) return null

  const offer = pricing.offer
  const discountedPrice = offer.active ? (pricing.monthly_price_usd * (1 - offer.percent / 100)).toFixed(2) : null
  const slot = pricing.slot_status
  const webCat = pricing.categories?.web_analytics
  const listingsCat = pricing.categories?.listings
  // Whatever the category locks behind Pro (Insurance, for one, has Listings in its free sections).
  const lockedLabels = Object.values(pricing.categories || {}).filter((c) => c.locked).map((c) => c.label)

  // Subscribe or start a trial. A refusal (the market just filled, a trial is already running) refreshes what the
  // page shows and says why, instead of failing silently.
  async function purchase(action) {
    setBusy(true)
    setActionError(null)
    try {
      await action(profileId)
      navigate(`/dashboard/${profileId}?justUpgraded=1`)
    } catch (err) {
      if (err.status === 401) return
      setActionError(err.status === 403 ? 'The last Pro spot was just taken. You can join the waitlist.' : errorMessage(err))
      getPricing(profileId).then(setPricing).catch(() => {})
    } finally {
      setBusy(false)
    }
  }
  const onSubscribe = () => purchase(upgradeToPro)
  const onStartTrial = () => purchase(startTrial)

  async function onJoinWaitlist() {
    await joinWaitlist(profileId)
    setJoined(true)
  }

  const unlockedEarned = Object.values(pricing.categories || {}).filter((c) => !c.locked).reduce((sum, c) => sum + c.earned, 0)
  const preview = pricing.rank_preview && pricing.rank_preview.rank_to < pricing.rank_preview.rank_from ? pricing.rank_preview : null

  return (
    <div className="owner-shell">
      <Sidebar profileId={profileId} onboarding={null} />
      <div className="app-main">
        <AppTopBar title="Upgrade to Pro" currentProfile={dashboardProfile} />

        {pricing.is_pro ? (
          <div style={{ maxWidth: 680, margin: '60px auto', padding: '0 24px' }}>
            <div className="price-hero price-hero--center" data-agent-target="pricing-card">
              <div style={{ fontSize: 52, marginBottom: 10 }}>👑</div>
              <h1>You&apos;re already <em>Pro</em></h1>
              <p>All {Object.keys(pricing.categories || {}).length} score sections are unlocked on your profile.</p>
            </div>
          </div>
        ) : (
          <div className="owner-grid owner-grid--pricing">
            <div className="stack">
              <div className="price-hero" data-agent-target="pricing-card-hero">
                <div className="price-hero__eyebrow">👑 ClearRank Pro</div>
                <h1>Unlock {pricing.unlock_points > 0 ? <><em>{pricing.unlock_points} real points</em></> : 'your full score'}</h1>
                <p>
                  Currently locked on your profile — {lockedLabels.join(' and ') || 'nothing'} only unlock once you&apos;re Pro
                  (or on a free trial).
                </p>

                {(preview || pricing.unlock_points > 0) && (
                  <div className="before-after">
                    {pricing.unlock_points > 0 && (
                      <>
                        <div className="ba-tile"><small>Your score</small><b>{unlockedEarned}</b></div>
                        <span className="ba-arrow" aria-hidden="true">→</span>
                        <div className="ba-tile ba-tile--good"><small>With Pro</small><b>{unlockedEarned + pricing.unlock_points}</b></div>
                      </>
                    )}
                    {preview && (
                      <div className="ba-tile ba-tile--good" style={{ flexBasis: 240 }}>
                        <small>Your rank</small>
                        <b>{preview.rank_from} → {preview.rank_to} <span>of {preview.rank_total}</span></b>
                        <div style={{ fontSize: 12.5, color: '#b9b4dd', marginTop: 4 }}>{pricing.category} pros in {pricing.location}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="feature-grid">
                {webCat?.locked && (
                  <div className="feature">
                    <span className="feature__icon" style={{ background: '#e3eeff' }}>🌐</span>
                    <div>
                      <h3>Website Health audit</h3>
                      <p>Load time, mobile-friendliness, contact info, meta description, hours</p>
                    </div>
                    <span className="feature__pts">{webCat.earned > 0 ? `+${webCat.earned} pts` : `up to ${webCat.max} pts`}</span>
                  </div>
                )}
                {listingsCat?.locked && (
                  <div className="feature">
                    <span className="feature__icon" style={{ background: '#ffeedd' }}>📍</span>
                    <div>
                      <h3>Listings management</h3>
                      <p>Publish across the directories that matter for your category</p>
                    </div>
                    <span className="feature__pts">{listingsCat.earned > 0 ? `+${listingsCat.earned} pts` : `up to ${listingsCat.max} pts`}</span>
                  </div>
                )}
                <div className="feature">
                  <span className="feature__icon" style={{ background: '#efecff' }}>🎯</span>
                  <div>
                    <h3>Live what-if score simulator</h3>
                    <p>See your real projected score before you commit to any change</p>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <div className="price-card" data-agent-target="pricing-card">
                {offer.active && (
                  <div className="offer-banner">🎉 {offer.percent}% off with code {offer.code} — expires {new Date(offer.expires_at).toLocaleDateString()}</div>
                )}

                {slot && (
                  <>
                    <div className="slot-head">
                      <b>Pro spots in your market</b>
                      <span style={{ whiteSpace: 'nowrap', color: 'var(--ink-soft)', fontWeight: 600 }}>{slot.taken} of {slot.total} taken</span>
                    </div>
                    <div className="slot-dots" aria-hidden="true">
                      {Array.from({ length: slot.total }, (_, i) => <i key={i} className={i < slot.taken ? 'on' : ''} />)}
                    </div>
                    <div className={`callout ${slot.is_full ? 'callout--dark' : slot.remaining <= 1 ? 'callout--warm' : 'callout--soft'}`}>
                      {slot.is_full
                        ? `🔒 All ${slot.total} Pro spots taken in your market`
                        : slot.remaining <= 1
                          ? `🔥 Only ${slot.remaining} spot left in your market`
                          : `✨ ${slot.remaining} spots left in your market`}
                    </div>
                  </>
                )}

                <div className="price">
                  <small>ClearRank Pro</small>
                  {offer.active ? (
                    <div><s>${pricing.monthly_price_usd}</s><b>${discountedPrice}</b><span>/month</span></div>
                  ) : (
                    <div><b>${pricing.monthly_price_usd}</b><span>/month</span></div>
                  )}
                </div>

                <ul className="perk-list">
                  {lockedLabels.map((label) => <li key={label}>{label} unlocked</li>)}
                  <li>Up to {pricing.unlock_points} more score points</li>
                  <li>Move up in your market&apos;s ranking</li>
                </ul>

                {slot?.is_full ? (
                  <button onClick={onJoinWaitlist} disabled={joined} className={`btn btn--lg btn--block ${joined ? 'btn--ghost' : 'btn--primary'}`}>
                    {joined ? "You're on the waitlist" : 'Join Waitlist'}
                  </button>
                ) : (
                  <div style={{ display: 'grid', gap: 10 }}>
                    <button onClick={onSubscribe} disabled={busy} className="btn btn--pro btn--lg btn--block">👑 Subscribe to Pro</button>
                    {!slot?.is_trial && (
                      <button onClick={onStartTrial} disabled={busy} className="btn btn--outline btn--lg btn--block">Start Free Trial</button>
                    )}
                    {slot?.is_trial && <div className="panel__sub" style={{ textAlign: 'center' }}>Your free trial is running.</div>}
                    {actionError && <div role="alert" className="error-text">{actionError}</div>}
                  </div>
                )}

                <div style={{ textAlign: 'center', marginTop: 14 }}>
                  <button className="text-btn" onClick={() => navigate(-1)} disabled={busy}>← Upgrade later</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default PricingPage
