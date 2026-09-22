import { useState } from 'react'

function PromoBanner() {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  return (
    <div
      style={{
        background: 'linear-gradient(90deg, #5b3df5, #7c5cff)',
        color: '#fff',
        padding: '8px 20px',
        fontSize: 13,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <strong>The Next Era of Search Has Arrived</strong>
      <span style={{ opacity: 0.9 }}>Customers are searching right now. Don&apos;t get left out of the AI answers.</span>
      <button
        style={{
          marginLeft: 'auto',
          background: '#fff',
          color: 'var(--brand)',
          border: 'none',
          borderRadius: 6,
          padding: '4px 12px',
          fontWeight: 600,
          fontSize: 12,
          cursor: 'pointer',
        }}
      >
        Learn about AI Visibility →
      </button>
      <span style={{ opacity: 0.8, fontSize: 11 }}>powered by VOCE</span>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: 14 }}
      >
        ✕
      </button>
    </div>
  )
}

export default PromoBanner
