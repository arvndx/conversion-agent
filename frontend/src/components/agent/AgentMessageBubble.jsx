function AgentMessageBubble({ role, text }) {
  const isUser = role === 'user'

  if (role === 'system') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
        <div
          style={{
            maxWidth: '90%',
            background: '#fff7ed',
            color: '#9a3412',
            border: '1px solid #fdba74',
            borderRadius: 10,
            padding: '7px 12px',
            fontSize: 11.5,
            fontWeight: 600,
            textAlign: 'center',
            lineHeight: 1.4,
          }}
        >
          {text}
        </div>
      </div>
    )
  }

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <div
          style={{
            maxWidth: '88%',
            background: 'linear-gradient(135deg, #7c5cff, var(--brand))',
            color: '#fff',
            borderRadius: 14,
            borderBottomRightRadius: 3,
            padding: '9px 13px',
            fontSize: 13.5,
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
          }}
        >
          {text}
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 18, alignItems: 'flex-start' }}>
      <div
        style={{
          width: 22,
          height: 22,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #6d28d9, var(--brand))',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 11,
          marginTop: 1,
        }}
      >
        ✨
      </div>
      <div style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--ink)', whiteSpace: 'pre-wrap', paddingTop: 2 }}>{text}</div>
    </div>
  )
}

export default AgentMessageBubble
