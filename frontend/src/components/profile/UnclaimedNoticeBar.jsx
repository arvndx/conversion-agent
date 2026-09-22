function UnclaimedNoticeBar({ onClaim, claiming }) {
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
        disabled={claiming}
        style={{
          background: 'var(--brand)',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          padding: '8px 16px',
          fontWeight: 600,
          fontSize: 13,
          cursor: claiming ? 'default' : 'pointer',
        }}
      >
        {claiming ? 'Sending…' : 'Is this your profile?'}
      </button>
    </div>
  )
}

export default UnclaimedNoticeBar
