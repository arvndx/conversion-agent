import PilotOrb from './PilotOrb.jsx'
import { PilotStream } from './pilotText.jsx'

// The assistant's signature voice card: orb + name, one line at a time (typed), an optional
// sub-line and an optional action. Pass a `script` (from usePilotScript) for a typed sequence, or
// `children` for static text. Clicking the card skips the typing.
function PilotSay({ script, children, eyebrow, tone = 'default', sub, action, label = 'Profile Pilot' }) {
  return (
    <div
      className={`pilot-bubble pilot-rise${tone === 'milestone' ? ' pilot-bubble--milestone' : ''}`}
      style={{ padding: '18px 20px', textAlign: 'left', cursor: script?.typing ? 'pointer' : 'default' }}
      onClick={script?.typing ? script.settle : undefined}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
        <PilotOrb size={28} />
        <span style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--ink-soft)' }}>
          {label}
        </span>
        {eyebrow && <span className="pilot-eyebrow" style={{ marginLeft: 'auto' }}>{eyebrow}</span>}
      </div>
      <p className={`pilot-voice${script && script.line.length > 150 ? ' pilot-voice--long' : ''}`} aria-live="polite">
        {script ? (
          <PilotStream key={`${script.index}:${script.line}`} text={script.line} caret={script.typing} complete={!script.typing} onDone={script.settle} />
        ) : (
          children
        )}
      </p>
      {sub && <p className="pilot-voice-sub">{sub}</p>}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  )
}

export default PilotSay
