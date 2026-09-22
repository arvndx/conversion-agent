function ProgressBar({ percent, color = 'var(--brand)', height = 6 }) {
  const clamped = Math.max(0, Math.min(100, percent))
  return (
    <div style={{ background: 'var(--border)', borderRadius: 999, height, overflow: 'hidden' }}>
      <div style={{ width: `${clamped}%`, background: color, height: '100%', borderRadius: 999 }} />
    </div>
  )
}

export default ProgressBar
