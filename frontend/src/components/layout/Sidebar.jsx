import { Link, useLocation } from 'react-router-dom'

const NAV_LINK_STYLE = { display: 'block', padding: '8px 20px', fontSize: 14, color: 'var(--ink)', textDecoration: 'none' }
const NAV_STATIC_STYLE = { ...NAV_LINK_STYLE, color: 'var(--ink-soft)', cursor: 'default' }

function SectionLabel({ children }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-soft)', padding: '16px 20px 6px', letterSpacing: 0.5 }}>
      {children}
    </div>
  )
}

function Sidebar({ profileId, onboarding }) {
  const location = useLocation()
  const isHome = location.pathname === `/dashboard/${profileId}`
  const isManage = location.pathname === `/dashboard/${profileId}/manage`

  return (
    <aside style={{ width: 240, flexShrink: 0, borderRight: '1px solid var(--border)', background: '#fff', paddingBottom: 24 }}>
      <Link
        to="/search"
        style={{ display: 'block', padding: '16px 20px', fontWeight: 800, fontSize: 18, color: 'var(--brand)', textDecoration: 'none' }}
      >
        eXperience<span style={{ color: 'var(--ink)' }}>.com</span>
      </Link>

      {onboarding && onboarding.total > 0 && (
        <div style={{ margin: '0 20px 12px', background: 'var(--brand)', color: '#fff', borderRadius: 8, padding: '10px 14px', fontSize: 13, fontWeight: 600 }}>
          Complete Onboarding {onboarding.completed}/{onboarding.total}
        </div>
      )}

      <Link to={`/dashboard/${profileId}`} style={{ ...NAV_LINK_STYLE, fontWeight: isHome ? 700 : 400, background: isHome ? 'var(--surface-muted)' : 'transparent' }}>
        Home
      </Link>

      <SectionLabel>Command Center</SectionLabel>
      <span style={NAV_STATIC_STYLE}>Search Ranking</span>
      <span style={NAV_STATIC_STYLE}>AI Visibility</span>
      <span style={NAV_STATIC_STYLE}>
        Social Posts{' '}
        <span style={{ background: 'var(--pro-badge)', color: '#fff', fontSize: 10, fontWeight: 700, borderRadius: 4, padding: '1px 5px', marginLeft: 4 }}>
          PRO
        </span>
      </span>
      <span style={NAV_STATIC_STYLE}>Insights</span>
      <span style={NAV_STATIC_STYLE}>Network</span>

      <SectionLabel>Account Center</SectionLabel>
      <Link
        to={`/dashboard/${profileId}/manage`}
        style={{ ...NAV_LINK_STYLE, fontWeight: isManage ? 700 : 400, background: isManage ? 'var(--surface-muted)' : 'transparent' }}
      >
        Profile
      </Link>
      <Link
        to={`/dashboard/${profileId}/manage`}
        style={NAV_LINK_STYLE}
      >
        Connections
      </Link>
      <span style={NAV_STATIC_STYLE}>Learning Hub</span>
      <span style={NAV_STATIC_STYLE}>Settings</span>
      <span style={NAV_STATIC_STYLE}>Billing</span>
    </aside>
  )
}

export default Sidebar
