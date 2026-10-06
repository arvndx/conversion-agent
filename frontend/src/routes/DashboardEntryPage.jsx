import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

// /dashboard sends a signed-in agent to their own dashboard (or to onboarding, if they have not finished
// it), and everyone else to sign in.
function DashboardEntryPage() {
  const { me } = useAuth()
  if (me === null) return null
  if (!me.authenticated) return <Navigate to="/signin?next=/dashboard" replace />
  return <Navigate to={me.onboarding_completed === false ? `/onboarding/${me.profile_id}` : `/dashboard/${me.profile_id}`} replace />
}

export default DashboardEntryPage
