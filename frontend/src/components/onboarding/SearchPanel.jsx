import { useEffect, useState } from 'react'
import { pluralize } from './sourceMeta.js'

export function useRotating(lines, ms = 3400) {
  const [n, setN] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setN((x) => x + 1), ms)
    return () => clearInterval(t)
  }, [ms])
  return lines[n % lines.length]
}

// While the web is being searched: what is being looked for, and where. Never an invented count.
function SearchPanel({ data, found = 0 }) {
  const p = data.profile
  const who = [p.name, p.title || data.category?.name].filter(Boolean).join(' · ')
  const steps = [
    `Searching the web for “${who}”${p.location ? ` in ${p.location}` : ''}…`,
    'Going through the results…',
    'Filtering out pages that are not you…',
    'Picking the best matches for you…',
  ]
  const line = useRotating(steps, 3000)
  return (
    <div className="rd-search pilot-rise">
      <div className="rd-search__top">
        <span className="rd-search__icon"><span className="ob-spinner" /></span>
        <div>
          <div className="rd-hero__title" style={{ fontSize: '0.98rem' }}>Looking for more of your pages</div>
          <div className="rd-hero__sub" key={line}>{line}</div>
        </div>
      </div>
      <div className="rd-search__rows">
        {[88, 70, 80].map((w, i) => <div key={i} className="pilot-shimmer" style={{ height: 10, width: `${w}%` }} />)}
      </div>
      {found > 0 && <div className="ob-hint" style={{ marginTop: 10 }}>{pluralize(found, 'possible page')} so far</div>}
    </div>
  )
}

export default SearchPanel
