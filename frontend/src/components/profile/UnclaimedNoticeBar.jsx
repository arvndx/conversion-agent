function UnclaimedNoticeBar({ onClaim }) {
  return (
    <div
      style={{
        background: '#111827',
        color: '#fff',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 24px',
      }}
    >
      <span style={{ fontSize: 13 }}>ⓘ Unclaimed Profile</span>
      <button
        onClick={onClaim}
        style={{
          background: 'var(--brand)',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          padding: '8px 16px',
          fontWeight: 600,
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        Claim now
      </button>
    </div>
  )
}

export default UnclaimedNoticeBar
