import { useEffect, useMemo, useState } from 'react'

const DURATION_MS = 2600
const COLORS = ['#7c5cff', '#f59e0b', '#22c55e', '#ef4444', '#3b82f6', '#ec4899']
const PARTICLE_COUNT = 60

function makeParticles() {
  return Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
    id: i,
    left: Math.random() * 100,
    delay: Math.random() * 0.4,
    duration: 1.8 + Math.random() * 1.2,
    size: 6 + Math.random() * 7,
    color: COLORS[i % COLORS.length],
    rotate: Math.random() * 360,
    drift: (Math.random() - 0.5) * 160,
    isCircle: Math.random() > 0.5,
  }))
}

function CelebrationOverlay({ trigger }) {
  const [visible, setVisible] = useState(false)
  const particles = useMemo(() => makeParticles(), [trigger])

  useEffect(() => {
    if (!trigger) return
    setVisible(true)
    const timer = setTimeout(() => setVisible(false), DURATION_MS)
    return () => clearTimeout(timer)
  }, [trigger])

  if (!visible) return null

  return (
    <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 9999, overflow: 'hidden' }}>
      {particles.map((p) => (
        <div
          key={p.id}
          style={{
            position: 'absolute',
            top: -20,
            left: `${p.left}%`,
            width: p.size,
            height: p.size,
            background: p.color,
            borderRadius: p.isCircle ? '50%' : 2,
            animation: `clearrank-confetti-fall ${p.duration}s ${p.delay}s ease-in forwards`,
            '--drift': `${p.drift}px`,
            '--rotate': `${p.rotate}deg`,
          }}
        />
      ))}
      <div
        style={{
          position: 'absolute',
          top: '18vh',
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 22,
          fontWeight: 800,
          color: 'var(--ink)',
          background: '#fff',
          padding: '12px 24px',
          borderRadius: 999,
          boxShadow: '0 12px 36px rgba(0,0,0,0.18)',
          animation: 'clearrank-celebrate-badge 2.6s ease-out forwards',
          whiteSpace: 'nowrap',
        }}
      >
        🎉 Nice work!
      </div>
      <style>{`
        @keyframes clearrank-confetti-fall {
          0% { transform: translate(0, 0) rotate(0deg); opacity: 1; }
          100% { transform: translate(var(--drift), 100vh) rotate(var(--rotate)); opacity: 0; }
        }
        @keyframes clearrank-celebrate-badge {
          0% { transform: translateX(-50%) scale(0.6); opacity: 0; }
          15% { transform: translateX(-50%) scale(1.08); opacity: 1; }
          25% { transform: translateX(-50%) scale(1); opacity: 1; }
          80% { transform: translateX(-50%) scale(1); opacity: 1; }
          100% { transform: translateX(-50%) scale(1); opacity: 0; }
        }
      `}</style>
    </div>
  )
}

export default CelebrationOverlay
