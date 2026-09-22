import { useLocation } from 'react-router-dom'
import { useActiveProfile } from '../../context/ActiveProfileContext.jsx'

// Parses the profile id straight out of the URL rather than using useParams() —
// AgentWidget is mounted as a sibling of <Routes>, not inside any one <Route>'s
// element tree, so useParams() there never sees the matched route's params.
const ROUTE_PATTERNS = [/^\/profile\/(\d+)/, /^\/dashboard\/(\d+)/, /^\/claim\/(\d+)\/details/]

function useCurrentProfileId() {
  const location = useLocation()
  const { activeProfileId } = useActiveProfile()

  for (const pattern of ROUTE_PATTERNS) {
    const match = location.pathname.match(pattern)
    if (match) return match[1]
  }
  return activeProfileId || null
}

export default useCurrentProfileId
