import { firstName } from './sourceMeta.js'

const STEPS = ['Your pages', 'Reading', 'Differences', 'Details', 'Done']
const STEP_OF_STAGE = {
  urls: 0, links: 1, board: 1, scraping: 1, identity: 1, merge: 1, conflicts: 2, fields: 3, completed: 4,
}

// The person, and a five-step strip showing where onboarding stands (steps before the current one are done).
function OnboardingProgress({ profile, category, stage }) {
  const step = STEP_OF_STAGE[stage] ?? 0
  const name = profile?.name || ''
  const initials = name.split(' ').map((w) => w[0]).filter(Boolean).slice(0, 2).join('') || '?'
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'linear-gradient(135deg, var(--p-2), var(--p-3))', color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 13 }}>
          {initials}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 800, fontSize: 16 }}>{name || firstName(name)}</div>
          <div style={{ fontSize: 12.5, color: 'var(--ink-soft)' }}>{[category?.name, profile?.location].filter(Boolean).join(' · ')}</div>
        </div>
        <div style={{ marginLeft: 'auto', fontSize: 11.5, fontWeight: 700, color: 'var(--success)', background: '#ecfdf3', borderRadius: 999, padding: '3px 10px', whiteSpace: 'nowrap' }}>
          ✓ Claimed
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {STEPS.map((label, i) => {
          const done = i < step
          const active = i === step
          return (
            <div key={label} style={{ flex: 1 }}>
              <div
                className={active ? 'pilot-step-ring' : undefined}
                style={{ height: 6, borderRadius: 999, transition: 'background 0.3s ease', background: done || active ? 'linear-gradient(90deg, var(--p-2), var(--p-3))' : '#e6e3f1', opacity: done ? 0.55 : 1 }}
              />
              <div style={{ fontSize: 11, fontWeight: active ? 800 : 600, marginTop: 5, color: active ? 'var(--ink)' : 'var(--ink-soft)' }}>{done ? '✓ ' : ''}{label}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default OnboardingProgress
