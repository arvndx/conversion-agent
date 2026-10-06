import Panel from '../shared/Panel.jsx'
import ProgressBar from '../shared/ProgressBar.jsx'

function AIWritingStudioCard({ studio }) {
  return (
    <Panel icon="✍️" tint="#ffe9f3" title="AI Writing Studio" subtitle="Be cited in AI search">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-0.03em' }}>{studio.authority_score}</span>
        <span className="panel__sub">Authority Score</span>
      </div>
      <ProgressBar percent={studio.authority_score} color="linear-gradient(90deg, #ff7eb3, #ff5c8a)" />

      <div className="stat-pair">
        <div><b>{studio.articles_count}</b><small>Articles</small></div>
        <div><b>{studio.answers_count}</b><small>Answers</small></div>
      </div>

      <button className="btn btn--primary btn--block">✎ Write Article</button>
      <div style={{ textAlign: 'center', fontSize: 10.5, letterSpacing: '0.08em', color: '#98a0ae', marginTop: 10 }}>POWERED BY VOCE</div>
    </Panel>
  )
}

export default AIWritingStudioCard
