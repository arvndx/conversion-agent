import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import TopNav from '../components/layout/TopNav.jsx'
import { demoLogin, getDemoProfiles, requestLoginCode, verifyLoginCode } from '../api/auth.js'
import { errorMessage } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import '../styles/claim.css'

// Email-OTP sign-in for agents who have already claimed a profile.
function SignInPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { me, refresh } = useAuth()
  const [step, setStep] = useState('email')
  const [email, setEmail] = useState('')
  const [mailbox, setMailbox] = useState(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [demo, setDemo] = useState([])

  useEffect(() => {
    getDemoProfiles().then((d) => setDemo(d.profiles)).catch(() => {}) // 404 when demo mode is off
  }, [])

  // Back where they were going, else their dashboard — or onboarding, if they claimed but never finished it.
  function destination(account) {
    return params.get('next') || (account.onboarding_completed === false ? `/onboarding/${account.profile_id}` : `/dashboard/${account.profile_id}`)
  }

  async function sendCode(e) {
    e?.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await requestLoginCode(email)
      setMailbox(result.mailbox_url)
      setStep('code')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function verify(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await verifyLoginCode(email, code)
      await refresh()
      navigate(destination(result))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function signInAs(profileId) {
    const result = await demoLogin(profileId)
    await refresh()
    navigate(destination(result))
  }

  return (
    <div>
      <TopNav />
      <div style={{ maxWidth: 440, margin: '48px auto', padding: '0 16px' }}>
        <div className="claim-card" style={{ padding: '28px 30px' }}>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>Sign in</h1>
          {me?.authenticated && (
            <div style={{ marginTop: 10, fontSize: 13.5 }}>
              You are signed in as <strong>{me.name}</strong>. <Link to={`/dashboard/${me.profile_id}`}>Go to your dashboard</Link>
            </div>
          )}

          {step === 'email' ? (
            <form onSubmit={sendCode}>
              <p style={{ fontSize: 14, color: 'var(--ink-soft)', lineHeight: 1.5 }}>
                Enter the email of your claimed profile and we will send you a code.
              </p>
              <input className="claim-input" type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus style={{ width: '100%' }} />
              {error && <div role="alert" style={{ color: '#b91c1c', fontSize: 13, fontWeight: 600, marginTop: 10 }}>{error}</div>}
              <button type="submit" disabled={!email.trim() || busy} className="claim-btn-primary" style={{ width: '100%', padding: '12px 0', marginTop: 16 }}>
                {busy ? 'Sending…' : 'Send me a code'}
              </button>
              <div style={{ marginTop: 14, fontSize: 13, color: 'var(--ink-soft)' }}>
                Not claimed yet? <Link to="/search">Find your profile</Link> and press Claim.
              </div>
            </form>
          ) : (
            <form onSubmit={verify}>
              <p style={{ fontSize: 14, lineHeight: 1.5 }}>
                If <strong>{email}</strong> belongs to a claimed profile, a code is waiting in its mailbox.
              </p>
              <a href={mailbox} target="_blank" rel="noreferrer" style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--brand)' }}>
                Open the mailbox ↗
              </a>
              <input
                className="claim-input"
                style={{ width: '100%', marginTop: 16, fontSize: 22, letterSpacing: 8, textAlign: 'center', fontWeight: 700 }}
                inputMode="numeric"
                maxLength={6}
                placeholder="······"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                autoFocus
              />
              {error && <div role="alert" style={{ color: '#b91c1c', fontSize: 13, fontWeight: 600, marginTop: 10 }}>{error}</div>}
              <button type="submit" disabled={code.length !== 6 || busy} className="claim-btn-primary" style={{ width: '100%', padding: '12px 0', marginTop: 16 }}>
                {busy ? 'Checking…' : 'Sign in'}
              </button>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, fontSize: 12.5 }}>
                <button type="button" onClick={() => { setStep('email'); setCode(''); setError(null) }} style={{ border: 'none', background: 'none', color: 'var(--ink-soft)', cursor: 'pointer' }}>
                  ← Use a different email
                </button>
                <button type="button" onClick={sendCode} disabled={busy} style={{ border: 'none', background: 'none', color: 'var(--brand)', fontWeight: 700, cursor: 'pointer' }}>
                  Send a new code
                </button>
              </div>
            </form>
          )}
        </div>

        {demo.length > 0 && (
          <div className="claim-card" style={{ padding: '18px 22px', marginTop: 18 }}>
            <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink-soft)', marginBottom: 10 }}>
              Demo accounts (skip the code)
            </div>
            <div style={{ display: 'grid', gap: 6 }}>
              {demo.map((p) => (
                <button key={p.id} onClick={() => signInAs(p.id)} className="claim-btn-secondary" style={{ textAlign: 'left', padding: '8px 12px', fontSize: 13 }}>
                  {p.name} <span style={{ color: 'var(--ink-soft)' }}>· {p.category} · {p.lifecycle_state}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default SignInPage
