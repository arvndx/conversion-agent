import { useState } from 'react'
import PilotOrb from '../pilot/PilotOrb.jsx'

// **bold** in a line of the agent's text.
function inline(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )
}

// The agent's own words, shown on the main screen (not only in the chat panel): short paragraphs and bullet
// lists, as it wrote them.
function AgentVoice({ text, clamp = false }) {
  const [open, setOpen] = useState(false)
  const lines = String(text || '').split('\n').map((l) => l.trim()).filter(Boolean)
  const blocks = []
  for (const line of lines) {
    const bullet = line.match(/^([-•*]|\d+[.)])\s+(.*)$/)
    if (bullet) {
      const last = blocks[blocks.length - 1]
      if (last?.list) last.items.push(bullet[2])
      else blocks.push({ list: true, items: [bullet[2]] })
    } else {
      blocks.push({ text: line })
    }
  }
  const long = clamp && (blocks.length > 2 || String(text).length > 170)
  return (
    <div className={`ob-voice pilot-rise${long && !open ? ' ob-voice--clamp' : ''}${long && open ? ' ob-voice--open' : ''}`} key={text}>
      <PilotOrb size={30} animate={false} />
      <div className="ob-voice__body">
        {blocks.map((b, i) =>
          b.list ? (
            <ul key={i}>{b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}</ul>
          ) : (
            <p key={i}>{inline(b.text)}</p>
          ),
        )}
        {long && <button className="ob-link ob-voice__more" onClick={() => setOpen(!open)}>{open ? 'Show less ▴' : 'Show more ▾'}</button>}
      </div>
    </div>
  )
}

export default AgentVoice
