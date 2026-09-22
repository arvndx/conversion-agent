const CONNECTION_PLATFORMS = ['Google Business Profile', 'Facebook', 'LinkedIn', 'Instagram', 'Twitter/X']

function ConnectionsToggleList({ connections, onToggle }) {
  const connectedSet = new Set(connections.filter((c) => c.is_connected).map((c) => c.platform_name))

  return (
    <div>
      {CONNECTION_PLATFORMS.map((platform) => {
        const isConnected = connectedSet.has(platform)
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
              onClick={() => onToggle(platform, !isConnected)}
              style={{
                border: '1px solid var(--border)',
                borderRadius: 999,
                padding: '4px 14px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                background: isConnected ? 'var(--success)' : '#fff',
                color: isConnected ? '#fff' : 'var(--ink)',
              }}
            >
              {isConnected ? 'Connected' : 'Connect'}
            </button>
          </div>
        )
      })}
    </div>
  )
}

export default ConnectionsToggleList
