const PALETTE = ['#5b3df5', '#0891b2', '#c2410c', '#15803d', '#a21caf', '#b91c1c', '#4338ca', '#0f766e']

function initials(name) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
}

function colorFor(name) {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  }
  return PALETTE[hash % PALETTE.length]
}

function AvatarCircle({ name, avatarUrl, size = 48 }) {
  const style = {
    width: size,
    height: size,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 600,
    fontSize: size * 0.38,
    flexShrink: 0,
    overflow: 'hidden',
  }

  if (avatarUrl) {
    return <img src={avatarUrl} alt={name} style={{ ...style, objectFit: 'cover' }} />
  }

  return (
    <div style={{ ...style, background: colorFor(name || '?'), color: '#fff' }}>
      {initials(name || '?')}
    </div>
  )
}

export default AvatarCircle
