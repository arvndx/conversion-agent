import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AvatarCircle from '../shared/AvatarCircle.jsx'
import { demoLogin, getDemoProfiles } from '../../api/auth.js'
import { useActiveProfile } from '../../context/ActiveProfileContext.jsx'
import { useAuth } from '../../context/AuthContext.jsx'

function AppTopBar({ title, currentProfile, actions }) {
  const navigate = useNavigate()
  const { setActiveProfileId } = useActiveProfile()
  const { refresh, logout } = useAuth()
  const [switchable, setSwitchable] = useState([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    // A short list of ready-made accounts; the server only serves it in demo mode.
    getDemoProfiles().then((d) => setSwitchable(d.profiles)).catch(() => setSwitchable([]))
  }, [])

  async function switchTo(id) {
    await demoLogin(id) // demo mode: sign in as that account without a code
    setActiveProfileId(id)
    await refresh()
    setOpen(false)
    navigate(`/dashboard/${id}`)
  }

  async function signOut() {
    await logout()
    navigate('/signin')
  }

  return (
    <div className="app-topbar">
      <h1>{title}</h1>

      <div className="app-topbar__right">
        {actions}
        <button className="icon-btn" aria-label="Search">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
        </button>
        <button className="btn btn--ghost btn--sm">Help</button>
        <button className="icon-btn" aria-label="Notifications">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9a6 6 0 1 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9Z" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
          <span className="icon-btn__dot" />
        </button>

        <div style={{ position: 'relative' }}>
          <button className="user-chip" onClick={() => setOpen((o) => !o)}>
            <AvatarCircle name={currentProfile?.name || '?'} size={32} />
            <span className="user-chip__who">
              <small>Viewing as</small>
              <b>{currentProfile?.name}</b>
            </span>
            <span aria-hidden="true">▾</span>
          </button>

          {open && (
            <div className="menu">
              {switchable.length > 0 && <div className="menu__label">SWITCH DEMO ACCOUNT</div>}
              {switchable.map((p) => (
                <div key={p.id} className="menu__item" onClick={() => switchTo(p.id)}>
                  {p.name} <small>· {p.category}</small>
                </div>
              ))}
              <div className="menu__item menu__item--out" onClick={signOut}>Sign out</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AppTopBar
