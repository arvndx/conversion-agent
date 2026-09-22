import ProgressBar from '../shared/ProgressBar.jsx'

function AIWritingStudioCard({ studio }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 16, marginTop: 16 }}>
      <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>Your AI Writing Studio ⓘ</h3>
      <div style={{ fontSize: 24, fontWeight: 800 }}>{studio.authority_score}</div>
      <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginBottom: 8 }}>Authority Score</div>
      <ProgressBar percent={studio.authority_score} />

      <div style={{ display: 'flex', gap: 20, marginTop: 12 }}>
        <div>
          <div style={{ fontWeight: 700 }}>{studio.articles_count}</div>
          <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>Articles</div>
        </div>
        <div>
          <div style={{ fontWeight: 700 }}>{studio.answers_count}</div>
          <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>Answers</div>
        </div>
      </div>

      <button
        style={{
          width: '100%',
          marginTop: 12,
          background: 'var(--brand)',
          color: '#fff',
          border: 'none',
          borderRadius: 8,
          padding: '10px 0',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        ✎ Write Article
      </button>
      <div style={{ textAlign: 'center', fontSize: 10, color: 'var(--ink-soft)', marginTop: 8 }}>POWERED BY VOCE</div>
    </div>
  )
}

export default AIWritingStudioCard
