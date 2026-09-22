function ScarcityBanner({ location, category, proTaken, proSlotsPerMarket }) {
  if (!location) return null

  const remaining = proSlotsPerMarket - proTaken
  const isFull = remaining <= 0

  return (
    <div
      style={{
        background: isFull ? '#111827' : 'linear-gradient(90deg, #5b3df5, #7c5cff)',
        color: '#fff',
        borderRadius: 'var(--radius)',
        padding: '12px 20px',
        marginBottom: 16,
        fontSize: 14,
        fontWeight: 600,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      {isFull ? (
        <>🔒 All 5 Pro spots for {category} in {location} are taken.</>
      ) : (
        <>
          🔥 Only {remaining} of {proSlotsPerMarket} Pro spots left for {category} in {location} — grab yours before
          someone else does.
        </>
      )}
    </div>
  )
}

export default ScarcityBanner
