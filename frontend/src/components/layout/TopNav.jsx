import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useClaimCard } from '../claim/ClaimCard.jsx'
import { useAuth } from '../../context/AuthContext.jsx'

function TopNav({ initialKeyword = '' }) {
  const navigate = useNavigate()
  const { openClaim } = useClaimCard()
  const { me, logout } = useAuth()
  const [keyword, setKeyword] = useState(initialKeyword)

  function onSubmit(e) {
    e.preventDefault()
    const params = new URLSearchParams()
    if (keyword) params.set('keyword', keyword)
    navigate(`/search?${params.toString()}`)
  }

  return (
    <header style={{ borderBottom: '1px solid var(--border)', background: '#fff' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: 16,
          padding: '8px 24px',
          fontSize: 13,
          color: 'var(--ink-soft)',
        }}
      >
        <a href="#contact">Contact Us</a>
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 24,
          padding: '12px 24px',
          flexWrap: 'wrap',
        }}
      >
        <a
          href="/search"
          onClick={(e) => {
            e.preventDefault()
            navigate('/search')
          }}
          style={{ fontWeight: 800, fontSize: 20, color: 'var(--brand)', textDecoration: 'none' }}
        >
          eXperience<span style={{ color: 'var(--ink)' }}>.com</span>
        </a>

        <form
          onSubmit={onSubmit}
          style={{
            flex: 1,
            display: 'flex',
            minWidth: 280,
            border: '1px solid var(--border)',
            borderRadius: 999,
            overflow: 'hidden',
          }}
        >
          <input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="Search by name, company, title or city"
            aria-label="Search"
            style={{ flex: 1, border: 'none', padding: '10px 16px', outline: 'none' }}
          />
          <button
            type="submit"
            style={{
              border: 'none',
              background: 'var(--brand)',
              color: '#fff',
              padding: '0 20px',
              cursor: 'pointer',
            }}
          >
            →
          </button>
        </form>

        <nav style={{ display: 'flex', gap: 16, fontSize: 14, color: 'var(--ink-soft)' }}>
          <span>Professionals</span>
          <span>Enterprises</span>
          <span>Products</span>
          <span>Resources</span>
        </nav>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button
            onClick={() => openClaim()}
            style={{ background: '#fff', color: 'var(--brand)', border: '1.5px solid var(--brand)', borderRadius: 6, padding: '7px 14px', fontWeight: 700, cursor: 'pointer' }}
          >
            Claim a profile
          </button>
          {me?.authenticated ? (
            <>
              <Link to={`/dashboard/${me.profile_id}`} style={{ fontSize: 14, fontWeight: 600 }}>
                {me.name}
              </Link>
              <button
                onClick={async () => {
                  await logout()
                  navigate('/search')
                }}
                style={{ background: 'none', border: 'none', color: 'var(--ink-soft)', cursor: 'pointer', fontSize: 14 }}
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link to="/signin" style={{ fontSize: 14 }}>
                Login
              </Link>
              <button
                onClick={() => openClaim()}
                style={{ background: 'var(--brand)', color: '#fff', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer' }}
              >
                Sign up
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

export default TopNav
