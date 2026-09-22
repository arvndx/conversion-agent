const DIRECTORY_PLATFORMS = ['Google Business Profile', 'Yelp', 'Facebook', 'Apple Maps', 'Voice Search']

function DirectoryListingsSection({ isPro, listings, onToggle }) {
  const published = new Set((listings?.platforms || []).filter((p) => p.is_published).map((p) => p.name))

  if (!isPro) {
    return (
      <div style={{ background: 'var(--surface-muted)', borderRadius: 8, padding: 16, color: 'var(--ink-soft)', fontSize: 13 }}>
        🔒 Upgrade to Pro to unlock Listings management across {DIRECTORY_PLATFORMS.length} directory platforms.
      </div>
    )
  }

  return (
    <div>
      {DIRECTORY_PLATFORMS.map((platform) => {
        const isPublished = published.has(platform)
        return (
          <div
            key={platform}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '10px 0',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <span style={{ fontSize: 14 }}>{platform}</span>
            <button
              onClick={() => onToggle(platform, !isPublished)}
              style={{
                border: '1px solid var(--border)',
                borderRadius: 999,
                padding: '4px 14px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                background: isPublished ? 'var(--success)' : '#fff',
                color: isPublished ? '#fff' : 'var(--ink)',
              }}
            >
              {isPublished ? 'Published' : 'Publish'}
            </button>
          </div>
        )
      })}
    </div>
  )
}

export default DirectoryListingsSection
