import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import TopNav from '../components/layout/TopNav.jsx'
import { verifyOtp } from '../api/profiles.js'
import { getEmail, listInbox } from '../api/inbox.js'

function MockInboxPage() {
  const navigate = useNavigate()
  const [emails, setEmails] = useState([])
  const [selected, setSelected] = useState(null)
  const [otp, setOtp] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    listInbox().then(setEmails)
  }, [])

  async function openEmail(id) {
    const email = await getEmail(id)
    setSelected(email)
    setOtp('')
    setError(null)
    setEmails((prev) => prev.map((e) => (e.id === id ? { ...e, is_opened: true } : e)))
  }

  async function onVerify() {
    setVerifying(true)
    setError(null)
    try {
      await verifyOtp(selected.profile_id, otp)
      navigate(`/claim/${selected.profile_id}/details`)
    } catch {
      setError('Invalid verification code. Please try again.')
    } finally {
      setVerifying(false)
    }
  }

  return (
    <div>
      <TopNav />
      <div style={{ display: 'flex', gap: 24, padding: 24, maxWidth: 1000, margin: '0 auto' }}>
        <div style={{ width: 320, border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff' }}>
          <h2 style={{ fontSize: 16, padding: '12px 16px', margin: 0, borderBottom: '1px solid var(--border)' }}>
            Mock Inbox
          </h2>
          {emails.length === 0 && (
            <div style={{ padding: 16, fontSize: 13, color: 'var(--ink-soft)' }}>No emails yet.</div>
          )}
          {emails.map((e) => (
            <div
              key={e.id}
              onClick={() => openEmail(e.id)}
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid var(--border)',
                cursor: 'pointer',
                fontWeight: e.is_opened ? 400 : 700,
                background: selected?.id === e.id ? 'var(--surface-muted)' : 'transparent',
              }}
            >
              <div style={{ fontSize: 13 }}>{e.to_email}</div>
              <div style={{ fontSize: 13 }}>{e.subject}</div>
              <div style={{ fontSize: 11, color: 'var(--ink-soft)' }}>
                {new Date(e.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>

        <div style={{ flex: 1, border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 20 }}>
          {!selected && <div style={{ color: 'var(--ink-soft)' }}>Select an email to view it.</div>}
          {selected && (
            <div>
              <h3 style={{ marginTop: 0 }}>{selected.subject}</h3>
              <div dangerouslySetInnerHTML={{ __html: selected.body_html }} />

              <div style={{ marginTop: 20, paddingTop: 20, borderTop: '1px solid var(--border)' }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Enter verification code
                </label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    maxLength={6}
                    placeholder="6-digit code"
                    style={{
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      padding: '8px 12px',
                      fontSize: 16,
                      letterSpacing: 4,
                      width: 160,
                    }}
                  />
                  <button
                    onClick={onVerify}
                    disabled={verifying || otp.length !== 6}
                    style={{
                      background: 'var(--brand)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 6,
                      padding: '10px 20px',
                      fontWeight: 600,
                      cursor: verifying || otp.length !== 6 ? 'default' : 'pointer',
                    }}
                  >
                    {verifying ? 'Verifying…' : 'Verify'}
                  </button>
                </div>
                {error && <div style={{ color: 'var(--danger)', fontSize: 13, marginTop: 8 }}>{error}</div>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default MockInboxPage
