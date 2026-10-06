const SHARDS = [
  { a: '0deg', d: 78, color: 'var(--p-2)' },
  { a: '52deg', d: 62, color: 'var(--p-3)' },
  { a: '104deg', d: 88, color: 'var(--p-4)' },
  { a: '156deg', d: 58, color: 'var(--p-2)' },
  { a: '208deg', d: 82, color: 'var(--p-3)' },
  { a: '260deg', d: 66, color: 'var(--p-4)' },
  { a: '312deg', d: 74, color: 'var(--p-2)' },
]

// Profile Pilot's mark: a glowing gradient orb with a four-point sparkle and a soft aurora halo.
// `flyIn` plays the one-time entrance (spin-in, two burst rings, flying shards).
function PilotOrb({ size = 108, flyIn = false, animate = true }) {
  return (
    <div style={{ position: 'relative', width: size, height: size, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
      {flyIn && (
        <>
          <div
            className="pilot-burst"
            style={{ position: 'absolute', inset: 0, borderRadius: '50%', border: '2px solid rgba(99, 91, 255, 0.55)', pointerEvents: 'none' }}
          />
          <div
            className="pilot-burst"
            style={{ position: 'absolute', inset: 0, borderRadius: '50%', border: '2px solid rgba(214, 51, 132, 0.42)', animationDelay: '980ms', pointerEvents: 'none' }}
          />
          {SHARDS.map((s, i) => (
            <span
              key={i}
              className="pilot-shard"
              style={{
                position: 'absolute',
                left: '50%',
                top: '50%',
                width: 6,
                height: 6,
                marginLeft: -3,
                marginTop: -3,
                borderRadius: '50%',
                background: s.color,
                pointerEvents: 'none',
                '--shard-a': s.a,
                '--shard-d': `${s.d}px`,
                animationDelay: `${840 + i * 22}ms`,
              }}
            />
          ))}
        </>
      )}

      <div
        className={animate ? 'pilot-halo' : undefined}
        style={{
          position: 'absolute',
          inset: '-10%',
          borderRadius: '50%',
          opacity: 0.4,
          background: 'conic-gradient(from 200deg, rgba(99,91,255,0.55), rgba(214,51,132,0.5), rgba(245,158,11,0.45), rgba(99,91,255,0.55))',
          filter: `blur(${Math.round(size / 5)}px)`,
          pointerEvents: 'none',
        }}
      />

      <div
        className={[animate ? 'pilot-breathe' : '', flyIn ? 'pilot-orb-in' : ''].join(' ').trim() || undefined}
        style={{
          position: 'relative',
          width: size,
          height: size,
          borderRadius: '50%',
          background: 'radial-gradient(circle at 32% 28%, #ffffff 0%, rgba(255,255,255,0.0) 34%), conic-gradient(from 210deg, var(--p-2), var(--p-3), var(--p-4), var(--p-2))',
          boxShadow: `0 ${Math.round(size / 8)}px ${Math.round(size / 3)}px rgba(99, 91, 255, 0.35), inset 0 -${Math.round(size / 14)}px ${Math.round(size / 8)}px rgba(0,0,0,0.12)`,
          display: 'grid',
          placeItems: 'center',
        }}
      >
        <svg width={size * 0.46} height={size * 0.46} viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 2c.6 4.8 2.6 8.8 8.5 10-5.9 1.2-7.9 5.2-8.5 10-.6-4.8-2.6-8.8-8.5-10C9.4 10.8 11.4 6.8 12 2z" fill="#fff" />
        </svg>
      </div>
    </div>
  )
}

export default PilotOrb
