import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar.jsx'
import AppTopBar from '../components/layout/AppTopBar.jsx'
import { getDashboard, joinWaitlist, startTrial, upgradeToPro } from '../api/dashboard.js'
import { getPricing, trackPricingVisit } from '../api/pricing.js'
import { useActiveProfile } from '../context/ActiveProfileContext.jsx'

function PricingStyles() {
  return (
    <style>{`
      .pricing-hero {
        background: radial-gradient(circle at 20% 20%, rgba(124,92,255,0.16), transparent 55%),
                    linear-gradient(160deg, #1b1533, #100c24);
        color: #fff;
        border-radius: 20px;
        padding: 36px 34px;
        position: relative;
        overflow: hidden;
      }
      .pricing-feature-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 0;
        border-bottom: 1px solid var(--border);
      }
      .pricing-feature-row:last-child { border-bottom: none; }
      .pricing-price-card {
        background: #fff;
        border-radius: 20px;
        box-shadow: 0 1px 2px rgba(16,24,40,0.04), 0 12px 36px rgba(16,24,40,0.1);
        padding: 28px;
      }
    `}</style>
  )
}

function PricingPage() {
  const { profileId } = useParams()
  const navigate = useNavigate()
  const { setActiveProfileId } = useActiveProfile()
  const [pricing, setPricing] = useState(null)
  const [dashboardProfile, setDashboardProfile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [joined, setJoined] = useState(false)

  useEffect(() => {
    setActiveProfileId(profileId)
    trackPricingVisit(profileId).then(() => getPricing(profileId)).then(setPricing)
    getDashboard(profileId).then((d) => setDashboardProfile(d.profile))
  }, [profileId])

  if (!pricing || !dashboardProfile) return null

  const offer = pricing.offer
  const discountedPrice = offer.active ? (pricing.monthly_price_usd * (1 - offer.percent / 100)).toFixed(2) : null
  const slot = pricing.slot_status
  const webCat = pricing.categories?.web_analytics
  const listingsCat = pricing.categories?.listings

  async function onSubscribe() {
    setBusy(true)
    try {
      await upgradeToPro(profileId)
      navigate(`/dashboard/${profileId}?justUpgraded=1`)
    } catch (err) {
      if (err.status !== 403) throw err
      const refreshed = await getPricing(profileId)
      setPricing(refreshed)
    } finally {
      setBusy(false)
    }
  }

  async function onStartTrial() {
    setBusy(true)
    try {
      await startTrial(profileId)
      navigate(`/dashboard/${profileId}?justUpgraded=1`)
    } catch (err) {
      if (err.status !== 403) throw err
      const refreshed = await getPricing(profileId)
      setPricing(refreshed)
    } finally {
      setBusy(false)
    }
  }

  async function onJoinWaitlist() {
    await joinWaitlist(profileId)
    setJoined(true)
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f7f7fb' }}>
      <PricingStyles />
      <Sidebar profileId={profileId} onboarding={null} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <AppTopBar title="Upgrade to Pro" currentProfile={dashboardProfile} />

        {pricing.is_pro ? (
          <div style={{ maxWidth: 640, margin: '60px auto', padding: '0 24px' }}>
            <div className="pricing-hero" style={{ textAlign: 'center' }} data-agent-target="pricing-card">
              <div style={{ fontSize: 44, marginBottom: 8 }}>👑</div>
              <h2 style={{ margin: '0 0 6px' }}>You're already Pro!</h2>
              <p style={{ color: '#d6d3f0', margin: 0 }}>All 5 categories are unlocked on your profile.</p>
            </div>
          </div>
        ) : (
          <div style={{ maxWidth: 1040, margin: '0 auto', padding: '32px 24px', display: 'grid', gridTemplateColumns: '1fr 380px', gap: 28 }}>
            <div>
              <div className="pricing-hero" style={{ marginBottom: 24 }} data-agent-target="pricing-card-hero">
                <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1, color: '#b9adff', textTransform: 'uppercase', marginBottom: 10 }}>
                  ClearRank Pro
                </div>
                <h1 style={{ fontSize: 30, margin: '0 0 10px', fontWeight: 800 }}>
                  Unlock {pricing.unlock_points > 0 ? `${pricing.unlock_points} real points` : 'your full score'}
                </h1>
                <p style={{ color: '#d6d3f0', fontSize: 14.5, margin: 0, maxWidth: 480, lineHeight: 1.55 }}>
                  Currently locked on your profile — Website Health and Listings only unlock once you're Pro (or on
                  a free trial).
                </p>

                {pricing.rank_preview && (
                  <div
                    style={{
                      marginTop: 20,
                      background: 'rgba(255,255,255,0.08)',
                      border: '1px solid rgba(255,255,255,0.15)',
                      borderRadius: 12,
                      padding: '12px 16px',
                      fontSize: 14,
                    }}
                  >
                    📈 Unlocking Pro moves you from rank <strong>{pricing.rank_preview.rank_from}</strong> to rank{' '}
                    <strong style={{ color: '#a7f3d0' }}>{pricing.rank_preview.rank_to}</strong> of{' '}
                    {pricing.rank_preview.rank_total} {pricing.category} pros in {pricing.location}.
                  </div>
                )}
              </div>

              <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 16, padding: '8px 20px' }}>
                {webCat && (
                  <div className="pricing-feature-row">
                    <span style={{ fontSize: 20 }}>🌐</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: 14 }}>Website Health audit</div>
                      <div style={{ fontSize: 12.5, color: 'var(--ink-soft)' }}>
                        Load time, mobile-friendliness, contact info, meta description, hours
                      </div>
                    </div>
                    <div style={{ fontWeight: 800, color: 'var(--success)', fontSize: 14 }}>+{webCat.earned} pts</div>
                  </div>
                )}
                {listingsCat && (
                  <div className="pricing-feature-row">
                    <span style={{ fontSize: 20 }}>📍</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: 14 }}>Listings management</div>
                      <div style={{ fontSize: 12.5, color: 'var(--ink-soft)' }}>
                        Publish across Google, Yelp, Facebook, Apple Maps, Voice Search
                      </div>
                    </div>
                    <div style={{ fontWeight: 800, color: 'var(--success)', fontSize: 14 }}>+{listingsCat.earned} pts</div>
                  </div>
                )}
                <div className="pricing-feature-row">
                  <span style={{ fontSize: 20 }}>🎯</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>Live what-if score simulator</div>
                    <div style={{ fontSize: 12.5, color: 'var(--ink-soft)' }}>See your real projected score before you commit to any change</div>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <div className="pricing-price-card" data-agent-target="pricing-card" style={{ position: 'sticky', top: 24 }}>
                {offer.active && (
                  <div
                    style={{
                      background: 'linear-gradient(135deg, #fff7ed, #ffedd5)',
                      border: '1px solid #fed7aa',
                      color: '#9a3412',
                      borderRadius: 10,
                      padding: '10px 14px',
                      fontSize: 12.5,
                      fontWeight: 700,
                      marginBottom: 18,
                      textAlign: 'center',
                    }}
                  >
                    🎉 {offer.percent}% off with code {offer.code} — expires {new Date(offer.expires_at).toLocaleDateString()}
                  </div>
                )}

                {slot && (
                  <div
                    style={{
                      textAlign: 'center',
                      fontSize: 12,
                      fontWeight: 700,
                      borderRadius: 999,
                      padding: '5px 12px',
                      marginBottom: 16,
                      display: 'inline-block',
                      width: '100%',
                      boxSizing: 'border-box',
                      background: slot.is_full ? '#111827' : slot.remaining <= 1 ? '#fef2f2' : 'var(--surface-muted)',
                      color: slot.is_full ? '#fff' : slot.remaining <= 1 ? '#b91c1c' : 'var(--ink-soft)',
                    }}
                  >
                    {slot.is_full
                      ? `🔒 All ${slot.total} Pro spots taken in your market`
                      : slot.remaining <= 1
                        ? `🔥 Only ${slot.remaining} spot left in your market`
                        : `${slot.taken} of ${slot.total} Pro spots taken in your market`}
                  </div>
                )}

                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 13, color: 'var(--ink-soft)', fontWeight: 700 }}>ClearRank Pro</div>
                  {offer.active ? (
                    <div style={{ margin: '6px 0' }}>
                      <span style={{ fontSize: 18, color: 'var(--ink-soft)', textDecoration: 'line-through', marginRight: 6 }}>
                        ${pricing.monthly_price_usd}
                      </span>
                      <span style={{ fontSize: 38, fontWeight: 800 }}>${discountedPrice}</span>
                      <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}>/month</span>
                    </div>
                  ) : (
                    <div style={{ margin: '6px 0' }}>
                      <span style={{ fontSize: 38, fontWeight: 800 }}>${pricing.monthly_price_usd}</span>
                      <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}>/month</span>
                    </div>
                  )}
                </div>

                {slot?.is_full ? (
                  <button
                    onClick={onJoinWaitlist}
                    disabled={joined}
                    className={joined ? 'agent-btn-secondary' : 'agent-btn-primary'}
                    style={{ width: '100%', padding: '13px 0', fontSize: 14, marginTop: 18 }}
                  >
                    {joined ? "You're on the waitlist" : 'Join Waitlist'}
                  </button>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 18 }}>
                    <button
                      onClick={onSubscribe}
                      disabled={busy}
                      className="agent-btn-primary"
                      style={{ width: '100%', padding: '13px 0', fontSize: 14, background: 'linear-gradient(135deg, #f59e0b, #d97706)' }}
                    >
                      👑 Subscribe to Pro
                    </button>
                    <button onClick={onStartTrial} disabled={busy} className="agent-btn-secondary" style={{ width: '100%', padding: '13px 0', fontSize: 14 }}>
                      Start Free Trial
                    </button>
                  </div>
                )}

                <button
                  onClick={() => navigate(-1)}
                  disabled={busy}
                  style={{
                    marginTop: 14,
                    width: '100%',
                    background: 'none',
                    color: 'var(--ink-soft)',
                    border: 'none',
                    fontSize: 12.5,
                    fontWeight: 600,
                    cursor: busy ? 'default' : 'pointer',
                    textDecoration: 'underline',
                  }}
                >
                  ← Upgrade later
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default PricingPage
