function ProgressBar({ percent, color = 'var(--brand)', height = 8 }) {
  const clamped = Math.max(0, Math.min(100, percent))
  return (
    <div className="bar" style={{ height }}>
      <i style={{ width: `${clamped}%`, background: color }} />
    </div>
  )
}

export default ProgressBar
