const CHECKS = [
  { key: 'has_meta_description', label: 'Meta description for search snippets' },
  { key: 'mobile_friendly', label: 'Mobile-friendly' },
  { key: 'has_contact_info', label: 'Contact info clearly listed' },
  { key: 'has_business_hours_listed', label: 'Business hours listed' },
]

function AnalyticsReadout({ isPro, websiteUrl, websiteAudit }) {
  if (!isPro) {
    return (
      <div className="locked-note">
        <span style={{ fontSize: 22 }}>🔒</span>
        <span>Upgrade to Pro to unlock your Website Health audit.</span>
      </div>
    )
  }

  if (!websiteUrl) {
    return <div className="empty-note">Add your website URL in Profile Details above to get a health audit.</div>
  }

  const audit = websiteAudit || {}
  const loadTimeMs = audit.load_time_ms
  const loadTimeOk = loadTimeMs != null && loadTimeMs <= 2500

  return (
    <div>
      <div className="metric">
        <b>{loadTimeMs != null ? `${loadTimeMs}ms` : '—'}</b>
        <span style={{ color: loadTimeOk ? 'var(--success)' : '#b45309' }}>
          <small>{loadTimeOk ? '✓ Fast load time' : '⚠ Slow load time (target: under 2.5s)'}</small>
        </span>
      </div>
      <div className="check-grid">
        {CHECKS.map(({ key, label }) => {
          const passed = Boolean(audit[key])
          return (
            <div key={key} className={`check ${passed ? 'check--ok' : 'check--bad'}`}>
              <i>{passed ? '✓' : '!'}</i>
              <span style={{ flex: 1 }}>{label}</span>
              <small style={{ color: passed ? 'var(--success)' : '#b45309', fontWeight: 700 }}>{passed ? 'Pass' : 'Needs work'}</small>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default AnalyticsReadout
