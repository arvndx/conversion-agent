import { useNavigate } from 'react-router-dom'
import { useState } from 'react'

function TopNav({ initialKeyword = '', initialLocation = '' }) {
  const navigate = useNavigate()
  const [keyword, setKeyword] = useState(initialKeyword)
  const [location, setLocation] = useState(initialLocation)

  function onSubmit(e) {
    e.preventDefault()
    const params = new URLSearchParams()
    if (keyword) params.set('keyword', keyword)
    if (location) params.set('location', location)
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
            placeholder="Find a professional, service or business"
            style={{ flex: 2, border: 'none', padding: '10px 16px', outline: 'none' }}
          />
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Location"
            style={{
              flex: 1,
              border: 'none',
              borderLeft: '1px solid var(--border)',
              padding: '10px 16px',
              outline: 'none',
            }}
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
          <a href="#login" style={{ fontSize: 14 }}>
            Login
          </a>
          <button
            style={{
              background: 'var(--brand)',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              padding: '8px 16px',
              cursor: 'pointer',
            }}
          >
            Sign up
          </button>
        </div>
      </div>
    </header>
  )
}

export default TopNav
