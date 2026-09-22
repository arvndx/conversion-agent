import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AvatarCircle from '../shared/AvatarCircle.jsx'
import { searchProfiles } from '../../api/search.js'
import { useActiveProfile } from '../../context/ActiveProfileContext.jsx'

function AppTopBar({ title, currentProfile, actions }) {
  const navigate = useNavigate()
  const { setActiveProfileId } = useActiveProfile()
  const [switchable, setSwitchable] = useState([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    searchProfiles().then((data) => {
      setSwitchable(data.results.filter((p) => p.is_verified))
    })
  }, [])

  function switchTo(id) {
    setActiveProfileId(id)
    setOpen(false)
    navigate(`/dashboard/${id}`)
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '14px 24px',
        borderBottom: '1px solid var(--border)',
        background: '#fff',
      }}
    >
      <h1 style={{ fontSize: 18, margin: 0 }}>{title}</h1>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {actions}
        <span style={{ cursor: 'pointer' }}>🔍</span>
        <button style={{ border: '1px solid var(--border)', background: '#fff', borderRadius: 6, padding: '6px 14px', fontSize: 13, cursor: 'pointer' }}>
          Help
        </button>
        <span style={{ cursor: 'pointer' }}>🔔</span>

        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setOpen((o) => !o)}
            style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'none', border: 'none', cursor: 'pointer' }}
          >
            <AvatarCircle name={currentProfile?.name || '?'} size={32} />
            <span style={{ fontSize: 13, textAlign: 'left' }}>
              <div style={{ color: 'var(--ink-soft)', fontSize: 11 }}>Viewing as</div>
              <div style={{ fontWeight: 600 }}>{currentProfile?.name}</div>
            </span>
            <span>▾</span>
          </button>

          {open && (
            <div
              style={{
                position: 'absolute',
                right: 0,
                top: '110%',
                background: '#fff',
                border: '1px solid var(--border)',
                borderRadius: 8,
                boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                minWidth: 200,
                zIndex: 10,
              }}
            >
              {switchable.map((p) => (
                <div
                  key={p.id}
                  onClick={() => switchTo(p.id)}
                  style={{ padding: '10px 14px', fontSize: 13, cursor: 'pointer' }}
                >
                  {p.name}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AppTopBar
