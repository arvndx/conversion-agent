const VARIANTS = {
  verified: { background: '#e6f0ff', color: '#1d4ed8', label: '✓ Verified' },
  pro: { background: 'var(--pro-badge)', color: '#fff', label: 'PRO' },
  top5: { background: '#111827', color: '#fff', label: 'Top 5%' },
}

function Badge({ variant, children }) {
  const preset = VARIANTS[variant]
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 8px',
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        background: preset?.background ?? '#eee',
        color: preset?.color ?? '#333',
      }}
    >
      {children ?? preset?.label}
    </span>
  )
}

export default Badge
