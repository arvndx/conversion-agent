import { Link, useSearchParams } from 'react-router-dom'
import TopNav from '../components/layout/TopNav.jsx'

// Any address the app does not know, or a profile that does not exist.
function NotFoundPage() {
  const [params] = useSearchParams()
  const what = params.get('what') === 'profile' ? 'profile' : 'page'
  return (
    <div>
      <TopNav />
      <div style={{ maxWidth: 520, margin: '72px auto', padding: '0 16px', textAlign: 'center' }}>
        <div style={{ fontSize: 48 }}>🧭</div>
        <h1 style={{ fontSize: 24, margin: '12px 0 8px' }}>We can&apos;t find that {what}</h1>
        <p style={{ color: 'var(--ink-soft)', lineHeight: 1.6 }}>It may have moved, or the address may be mistyped.</p>
        <Link to="/search" style={{ color: 'var(--brand)', fontWeight: 700 }}>Search professionals →</Link>
      </div>
    </div>
  )
}

export default NotFoundPage
