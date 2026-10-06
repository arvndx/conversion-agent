import { Link, useLocation } from 'react-router-dom'

function Item({ icon, to, active, children }) {
  const body = (
    <>
      <span className="nav-item__icon" aria-hidden="true">{icon}</span>
      {children}
    </>
  )
  if (!to) return <span className="nav-item nav-item--soft">{body}</span>
  return <Link to={to} className={`nav-item${active ? ' nav-item--active' : ''}`}>{body}</Link>
}

function Sidebar({ profileId, onboarding }) {
  const location = useLocation()
  const isHome = location.pathname === `/dashboard/${profileId}`
  const isManage = location.pathname === `/dashboard/${profileId}/manage`

  return (
    <aside className="app-sidebar">
      <Link to="/search" className="app-brand">
        <span className="app-brand__mark" aria-hidden="true">✦</span>
        <span>eXperience<span>.com</span></span>
      </Link>

      {onboarding && onboarding.total > 0 && (
        <div className="nav-onboarding">Complete Onboarding {onboarding.completed}/{onboarding.total}</div>
      )}

      <Item icon="🏠" to={`/dashboard/${profileId}`} active={isHome}>Home</Item>

      <div className="nav-label">Command Center</div>
      <Item icon="📈">Search Ranking</Item>
      <Item icon="✨">AI Visibility</Item>
      <Item icon="📣">Social Posts <span className="tag-pro">PRO</span></Item>
      <Item icon="💡">Insights</Item>
      <Item icon="🤝">Network</Item>

      <div className="nav-label">Account Center</div>
      <Item icon="👤" to={`/dashboard/${profileId}/manage`} active={isManage}>Profile</Item>
      <Item icon="🔗" to={`/dashboard/${profileId}/manage`}>Connections</Item>
      <Item icon="🎓">Learning Hub</Item>
      <Item icon="⚙️">Settings</Item>
      <Item icon="💳">Billing</Item>
    </aside>
  )
}

export default Sidebar
