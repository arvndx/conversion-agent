import { useMemo, useRef } from 'react'
import PilotSay from '../pilot/PilotSay.jsx'
import PilotAction from '../pilot/PilotAction.jsx'
import { usePilotScript } from '../pilot/usePilotScript.js'
import FieldGroups from '../fields/FieldGroups.jsx'
import ProfileField from '../fields/ProfileField.jsx'
import ProfileMeter from '../fields/ProfileMeter.jsx'
import SocialLinks from './SocialLinks.jsx'
import SourceStrip from './SourceStrip.jsx'

const AI_FIELDS = ['specialities', 'bio']

// Stage "fields": everything the pages gave us, ready to edit; what wasn't found is marked, and the
// agent's drafts for the description and specialities wait for a yes. Finishing is refused while
// anything else (a card unanswered, a conflict open) is still pending.
function FieldsScene({ data, drafts, busy, agentBusy, onSave, onSaveLink, onUseDraft, onAskDraft, onFinish }) {
  const filled = data.fields.filter((f) => data.profile[f.key]).length
  const lines = useMemo(
    () => [filled > 0 ? `Here is everything I have — **${filled} of ${data.fields.length}** details. Fix anything, add what's missing, then finish.` : 'I could not find much, so these are yours to fill in. Add what you can — you can finish the rest from your dashboard.'],
    [filled, data.fields.length],
  )
  const script = usePilotScript(lines)
  const pending = useRef(new Set()) // saves still in flight: Finish waits for them
  const locked = busy || agentBusy
  const needsDraft = AI_FIELDS.some((k) => !data.profile[k] && !drafts[k])

  async function track(promise) {
    pending.current.add(promise)
    try { return await promise } finally { pending.current.delete(promise) }
  }
  const save = (key, value) => track(onSave(key, value))
  const applyDraft = (key, value) => track(onUseDraft(key, value))
  async function finish() {
    await Promise.all([...pending.current])
    onFinish()
  }

  return (
    <div className="ob-stack">
      <PilotSay script={script} eyebrow="Your details" />
      <div className="claim-card pilot-rise" style={{ padding: '22px 24px' }}>
        <ProfileMeter className="pf-meter--full" filled={filled} total={data.fields.length} />
        <FieldGroups fields={data.fields}>
          {(f) => {
            const draft = drafts[f.key]
            const value = data.profile[f.key]
            const showDraft = draft && String(draft).trim() !== (value || '').trim()
            return (
              <ProfileField
                key={f.key} fieldKey={f.key} label={f.label} value={value} wide={f.wide} inputId={`f-${f.key}`}
                autosave missingLabel="Not found yet" disabled={locked} onSave={(v) => save(f.key, v)}
              >
                {showDraft && (
                  <div className="claim-suggestion-box pilot-rise">
                    <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--brand)', marginBottom: 4 }}>✨ Suggested by Profile Pilot</div>
                    <div style={{ fontSize: 13.5, lineHeight: 1.5, marginBottom: 10 }}>{draft}</div>
                    <button className="claim-btn-primary ob-btn" disabled={locked} onClick={() => applyDraft(f.key, draft)}>Use this</button>
                  </div>
                )}
              </ProfileField>
            )
          }}
        </FieldGroups>
        <div style={{ marginTop: 26 }}><SocialLinks items={data.link_only} disabled={locked} onSave={onSaveLink} /></div>
        {needsDraft && (
          <button className="pf-ai" disabled={locked} onClick={onAskDraft}>✨ Draft my description and specialities</button>
        )}
      </div>
      {data.blockers.length > 0 && (
        <div className="pf-blockers">
          <span aria-hidden="true">⚠️</span>
          <div>
            <div className="pf-blockers__title">Before you can finish</div>
            {data.blockers.map((b) => <div key={b} className="ob-hint">• {b}</div>)}
          </div>
        </div>
      )}
      <PilotAction disabled={locked || data.blockers.length > 0} onClick={finish}>Finish onboarding →</PilotAction>
      <SourceStrip sources={data.sources} compact />
    </div>
  )
}

export default FieldsScene
