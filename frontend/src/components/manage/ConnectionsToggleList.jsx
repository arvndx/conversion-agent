import PlatformIcon from '../shared/PlatformIcon.jsx'

// The category's social slots come from the server; the fallback is the usual five.
const DEFAULT_PLATFORMS = ['Google Business Profile', 'Facebook', 'LinkedIn', 'Twitter/X', 'Instagram']

function ConnectionsToggleList({ connections, slots = DEFAULT_PLATFORMS, onToggle }) {
  const connectedSet = new Set(connections.filter((c) => c.is_connected).map((c) => c.platform_name))

  return (
    <div>
      {slots.map((platform) => {
        const isConnected = connectedSet.has(platform)
        return (
          <div key={platform} className={`link-row${isConnected ? ' link-row--on' : ''}`}>
            <PlatformIcon name={platform} />
            <div className="link-row__name">
              {platform}
              <small>{isConnected ? 'Counting toward your score' : 'Not connected'}</small>
            </div>
            <button onClick={() => onToggle(platform, !isConnected)} className={`pill-btn${isConnected ? ' pill-btn--on' : ''}`}>
              {isConnected ? '✓ Connected' : 'Connect'}
            </button>
          </div>
        )
      })}
    </div>
  )
}

export default ConnectionsToggleList
