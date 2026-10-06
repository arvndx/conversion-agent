import PlatformIcon from '../shared/PlatformIcon.jsx'

function DirectoryListingsSection({ locked, slots = [], listings, onToggle }) {
  // The platforms are this category's directory slots (Zillow, LendingTree, Yelp, ...), whether or not the
  // profile has a record for them yet; anything else already recorded (an old directory) is listed after them.
  const recorded = (listings?.platforms || []).map((p) => p.name)
  const platforms = [...slots, ...recorded.filter((name) => !slots.includes(name))]
  const published = new Set((listings?.platforms || []).filter((p) => p.is_published).map((p) => p.name))

  if (locked) {
    return (
      <div className="locked-note">
        <span style={{ fontSize: 22 }}>🔒</span>
        <span>Upgrade to Pro to unlock Listings management across {platforms.length} directory platforms.</span>
      </div>
    )
  }

  return (
    <div>
      {platforms.map((platform) => {
        const isPublished = published.has(platform)
        return (
          <div key={platform} className={`link-row${isPublished ? ' link-row--on' : ''}`}>
            <PlatformIcon name={platform} />
            <div className="link-row__name">
              {platform}
              <small>{isPublished ? 'Your listing is live' : 'Not published yet'}</small>
            </div>
            <button onClick={() => onToggle(platform, !isPublished)} className={`pill-btn${isPublished ? ' pill-btn--on' : ''}`}>
              {isPublished ? '✓ Published' : 'Publish'}
            </button>
          </div>
        )
      })}
    </div>
  )
}

export default DirectoryListingsSection
