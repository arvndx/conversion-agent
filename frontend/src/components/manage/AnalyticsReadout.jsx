const CHECKS = [
  { key: 'has_meta_description', label: 'Meta description for search snippets' },
  { key: 'mobile_friendly', label: 'Mobile-friendly' },
  { key: 'has_contact_info', label: 'Contact info clearly listed' },
  { key: 'has_business_hours_listed', label: 'Business hours listed' },
]

function AnalyticsReadout({ isPro, websiteUrl, websiteAudit }) {
  if (!isPro) {
    return (
      <div style={{ background: 'var(--surface-muted)', borderRadius: 8, padding: 16, color: 'var(--ink-soft)', fontSize: 13 }}>
        🔒 Upgrade to Pro to unlock your Website Health audit.
      </div>
    )
  }

  if (!websiteUrl) {
    return (
      <div style={{ background: 'var(--surface-muted)', borderRadius: 8, padding: 16, color: 'var(--ink-soft)', fontSize: 13 }}>
        Add your website URL in Profile Details above to get a health audit.
      </div>
    )
  }

  const audit = websiteAudit || {}
  const loadTimeMs = audit.load_time_ms
  const loadTimeOk = loadTimeMs != null && loadTimeMs <= 2500

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 20 }}>{loadTimeMs != null ? `${loadTimeMs}ms` : '—'}</span>
        <span style={{ fontSize: 12, color: loadTimeOk ? 'var(--success)' : '#b45309' }}>
          {loadTimeOk ? '✓ Fast load time' : '⚠ Slow load time (target: under 2.5s)'}
        </span>
      </div>
      <div>
        {CHECKS.map(({ key, label }) => {
          const passed = Boolean(audit[key])
          return (
            <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: 13 }}>{label}</span>
              <span style={{ fontSize: 13, color: passed ? 'var(--success)' : '#b45309', fontWeight: 600 }}>
                {passed ? '✓ Pass' : '⚠ Needs work'}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default AnalyticsReadout
