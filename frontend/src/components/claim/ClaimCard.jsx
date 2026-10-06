import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorMessage } from '../../api/client.js'
import { getTaxonomy, startClaim, verifyClaim } from '../../api/claims.js'
import { getProfile } from '../../api/profiles.js'
import { useAuth } from '../../context/AuthContext.jsx'
import '../../styles/claim.css'

// The claim card (core1.txt, Process 1). Opened from a search result / profile page ("claim this one")
// or from the header's "Claim a profile" (a profile that is not in the database yet). One modal for the
// whole app; any button calls openClaim({ profileId }) or openClaim().
const ClaimCardContext = createContext(null)

// eslint-disable-next-line react-refresh/only-export-components
export function useClaimCard() {
  return useContext(ClaimCardContext)
}

export function ClaimCardProvider({ children }) {
  const [target, setTarget] = useState(null) // { profileId } | {} for a new profile | null when closed
  const openClaim = useCallback((opts = {}) => setTarget(opts), [])
  const close = useCallback(() => setTarget(null), [])
  const value = useMemo(() => ({ openClaim }), [openClaim])
  return (
    <ClaimCardContext.Provider value={value}>
      {children}
      {target && <ClaimModal profileId={target.profileId} onClose={close} />}
    </ClaimCardContext.Provider>
  )
}

const digits = (value) => (value || '').replace(/\D/g, '')

function Label({ children, hint }) {
  return (
    <label className="claim-label">
      {children}
      {hint && <span style={{ fontWeight: 500, color: 'var(--ink-soft)', marginLeft: 6 }}>{hint}</span>}
    </label>
  )
}

function ClaimModal({ profileId, onClose }) {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const isNew = !profileId

  const [original, setOriginal] = useState(null) // the stored profile (existing mode)
  const [verticals, setVerticals] = useState([])
  const [form, setForm] = useState({ name: '', email: '', phone_number: '', vertical: '', category_id: '', services: [] })
  const [step, setStep] = useState('card') // card | code
  const [claim, setClaim] = useState(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null) // { message, action? }

  // Load the taxonomy and, for an existing profile, what we hold about it.
  useEffect(() => {
    let alive = true
    Promise.all([getTaxonomy(), profileId ? getProfile(profileId) : Promise.resolve(null)]).then(([taxonomy, profile]) => {
      if (!alive) return
      setVerticals(taxonomy.verticals)
      if (profile) {
        setOriginal(profile)
        // Only the vertical is pre-selected; the agent chooses the category and services.
        const match = taxonomy.verticals.find((v) => v.name === profile.vertical)
        setForm({
          name: profile.name || '',
          email: profile.email || '',
          phone_number: profile.phone_number || '',
          vertical: match?.key || '',
          category_id: '',
          services: [],
        })
      }
    })
    return () => {
      alive = false
    }
  }, [profileId])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const vertical = verticals.find((v) => v.key === form.vertical)
  const category = vertical?.categories.find((c) => String(c.id) === String(form.category_id))

  // Edit rule: of phone and email only one may differ from what we hold.
  const emailChanged = !isNew && original && form.email.trim().toLowerCase() !== (original.email || '').toLowerCase()
  const phoneChanged = !isNew && original && Boolean(digits(original.phone_number)) && digits(form.phone_number) !== digits(original.phone_number)

  const set = (patch) => setForm((prev) => ({ ...prev, ...patch }))
  const toggleService = (key) =>
    set({ services: form.services.includes(key) ? form.services.filter((s) => s !== key) : [...form.services, key] })

  const complete =
    form.name.trim() && form.email.trim() && digits(form.phone_number).length >= 10 && form.vertical && form.category_id && form.services.length > 0

  async function submitCard(e) {
    e?.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await startClaim({
        profile_id: profileId || undefined,
        name: form.name,
        email: form.email,
        phone_number: form.phone_number,
        vertical: form.vertical,
        category_id: Number(form.category_id),
        services: form.services,
      })
      setClaim(result)
      setCode('')
      setStep('code')
    } catch (err) {
      const detail = err.detail
      if (detail?.code === 'already_claimed') setError({ message: detail.message, action: { label: 'Sign in', to: '/signin' } })
      else if (detail?.code === 'profile_exists')
        setError({ message: detail.message, action: { label: 'Open that profile', to: `/profile/${detail.profile_id}` } })
      else setError({ message: errorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  async function submitCode(e) {
    e?.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await verifyClaim(claim.claim_id, code.trim())
      await refresh()
      onClose()
      navigate(result.next)
    } catch (err) {
      setError({ message: errorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  const inputStyle = { width: '100%' }
  const lockedStyle = { background: '#f3f4f6', color: 'var(--ink-soft)' }

  return (
    <div
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      style={{ position: 'fixed', inset: 0, background: 'rgba(17,24,39,0.5)', backdropFilter: 'blur(3px)', display: 'grid', placeItems: 'center', zIndex: 1000, padding: 16 }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={isNew ? 'Claim a profile' : 'Claim this profile'}
        className="claim-card claim-modal pilot-rise"
        style={{ width: '100%', maxWidth: 540, maxHeight: '92vh', overflowY: 'auto', padding: '30px 30px 26px' }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
          <span className="claim-modal__icon" aria-hidden="true">{step === 'code' ? '✉️' : '🛡️'}</span>
          <div style={{ flex: 1 }}>
            <h2 style={{ margin: 0, fontSize: 21, fontWeight: 800 }}>{isNew ? 'Claim a profile' : 'Claim this profile'}</h2>
            <p style={{ margin: '6px 0 0', fontSize: 13.5, color: 'var(--ink-soft)', lineHeight: 1.5 }}>
              {step === 'code'
                ? 'One last step: enter the code we sent you.'
                : isNew
                  ? "We don't have you yet. Tell us who you are and we'll set up your profile."
                  : 'Check your details, choose your category and services, then claim it.'}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ border: 'none', background: 'transparent', fontSize: 20, cursor: 'pointer', color: 'var(--ink-soft)' }}>
            ✕
          </button>
        </div>

        {step === 'card' && (
          <form onSubmit={submitCard}>
            <Label>Full name *</Label>
            <input className="claim-input" style={inputStyle} value={form.name} onChange={(e) => set({ name: e.target.value })} autoFocus />

            <Label hint={!isNew && phoneChanged ? '(locked: you are changing your phone)' : undefined}>Email *</Label>
            <input
              className="claim-input"
              style={{ ...inputStyle, ...(!isNew && phoneChanged ? lockedStyle : {}) }}
              type="email"
              value={form.email}
              readOnly={!isNew && phoneChanged}
              onChange={(e) => set({ email: e.target.value })}
            />

            <Label hint={!isNew && emailChanged ? '(locked: you are changing your email)' : undefined}>Phone number *</Label>
            <input
              className="claim-input"
              style={{ ...inputStyle, ...(!isNew && emailChanged ? lockedStyle : {}) }}
              value={form.phone_number}
              readOnly={!isNew && emailChanged}
              onChange={(e) => set({ phone_number: e.target.value })}
            />
            {!isNew && (
              <div style={{ fontSize: 11.5, color: 'var(--ink-soft)', marginTop: 5 }}>
                You can change your name, and either your phone number or your email, but not both.
                {(emailChanged || phoneChanged) && (
                  <button
                    type="button"
                    onClick={() => set({ email: original.email || '', phone_number: original.phone_number || '' })}
                    style={{ border: 'none', background: 'none', color: 'var(--brand)', fontWeight: 700, cursor: 'pointer', marginLeft: 6 }}
                  >
                    Undo my change
                  </button>
                )}
              </div>
            )}

            <div className="claim-two">
            <div>
            <Label>Vertical *</Label>
            <select
              className="claim-input"
              style={inputStyle}
              value={form.vertical}
              onChange={(e) => set({ vertical: e.target.value, category_id: '', services: [] })}
            >
              <option value="">Choose a vertical</option>
              {verticals.map((v) => (
                <option key={v.key} value={v.key}>
                  {v.name}
                </option>
              ))}
            </select>

            </div>
            <div>
            <Label>Category *</Label>
            <select
              className="claim-input"
              style={inputStyle}
              value={form.category_id}
              disabled={!vertical}
              onChange={(e) => set({ category_id: e.target.value, services: [] })}
            >
              <option value="">{vertical ? 'Choose a category' : 'Choose a vertical first'}</option>
              {(vertical?.categories || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>

            </div>
            </div>

            <Label hint="(choose one or more)">Services *</Label>
            {category ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                {category.services.map((s) => {
                  const on = form.services.includes(s.key)
                  return (
                    <button key={s.key} type="button" className="pilot-chip" aria-pressed={on} onClick={() => toggleService(s.key)}>
                      {on ? '✓ ' : '+ '}
                      {s.name}
                    </button>
                  )
                })}
              </div>
            ) : (
              <div style={{ fontSize: 12.5, color: 'var(--ink-soft)' }}>Choose a category to see its services.</div>
            )}

            {error && (
              <div role="alert" style={{ marginTop: 16, padding: '10px 12px', borderRadius: 8, background: '#fef2f2', color: '#b91c1c', fontSize: 13, fontWeight: 600 }}>
                {error.message}
                {error.action && (
                  <button
                    type="button"
                    onClick={() => {
                      onClose()
                      navigate(error.action.to)
                    }}
                    style={{ border: 'none', background: 'none', color: 'var(--brand)', fontWeight: 800, cursor: 'pointer', marginLeft: 8 }}
                  >
                    {error.action.label} →
                  </button>
                )}
              </div>
            )}

            <button type="submit" disabled={!complete || busy} className="claim-btn-primary" style={{ width: '100%', padding: '12px 0', fontSize: 14.5, marginTop: 18 }}>
              {busy ? 'Sending code…' : 'Claim now'}
            </button>
          </form>
        )}

        {step === 'code' && claim && (
          <form onSubmit={submitCode}>
            <div style={{ margin: '18px 0 6px', fontSize: 14, lineHeight: 1.55 }}>
              We sent a 6-digit code to <strong>{claim.email}</strong>.
            </div>
            <a href={claim.mailbox_url} target="_blank" rel="noreferrer" style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--brand)' }}>
              Open your mailbox ↗
            </a>
            <div style={{ fontSize: 11.5, color: 'var(--ink-soft)', marginTop: 4 }}>This is a demo, so the email is shown on a mailbox page instead of being sent.</div>

            <Label>Verification code</Label>
            <input
              className="claim-input"
              style={{ ...inputStyle, fontSize: 22, letterSpacing: 8, textAlign: 'center', fontWeight: 700 }}
              inputMode="numeric"
              maxLength={6}
              placeholder="······"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              autoFocus
            />

            {error && (
              <div role="alert" style={{ marginTop: 14, padding: '10px 12px', borderRadius: 8, background: '#fef2f2', color: '#b91c1c', fontSize: 13, fontWeight: 600 }}>
                {error.message}
              </div>
            )}

            <button type="submit" disabled={code.length !== 6 || busy} className="claim-btn-primary" style={{ width: '100%', padding: '12px 0', fontSize: 14.5, marginTop: 18 }}>
              {busy ? 'Verifying…' : 'Verify and claim'}
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, fontSize: 12.5 }}>
              <button type="button" onClick={() => { setStep('card'); setError(null) }} style={{ border: 'none', background: 'none', color: 'var(--ink-soft)', cursor: 'pointer' }}>
                ← Change my details
              </button>
              <button type="button" onClick={submitCard} disabled={busy} style={{ border: 'none', background: 'none', color: 'var(--brand)', fontWeight: 700, cursor: 'pointer' }}>
                Send a new code
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
