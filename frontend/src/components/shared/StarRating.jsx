function StarRating({ rating = 0, count }) {
  const rounded = Math.round(rating)
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 14 }}>
      <span
        style={{
          background: 'var(--ink)',
          color: '#fff',
          borderRadius: 4,
          padding: '1px 6px',
          fontWeight: 700,
          fontSize: 12,
        }}
      >
        {rating.toFixed(2)}
      </span>
      <span style={{ color: '#f59e0b', letterSpacing: 1 }}>
        {'★'.repeat(rounded)}
        {'☆'.repeat(5 - rounded)}
      </span>
      {typeof count === 'number' && <span style={{ color: 'var(--ink-soft)' }}>({count})</span>}
    </span>
  )
}

export default StarRating
