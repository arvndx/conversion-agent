function ReviewsList({ reviews }) {
  if (!reviews?.length) {
    return <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No reviews yet.</div>
  }

  return (
    <div>
      {reviews.map((r, i) => (
        <div key={i} style={{ borderBottom: '1px solid var(--border)', padding: '12px 0' }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>
            {r.reviewer_name} <span style={{ color: '#f59e0b' }}>{'★'.repeat(r.rating)}</span>
          </div>
          <div style={{ fontSize: 14, marginTop: 4 }}>{r.body}</div>
          {r.reply && (
            <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 6, paddingLeft: 12, borderLeft: '2px solid var(--border)' }}>
              Reply: {r.reply}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default ReviewsList
