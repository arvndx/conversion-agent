import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import TopNav from '../components/layout/TopNav.jsx'
import CelebrationOverlay from '../components/agent/CelebrationOverlay.jsx'
import AgentMessageBubble from '../components/agent/AgentMessageBubble.jsx'
import TypingIndicator from '../components/agent/TypingIndicator.jsx'
import { getProfile, submitClaimDetails } from '../api/profiles.js'
import { greetAgent, sendAgentMessage } from '../api/agent.js'
import { CLAIM_FIELDS, CLAIM_PAGE_COUNT, fieldsForPage } from '../constants/claimFields.js'
import { suggestPlaces } from '../constants/usPlaces.js'

const MANDATORY_KEYS = ['name', 'email', 'phone_number']

function toggleQuickPick(value, pick) {
  const items = value
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean)
  const next = items.includes(pick) ? items.filter((v) => v !== pick) : [...items, pick]
  return next.join(', ')
}

const FIELD_ICONS = {
  name: '👤',
  email: '✉️',
  phone_number: '📞',
  location: '📍',
  title: '💼',
  business_timing: '🕒',
  service_area: '🗺️',
  website_url: '🌐',
  license_number: '📜',
  products_services: '🛠️',
  specialities: '⭐',
  memberships: '🏅',
  year_started: '📅',
  awards: '🏆',
  achievements: '🎯',
  hobbies: '🎨',
  bio: '📝',
}

// Injected once — hover/focus states need real CSS (inline styles can't express :hover /
// :focus), and this keeps every component below free of onMouseEnter/onMouseLeave plumbing.
function ClaimWizardStyles() {
  return (
    <style>{`
      .claim-card {
        background: #fff;
        border-radius: 18px;
        box-shadow: 0 1px 2px rgba(16,24,40,0.04), 0 8px 28px rgba(16,24,40,0.07);
        padding: 28px 30px;
      }
      .claim-input {
        width: 100%;
        border: 1.5px solid var(--border);
        border-radius: 10px;
        padding: 10px 13px;
        font-size: 14px;
        font-family: inherit;
        background: #fff;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
        outline: none;
        box-sizing: border-box;
      }
      .claim-input:hover { border-color: #c7c9f5; }
      .claim-input:focus { border-color: var(--brand); box-shadow: 0 0 0 3.5px rgba(99, 91, 255, 0.13); }
      .claim-btn-primary {
        background: linear-gradient(135deg, #7c5cff, var(--brand));
        color: #fff;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        cursor: pointer;
        transition: transform 0.12s ease, box-shadow 0.12s ease, opacity 0.12s ease;
        box-shadow: 0 2px 8px rgba(99, 91, 255, 0.32);
      }
      .claim-btn-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(99, 91, 255, 0.4); }
      .claim-btn-primary:active:not(:disabled) { transform: translateY(0); }
      .claim-btn-primary:disabled { opacity: 0.5; cursor: default; transform: none; }
      .claim-btn-secondary {
        background: #fff;
        color: var(--ink);
        border: 1.5px solid var(--border);
        border-radius: 10px;
        font-weight: 600;
        cursor: pointer;
        transition: border-color 0.12s ease, background 0.12s ease;
      }
      .claim-btn-secondary:hover:not(:disabled) { border-color: var(--brand); background: #faf9ff; }
      .claim-suggestion-box {
        border: 1.5px solid #e0d9ff;
        border-radius: 12px;
        padding: 12px 14px;
        background: linear-gradient(135deg, #f8f6ff, #f0edff);
        position: relative;
        overflow: hidden;
      }
      .claim-suggestion-box::before {
        content: '';
        position: absolute;
        left: 0; top: 0; bottom: 0;
        width: 4px;
        background: linear-gradient(180deg, #7c5cff, var(--brand));
      }
      .claim-candidate-card {
        border: 1.5px solid var(--border);
        border-radius: 12px;
        padding: 13px 15px;
        margin-bottom: 10px;
        background: #fff;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
      }
      .claim-candidate-card:hover { border-color: #c7c9f5; box-shadow: 0 4px 14px rgba(16,24,40,0.06); }
    `}</style>
  )
}

function CandidateCard({ candidate, onSelect, disabled }) {
  return (
    <div className="claim-candidate-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
        <div style={{ fontWeight: 700, fontSize: 13.5 }}>{candidate.title || candidate.url}</div>
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: candidate.confidence_percent >= 60 ? 'var(--success)' : '#b45309',
            background: candidate.confidence_percent >= 60 ? '#ecfdf3' : '#fffbeb',
            borderRadius: 999,
            padding: '2px 9px',
            whiteSpace: 'nowrap',
          }}
        >
          {candidate.confidence_percent}% match
        </div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--ink-soft)', wordBreak: 'break-all', margin: '4px 0' }}>{candidate.url}</div>
      {candidate.snippet && <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginBottom: 10, lineHeight: 1.5 }}>{candidate.snippet}</div>}
      <button onClick={() => onSelect(candidate)} disabled={disabled} className="claim-btn-primary" style={{ padding: '7px 14px', fontSize: 12.5 }}>
        This is my profile
      </button>
    </div>
  )
}

function PlaceTypeahead({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const suggestions = open ? suggestPlaces(value) : []

  return (
    <div style={{ position: 'relative' }}>
      <input
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="e.g. Austin, TX and surrounding areas"
        className="claim-input"
      />
      {open && suggestions.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            background: '#fff',
            border: '1px solid var(--border)',
            borderRadius: 10,
            boxShadow: '0 10px 24px rgba(16,24,40,0.12)',
            zIndex: 20,
            maxHeight: 190,
            overflowY: 'auto',
            padding: 4,
          }}
        >
          {suggestions.map((s) => (
            <div
              key={s}
              onMouseDown={() => {
                onChange(s)
                setOpen(false)
              }}
              style={{ padding: '8px 10px', fontSize: 13, cursor: 'pointer', borderRadius: 7 }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-muted)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              📍 {s}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const inputStyle = {
  width: '100%',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '8px 10px',
  fontSize: 14,
  fontFamily: 'inherit',
}

function FieldRow({ field, value, suggestion, missing, onChange, onAcceptSuggestion, onEditSuggestion, onAiGenerate, aiBusy }) {
  return (
    <div style={{ marginBottom: 22 }} data-agent-target={`claim-field-${field.key}`}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13.5, fontWeight: 700, marginBottom: 6, color: 'var(--ink)' }}>
        <span style={{ fontSize: 15 }}>{FIELD_ICONS[field.key]}</span>
        {field.label} {field.required && <span style={{ color: 'var(--danger)' }}>*</span>}
        {field.aiSuggest && (
          <button
            onClick={() => onAiGenerate(field)}
            disabled={aiBusy}
            className="claim-btn-secondary"
            style={{
              marginLeft: 'auto',
              borderColor: '#d8ceff',
              color: 'var(--brand)',
              borderRadius: 999,
              padding: '3px 11px',
              fontSize: 11,
            }}
          >
            {aiBusy ? '✨ Thinking…' : '✨ AI Generate'}
          </button>
        )}
      </label>

      {suggestion ? (
        <div className="claim-suggestion-box">
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--brand)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 5 }}>
            {suggestion.isDefault ? '💡 Commonly used' : suggestion.sourceUrl ? '🔎 Suggested from your website' : '✨ AI suggestion'}
          </div>
          <div style={{ fontSize: 13.5, whiteSpace: 'pre-wrap', marginBottom: 10, lineHeight: 1.5 }}>{suggestion.value}</div>
          <div style={{ display: 'flex', gap: 7 }}>
            <button onClick={() => onAcceptSuggestion(field.key)} className="claim-btn-primary" style={{ padding: '5px 12px', fontSize: 12 }}>
              ✓ Use this
            </button>
            <button onClick={() => onEditSuggestion(field.key)} className="claim-btn-secondary" style={{ padding: '5px 12px', fontSize: 12 }}>
              I'll edit this
            </button>
          </div>
        </div>
      ) : field.multiline ? (
        <textarea value={value} onChange={(e) => onChange(field.key, e.target.value)} rows={3} className="claim-input" placeholder={field.placeholder} />
      ) : field.type === 'place-typeahead' ? (
        <PlaceTypeahead value={value} onChange={(v) => onChange(field.key, v)} />
      ) : (
        <input value={value} onChange={(e) => onChange(field.key, e.target.value)} className="claim-input" placeholder={field.placeholder} />
      )}

      {!suggestion && field.quickPicks && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {field.quickPicks.map((pick) => {
            const selected = value
              .split(',')
              .map((v) => v.trim())
              .includes(pick)
            return (
              <button
                key={pick}
                type="button"
                onClick={() => onChange(field.key, toggleQuickPick(value, pick))}
                className={selected ? 'agent-btn-primary' : 'claim-btn-secondary'}
                style={{ padding: '4px 11px', fontSize: 11.5, borderRadius: 999 }}
              >
                {selected ? '✓ ' : '+ '}
                {pick}
              </button>
            )
          })}
        </div>
      )}

      {missing && <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 5, fontWeight: 600 }}>⚠ This field is required.</div>}
    </div>
  )
}

function ClaimDetailsPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const route = `/claim/${id}/details`

  const [profile, setProfile] = useState(null)
  const [phase, setPhase] = useState('search') // 'search' | 'form' | 'done'
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [candidates, setCandidates] = useState(null)
  const [candidatesDismissed, setCandidatesDismissed] = useState(false)
  const [showUrlInput, setShowUrlInput] = useState(false)
  const [urlDraft, setUrlDraft] = useState('')
  const [chatDraft, setChatDraft] = useState('')

  const [form, setForm] = useState({})
  const [suggestions, setSuggestions] = useState({})
  const [aiBusyKey, setAiBusyKey] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [showMissingError, setShowMissingError] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [celebrateTrigger, setCelebrateTrigger] = useState(0)

  const listRef = useRef(null)
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, sending])

  useEffect(() => {
    getProfile(id).then((p) => {
      if (p.lifecycle_state !== 'unclaimed') {
        navigate(`/dashboard/${id}`)
        return
      }
      if (!p.otp_verified) {
        navigate(`/profile/${id}`)
        return
      }
      setProfile(p)
      const initialForm = {}
      for (const f of CLAIM_FIELDS) initialForm[f.key] = p[f.key] || ''
      setForm(initialForm)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // Once real scraping (if any) has had its chance to propose real values, fill in a
  // common-sense default for anything still genuinely empty — e.g. standard business
  // hours — rather than leaving the user to type something everyone would answer the
  // same way. Runs once per visit; a real scraped/AI suggestion always takes priority
  // since propose_field_updates can still overwrite these by key afterwards.
  const defaultsAppliedRef = useRef(false)
  useEffect(() => {
    if (phase !== 'form' || defaultsAppliedRef.current) return
    defaultsAppliedRef.current = true
    setSuggestions((prev) => {
      const next = { ...prev }
      for (const field of CLAIM_FIELDS) {
        if (field.defaultSuggestion && !form[field.key] && !next[field.key]) {
          next[field.key] = { value: field.defaultSuggestion, isDefault: true }
        }
      }
      return next
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase])

  const greetedRef = useRef(false)
  useEffect(() => {
    if (!profile || greetedRef.current) return
    greetedRef.current = true
    setSending(true)
    greetAgent(id, { route })
      .then((result) => {
        if (result?.reply_text) setMessages((prev) => [...prev, { role: 'assistant', text: result.reply_text }])
        applyUiActions(result?.ui_actions)
      })
      .catch(() => {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', text: "I couldn't search just now — no problem, you can share your website below or fill everything in yourself." },
        ])
      })
      .finally(() => setSending(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile])

  function applyUiActions(uiActions) {
    for (const action of uiActions || []) {
      if (action.type === 'present_candidate_matches') {
        setCandidates(action.result?.candidates || [])
      } else if (action.type === 'confirm_website_url' && action.result?.url) {
        setForm((prev) => ({ ...prev, website_url: action.result.url }))
      } else if (action.type === 'propose_field_updates') {
        const fields = action.result?.fields || {}
        const sourceUrl = action.result?.source_url
        setSuggestions((prev) => {
          const next = { ...prev }
          for (const [key, value] of Object.entries(fields)) {
            if (value) next[key] = { value, sourceUrl }
          }
          return next
        })
        if (Object.keys(fields).length > 0) setPhase('form')
      }
    }
  }

  async function sendMessage(text, { silent } = {}) {
    if (!silent) setMessages((prev) => [...prev, { role: 'user', text }])
    setSending(true)
    try {
      const result = await sendAgentMessage(id, text, { route })
      if (result?.reply_text) setMessages((prev) => [...prev, { role: 'assistant', text: result.reply_text }])
      applyUiActions(result?.ui_actions)
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', text: "Sorry, something went wrong there — try again in a moment." }])
    } finally {
      setSending(false)
    }
  }

  function selectCandidate(candidate) {
    setCandidatesDismissed(true)
    sendMessage(`Yes, this is my business: ${candidate.url}`)
  }

  function declineCandidates() {
    setCandidatesDismissed(true)
    sendMessage('None of these match my business.')
  }

  function submitOwnUrl() {
    const url = urlDraft.trim()
    if (!url) return
    setShowUrlInput(false)
    setCandidatesDismissed(true)
    sendMessage(`Here's my website: ${url}`)
    setUrlDraft('')
  }

  function fillManually() {
    setCandidatesDismissed(true)
    setPhase('form')
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', text: "No problem — let's fill in your details together. I'll suggest things where I can as you go." },
    ])
  }

  function updateField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function acceptSuggestion(key) {
    setForm((prev) => ({ ...prev, [key]: suggestions[key].value }))
    setSuggestions((prev) => {
      const { [key]: _, ...rest } = prev
      return rest
    })
  }

  function editSuggestion(key) {
    setForm((prev) => ({ ...prev, [key]: suggestions[key].value }))
    setSuggestions((prev) => {
      const { [key]: _, ...rest } = prev
      return rest
    })
  }

  async function requestAiSuggestion(field) {
    setAiBusyKey(field.key)
    const known = CLAIM_FIELDS.filter((f) => f.key !== field.key && (form[f.key] || '').trim())
      .map((f) => `${f.label}: ${form[f.key]}`)
      .join('; ')
    await sendMessage(
      `Please draft my ${field.label} based on what I've filled in so far${known ? ` — ${known}` : ' (nothing else filled in yet)'}.`
    )
    setAiBusyKey(null)
  }

  function pageMissingMandatory(page) {
    return fieldsForPage(page).filter((f) => f.required && !(form[f.key] || '').trim())
  }

  function goNext() {
    const missing = pageMissingMandatory(currentPage)
    if (missing.length > 0) {
      setShowMissingError(true)
      return
    }
    setShowMissingError(false)
    if (currentPage < CLAIM_PAGE_COUNT) {
      setCurrentPage((p) => p + 1)
    } else {
      claim()
    }
  }

  function goBack() {
    setShowMissingError(false)
    setCurrentPage((p) => Math.max(1, p - 1))
  }

  async function claim() {
    const missing = MANDATORY_KEYS.filter((k) => !(form[k] || '').trim())
    if (missing.length > 0) {
      setShowMissingError(true)
      return
    }
    setSubmitError(null)
    try {
      await submitClaimDetails(id, form)
      setPhase('done')
      setCelebrateTrigger((n) => n + 1)
      // Land straight on Manage (not Dashboard first) — that's where every score-affecting
      // lever actually lives, and justClaimed=1 is what tells the widget to auto-start the
      // tour immediately here, rather than making someone who just finished a form click
      // "Sure" on an offer too.
      setTimeout(() => navigate(`/dashboard/${id}/manage?justClaimed=1`), 2600)
    } catch {
      setSubmitError('Could not complete your claim. Please check the required fields and try again.')
    }
  }

  if (!profile) return null

  const currentFields = fieldsForPage(currentPage)
  const missingKeys = new Set(showMissingError ? pageMissingMandatory(currentPage).map((f) => f.key) : [])
  const isLastPage = currentPage === CLAIM_PAGE_COUNT

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div style={{ flexShrink: 0 }}>
        <TopNav />
      </div>
      <ClaimWizardStyles />
      <CelebrationOverlay trigger={celebrateTrigger} />
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <div style={{ flex: 1, overflowY: 'auto', background: '#f7f7fb' }}>
          <div style={{ maxWidth: 640, margin: '0 auto', padding: '32px 24px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 14 }}>
              <div
                style={{
                  width: 46,
                  height: 46,
                  flexShrink: 0,
                  borderRadius: 13,
                  background: 'linear-gradient(135deg, #7c5cff, var(--brand))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 22,
                  boxShadow: '0 6px 16px rgba(99, 91, 255, 0.35)',
                }}
              >
                📋
              </div>
              <div>
                <h1 style={{ fontSize: 25, margin: 0, fontWeight: 800, letterSpacing: -0.3 }}>Complete your profile</h1>
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    marginTop: 6,
                    background: '#ecfdf3',
                    color: 'var(--success)',
                    fontSize: 11.5,
                    fontWeight: 700,
                    borderRadius: 999,
                    padding: '3px 10px',
                  }}
                >
                  ✓ Email verified
                </div>
              </div>
            </div>
            <p style={{ color: 'var(--ink-soft)', fontSize: 14, marginTop: 0, marginBottom: 24, lineHeight: 1.55 }}>
              Let's find your real details and get you claimed — <strong style={{ color: 'var(--ink)' }}>name, email, and phone
              number</strong> are required, everything else is optional and can be updated later.
            </p>

            {phase === 'done' && (
              <div className="claim-card" style={{ textAlign: 'center', padding: '48px 0', fontSize: 17, fontWeight: 700 }}>
                🎉 You're claimed! Taking you to your dashboard…
              </div>
            )}

            {phase === 'search' && (
              <div className="claim-card">
                {candidates && candidates.length > 0 && !candidatesDismissed && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>🔍 Is one of these your business?</div>
                    {candidates.map((c) => (
                      <CandidateCard key={c.url} candidate={c} onSelect={selectCandidate} disabled={sending} />
                    ))}
                    <button onClick={declineCandidates} disabled={sending} className="claim-btn-secondary" style={{ marginTop: 4, padding: '8px 16px', fontSize: 13 }}>
                      None of these are mine
                    </button>
                  </div>
                )}

                {(!candidates || candidates.length === 0 || candidatesDismissed) && !sending && phase === 'search' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {!showUrlInput ? (
                      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                        <button onClick={() => setShowUrlInput(true)} className="claim-btn-primary" style={{ padding: '9px 16px', fontSize: 13 }}>
                          🔗 Share my website URL
                        </button>
                        <button onClick={fillManually} className="claim-btn-secondary" style={{ padding: '9px 16px', fontSize: 13 }}>
                          ✏️ I'll fill in my details myself
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: 10 }}>
                        <input
                          value={urlDraft}
                          onChange={(e) => setUrlDraft(e.target.value)}
                          placeholder="https://yourbusiness.com"
                          className="claim-input"
                        />
                        <button onClick={submitOwnUrl} className="claim-btn-primary" style={{ padding: '9px 16px', fontSize: 13, flexShrink: 0 }}>
                          Use this
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {phase === 'form' && (
              <div className="claim-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 26 }}>
                  <div style={{ display: 'flex', gap: 4, flex: 1 }}>
                    {Array.from({ length: CLAIM_PAGE_COUNT }, (_, i) => i + 1).map((n) => (
                      <div
                        key={n}
                        style={{
                          flex: 1,
                          height: 6,
                          borderRadius: 999,
                          background: n <= currentPage ? 'linear-gradient(90deg, #7c5cff, var(--brand))' : 'var(--surface-muted)',
                          transition: 'background 0.25s ease',
                        }}
                      />
                    ))}
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink-soft)', whiteSpace: 'nowrap' }}>
                    Step {currentPage} of {CLAIM_PAGE_COUNT}
                  </div>
                </div>

                {currentFields.map((field) => (
                  <FieldRow
                    key={field.key}
                    field={field}
                    value={form[field.key] || ''}
                    suggestion={suggestions[field.key]}
                    missing={missingKeys.has(field.key)}
                    onChange={updateField}
                    onAcceptSuggestion={acceptSuggestion}
                    onEditSuggestion={editSuggestion}
                    onAiGenerate={requestAiSuggestion}
                    aiBusy={aiBusyKey === field.key}
                  />
                ))}

                {showMissingError && pageMissingMandatory(currentPage).length > 0 && (
                  <div style={{ color: 'var(--danger)', fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
                    ⚠ Please fill in the required fields above before continuing.
                  </div>
                )}
                {submitError && <div style={{ color: 'var(--danger)', fontSize: 13, fontWeight: 600, marginBottom: 12 }}>⚠ {submitError}</div>}

                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, paddingTop: 18, borderTop: '1px solid var(--border)' }}>
                  <button
                    onClick={goBack}
                    disabled={currentPage === 1}
                    className="claim-btn-secondary"
                    style={{ padding: '10px 18px', fontSize: 13, visibility: currentPage === 1 ? 'hidden' : 'visible' }}
                  >
                    ← Back
                  </button>
                  <button onClick={goNext} className="claim-btn-primary" style={{ padding: '10px 24px', fontSize: 13.5 }}>
                    {isLastPage ? '🎉 Claim Profile' : 'Next →'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {phase !== 'done' && (
          <div
            style={{
              width: '25%',
              minWidth: 320,
              maxWidth: 440,
              flexShrink: 0,
              background: '#fafafa',
              borderLeft: '1px solid var(--border)',
              display: 'flex',
              flexDirection: 'column',
              height: '100%',
            }}
          >
            <div
              style={{
                padding: '14px 18px',
                borderBottom: '1px solid var(--border)',
                fontWeight: 700,
                fontSize: 14,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                flexShrink: 0,
              }}
            >
              <span
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #6d28d9, var(--brand))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 12,
                }}
              >
                ✨
              </span>
              Profile Pilot
            </div>
            <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '18px 16px' }}>
              {messages.map((m, i) => (
                <AgentMessageBubble key={i} role={m.role} text={m.text} />
              ))}
              {sending && <TypingIndicator />}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const text = chatDraft.trim()
                if (!text || sending) return
                sendMessage(text)
                setChatDraft('')
              }}
              style={{ display: 'flex', gap: 8, padding: 14, borderTop: '1px solid var(--border)', flexShrink: 0 }}
            >
              <input
                value={chatDraft}
                onChange={(e) => setChatDraft(e.target.value)}
                placeholder="Ask me anything…"
                style={{
                  flex: 1,
                  border: '1px solid var(--border)',
                  borderRadius: 999,
                  padding: '9px 15px',
                  fontSize: 13.5,
                  background: '#fff',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                disabled={sending || !chatDraft.trim()}
                aria-label="Send"
                style={{
                  width: 36,
                  height: 36,
                  flexShrink: 0,
                  borderRadius: '50%',
                  background: 'var(--brand)',
                  color: '#fff',
                  border: 'none',
                  fontSize: 15,
                  cursor: sending || !chatDraft.trim() ? 'default' : 'pointer',
                  opacity: sending || !chatDraft.trim() ? 0.5 : 1,
                }}
              >
                →
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}

export default ClaimDetailsPage
