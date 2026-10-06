import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import TopNav from '../components/layout/TopNav.jsx'
import { getMail, listMailbox } from '../api/mailbox.js'

const POLL_MS = 4000

// A mock mailbox: one page per email address. Nothing is sent; messages written for this address
// appear here (verification codes included). The list refreshes by itself so a code appears as soon
// as it is requested from another tab.
function MailboxPage() {
  const { email } = useParams()
  const navigate = useNavigate()
  const [draft, setDraft] = useState(email || '')
  const [mails, setMails] = useState([])
  const [selected, setSelected] = useState(null)
  const [loaded, setLoaded] = useState(false)

  const refresh = useCallback(async () => {
    if (!email) return
    const rows = await listMailbox(email).catch(() => [])
    setMails(rows)
    setLoaded(true)
  }, [email])

  useEffect(() => {
    setSelected(null)
    setLoaded(false)
    refresh()
    if (!email) return undefined
    const timer = setInterval(refresh, POLL_MS)
    return () => clearInterval(timer)
  }, [email, refresh])

  // Open the newest message by default (it is usually the code you came here for).
  useEffect(() => {
    if (mails.length > 0 && !selected) open(mails[0].id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mails])

  async function open(id) {
    setSelected(await getMail(id, email))
    refresh()
  }

  function onSubmit(e) {
    e.preventDefault()
    const value = draft.trim().toLowerCase()
    if (value) navigate(`/mailbox/${encodeURIComponent(value)}`)
  }

  return (
    <div>
      <TopNav />
      <div style={{ maxWidth: 1000, margin: '0 auto', padding: 'clamp(12px, 3vw, 24px)' }}>
        <form onSubmit={onSubmit} style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
          <input
            className="claim-input"
            type="email"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Email address to open the mailbox for"
            aria-label="Mailbox email address"
          />
          <button type="submit" className="claim-btn-primary" style={{ padding: '9px 20px', fontSize: 13.5, flexShrink: 0 }}>
            Open mailbox
          </button>
        </form>

        {!email ? (
          <div style={{ color: 'var(--ink-soft)', fontSize: 14 }}>
            This is a demo mailbox: nothing is really emailed. Enter an address to see the messages written for it.
          </div>
        ) : (
          <div className="mailbox-layout" style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
            <div className="mailbox-list" style={{ width: 320, flexShrink: 0, border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff' }}>
              <h2 style={{ fontSize: 15, padding: '12px 16px', margin: 0, borderBottom: '1px solid var(--border)', wordBreak: 'break-all' }}>
                Mailbox · {email}
              </h2>
              {loaded && mails.length === 0 && <div style={{ padding: 16, fontSize: 13, color: 'var(--ink-soft)' }}>No emails yet for this address.</div>}
              {mails.map((m) => (
                <div
                  key={m.id}
                  onClick={() => open(m.id)}
                  style={{
                    padding: '12px 16px',
                    borderBottom: '1px solid var(--border)',
                    cursor: 'pointer',
                    fontWeight: m.is_opened ? 400 : 700,
                    background: selected?.id === m.id ? 'var(--surface-muted)' : 'transparent',
                  }}
                >
                  <div style={{ fontSize: 13 }}>{m.subject}</div>
                  <div style={{ fontSize: 11, color: 'var(--ink-soft)' }}>{new Date(`${m.created_at}Z`).toLocaleString()}</div>
                </div>
              ))}
            </div>

            <div style={{ flex: 1, minWidth: 0, border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 24, minHeight: 200 }}>
              {selected ? (
                <>
                  <h3 style={{ marginTop: 0 }}>{selected.subject}</h3>
                  <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginBottom: 16 }}>To: {selected.to_email}</div>
                  {/* body_html is built by the server with every dynamic value HTML-escaped */}
                  <div dangerouslySetInnerHTML={{ __html: selected.body_html }} />
                </>
              ) : (
                <div style={{ color: 'var(--ink-soft)', fontSize: 14 }}>Select an email to read it.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default MailboxPage
