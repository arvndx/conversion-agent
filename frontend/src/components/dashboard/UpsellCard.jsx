function UpsellCard({ card, onUnlock }) {
  const [headline, subtext] = card.copy.split(' — ')

  return (
    <div
      style={{
        background: '#111827',
        color: '#fff',
        borderRadius: 'var(--radius)',
        padding: 16,
        flex: 1,
        minWidth: 220,
      }}
      data-agent-target={`upsell-${card.key}`}
    >
      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{headline}</div>
      {subtext && <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 12 }}>{subtext}</div>}
      <button
        onClick={onUnlock}
        style={{
          background: 'var(--pro-badge)',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          padding: '8px 14px',
          fontSize: 13,
          fontWeight: 700,
          cursor: 'pointer',
        }}
      >
        👑 UNLOCK MORE POINTS
      </button>
    </div>
  )
}

export default UpsellCard
