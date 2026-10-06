import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PilotOrb from '../pilot/PilotOrb.jsx'
import AgentVoice from './AgentVoice.jsx'
import { getImprovementPlan } from '../../api/dashboard.js'
import { firstName } from './sourceMeta.js'

const KIND_ICON = { reply_review: '💬', fill_field: '✏️', connect: '🔗', publish_listing: '📍' }

// A number that counts up to its value, so the first score feels earned.
function useCountUp(target, ms = 1100) {
  const [n, setN] = useState(0)
  useEffect(() => {
    let raf
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min(1, (now - start) / ms)
      setN(Math.round(target * (1 - (1 - t) ** 3)))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return n
}

// The score as a ring that fills, with the number counting up in the middle.
function ScoreRing({ score, max, size = 190, label = 'Search Rank Score' }) {
  const shown = useCountUp(score)
  const r = 78
  const C = 2 * Math.PI * r
  const [filled, setFilled] = useState(0)
  useEffect(() => {
    const t = setTimeout(() => setFilled(Math.min(1, score / (max || 1))), 120)
    return () => clearTimeout(t)
  }, [score, max])
  return (
    <div className="dn-ring" style={{ width: size, height: size }}>
      <svg viewBox="0 0 190 190" width={size} height={size} role="img" aria-label={`${label} ${score} of ${max}`}>
        <defs>
          <linearGradient id="dnRing" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#8f74ff" /><stop offset="55%" stopColor="#4527d1" /><stop offset="100%" stopColor="#ec4899" />
          </linearGradient>
        </defs>
        <circle cx="95" cy="95" r={r} fill="none" stroke="#ece9fb" strokeWidth="16" />
        <circle cx="95" cy="95" r={r} fill="none" stroke="url(#dnRing)" strokeWidth="16" strokeLinecap="round"
          strokeDasharray={`${filled * C} ${C}`} transform="rotate(-90 95 95)" style={{ transition: 'stroke-dasharray 1.2s cubic-bezier(0.2, 0.8, 0.2, 1)' }} />
      </svg>
      <div className="dn-ring__mid">
        <b>{shown}</b>
        <span>of {max}</span>
      </div>
    </div>
  )
}

// Everyone in the market as a dot, you highlighted: your place at a glance.
function RankDots({ position, total, to = null }) {
  const n = Math.min(total, 40)
  return (
    <div className="dn-dots" aria-hidden="true">
      {Array.from({ length: n }, (_, i) => {
        const place = i + 1
        const cls = place === position ? 'dn-dot dn-dot--you' : to && place === to ? 'dn-dot dn-dot--to' : place < position ? 'dn-dot dn-dot--ahead' : 'dn-dot'
        return <i key={i} className={cls} style={{ animationDelay: `${i * 18}ms` }} />
      })}
    </div>
  )
}

function SlideScore({ plan, location, voice, name }) {
  return (
    <div className="dn-slide">
      <h2 className="dn-title">You&apos;re set up, {firstName(name)} 🎉</h2>
      <div className="dn-hero">
        <ScoreRing score={plan.score.total} max={plan.score.max_possible} />
        <div className="dn-rank">
          <div className="dn-rank__label">Your rank{location ? ` in ${location}` : ''}</div>
          <div className="dn-rank__num">#{plan.rank.rank_position}<small> of {plan.rank.rank_total}</small></div>
          <RankDots position={plan.rank.rank_position} total={plan.rank.rank_total} />
          <div className="dn-rank__note">{plan.rank.rank_position - 1 === 0 ? 'You are #1 in your market.' : `${plan.rank.rank_position - 1} ${plan.rank.rank_position - 1 === 1 ? 'pro is' : 'pros are'} ahead of you.`}</div>
        </div>
      </div>
      {voice && <AgentVoice text={voice} clamp />}
    </div>
  )
}

function SlideSteps({ plan }) {
  const steps = plan.items.slice(0, 4)
  const top = Math.max(...steps.map((s) => s.points), 1)
  const projected = Math.min(plan.score.max_possible, plan.score.total + plan.reachable_points)
  return (
    <div className="dn-slide">
      <h2 className="dn-title">Your fastest ways to climb</h2>
      <div className="dn-steps">
        {steps.map((s, i) => (
          <div key={s.key} className="dn-step" style={{ animationDelay: `${i * 90}ms` }}>
            <span className="dn-step__icon">{KIND_ICON[s.kind] || '•'}</span>
            <div className="dn-step__main">
              <div className="dn-step__label">{s.label}</div>
              <div className="dn-step__bar"><i style={{ width: `${Math.max(12, (s.points / top) * 100)}%` }} /></div>
            </div>
            <b className="dn-step__pts">+{s.points}</b>
          </div>
        ))}
      </div>
      <div className="dn-total">
        <span>Do them all</span>
        <b>+{plan.reachable_points} points</b>
        <span>→ about {projected} / {plan.score.max_possible}</span>
      </div>
    </div>
  )
}

function SlidePro({ plan, profileId }) {
  const navigate = useNavigate()
  const pro = plan.pro
  const moves = pro.points_gained > 0
  const proMax = plan.score.max_possible + pro.locked_sections.reduce((n, s) => n + s.max, 0)
  return (
    <div className="dn-slide">
      <h2 className="dn-title">What Pro would do</h2>
      {moves ? (
        <>
          <div className="dn-compare">
            <div className="dn-compare__col">
              <small>Now</small>
              <b>{pro.score_before}</b>
              <div className="dn-bar"><i style={{ width: `${(pro.score_before / proMax) * 100}%` }} /></div>
              <span>Rank #{pro.rank_before}</span>
            </div>
            <span className="dn-compare__arrow" aria-hidden="true">→</span>
            <div className="dn-compare__col dn-compare__col--pro">
              <small>With Pro</small>
              <b>{pro.score_after}</b>
              <div className="dn-bar dn-bar--pro"><i style={{ width: `${Math.min(100, (pro.score_after / proMax) * 100)}%` }} /></div>
              <span>Rank #{pro.rank_after}</span>
            </div>
          </div>
          <RankDots position={pro.rank_before} total={pro.rank_total} to={pro.rank_after} />
          <div className="dn-total"><b>+{pro.points_gained} points</b><span>from {pro.locked_sections.map((s) => s.label).join(' and ')}</span></div>
        </>
      ) : (
        <div className="dn-note">Pro wouldn&apos;t change your score yet: {pro.locked_sections.map((s) => s.label).join(' and ')} haven&apos;t earned points so far.</div>
      )}
      <div className="dn-slots">
        <div className="slot-dots" aria-hidden="true">
          {Array.from({ length: pro.slots.total }, (_, i) => <i key={i} className={i < pro.slots.total - pro.slots.remaining ? 'on' : ''} />)}
        </div>
        <span>{pro.slots.remaining} of {pro.slots.total} Pro spots open in your market</span>
      </div>
      <button className="btn btn--pro" onClick={() => navigate(`/dashboard/${profileId}/upgrade`)}>{pro.slots.is_full ? 'See Pro (join the waitlist)' : 'See Pro →'}</button>
    </div>
  )
}

// Onboarding is finished (core1 Process 3): the first real score and rank, what would raise the score with each
// step's points, and the real Pro before/after, one slide at a time, then the guided tour.
function DoneScene({ profileId, name, location, voice }) {
  const navigate = useNavigate()
  const [plan, setPlan] = useState(null)
  const [slide, setSlide] = useState(0)
  useEffect(() => {
    getImprovementPlan(profileId).then(setPlan).catch(() => setPlan(null))
  }, [profileId])

  const slides = plan ? ['score', plan.items.length > 0 && 'steps', plan.pro?.available && 'pro'].filter(Boolean) : []
  const key = slides[Math.min(slide, slides.length - 1)]
  const last = slide >= slides.length - 1

  return (
    <div className="dn">
      {!plan ? (
        <div className="dn-slide" style={{ justifyItems: 'center' }}>
          <PilotOrb size={72} flyIn />
          <h2 className="dn-title">You&apos;re set up, {firstName(name)}</h2>
          <div className="pilot-shimmer" style={{ height: 12, width: 220 }} />
        </div>
      ) : (
        <>
          {key === 'score' && <SlideScore plan={plan} location={location} voice={voice} name={name} />}
          {key === 'steps' && <SlideSteps plan={plan} />}
          {key === 'pro' && <SlidePro plan={plan} profileId={profileId} />}
          <div className="dn-nav">
            <div className="dn-nav__dots">{slides.map((s, i) => <button key={s} aria-label={`Slide ${i + 1}`} className={i === slide ? 'on' : ''} onClick={() => setSlide(i)} />)}</div>
            {slide > 0 && <button className="btn btn--ghost btn--sm" onClick={() => setSlide(slide - 1)}>← Back</button>}
            {!last ? (
              <button className="btn btn--primary btn--sm" onClick={() => setSlide(slide + 1)}>Next →</button>
            ) : (
              <>
                <button className="btn btn--ghost btn--sm" onClick={() => navigate(`/dashboard/${profileId}`)}>Go to my dashboard</button>
                <button className="btn btn--primary btn--sm" onClick={() => navigate(`/dashboard/${profileId}/manage?justClaimed=1`)}>Take the quick tour →</button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default DoneScene
