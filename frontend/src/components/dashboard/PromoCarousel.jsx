function PromoCarousel() {
  return (
    <div
      style={{
        background: 'linear-gradient(120deg, #1e1b4b, #4527d1)',
        color: '#fff',
        borderRadius: 'var(--radius)',
        padding: 24,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 16,
      }}
    >
      <div>
        <div style={{ fontSize: 20, fontWeight: 800 }}>Meet Your ✨ AI Content Agent</div>
        <div style={{ fontSize: 13, opacity: 0.85, marginTop: 4 }}>Create, publish, and be cited in AI search.</div>
      </div>
      <button
        style={{
          background: '#fff',
          color: 'var(--brand)',
          border: 'none',
          borderRadius: 8,
          padding: '10px 20px',
          fontWeight: 700,
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        Get Started →
      </button>
    </div>
  )
}

export default PromoCarousel
